import os
import json
import sys

from copy import deepcopy
from datetime import datetime, timedelta
import uuid
from jsonpath_ng import parse
from jsonschema import validate
from .aws import get_current_sfn_task, s3

from .util import assign_json_path_value
from .cumulus_message import (resolve_config_templates, resolve_input,
                              resolve_path_str, load_config, load_remote_event)


class MessageAdapter:
    """
    transforms the cumulus message
    """
    REMOTE_DEFAULT_MAX_SIZE = 0
    CMA_CONFIG_KEYS = ['ReplaceConfig', 'task_config']

    def __init__(self, schemas=None):
        self.schemas = schemas

    ##################################
    #  Input message interpretation  #
    ##################################

    @staticmethod
    def __parse_parameter_configuration(event):
        parsed_event = event
        if event.get('cma'):
            updated_event = {k: v for (k, v) in event['cma'].items() if k != 'event'}
            parsed_event = event['cma']['event']
            parsed_event.update(updated_event)
        return parsed_event

    def load_and_update_remote_event(self, incoming_event, context):
        """
        * Looks at a Cumulus message. If the message has part of its data stored remotely in
        * S3, fetches that data, otherwise it returns the full message, both cases updated with
        * task metadata.
        * If event uses parameterized configuration, converts message into a
        * Cumulus message and ensures that incoming parameter keys are not overridden
        * @param {*} event The input Lambda event in the Cumulus message protocol
        * @returns {*} the full event data
        """
        event = deepcopy(incoming_event)

        if incoming_event.get('cma'):
            cma_event = deepcopy(incoming_event)
            event = load_remote_event(event['cma'].get('event'))
            cma_event['cma']['event'].update(event)
            event = self.__parse_parameter_configuration(cma_event)
        else:
            event = load_remote_event(event)

        if context and 'meta' in event and 'workflow_tasks' in event['meta']:
            cumulus_meta = event['cumulus_meta']
            task_meta = {}
            task_meta['name'] = context.get('function_name', context.get('functionName'))
            task_meta['version'] = context.get('function_version', context.get('functionVersion'))
            task_meta['arn'] = context.get('invoked_function_arn',
                                           context.get('invokedFunctionArn',
                                                       context.get('activityArn')))
            task_name = get_current_sfn_task(cumulus_meta['state_machine'],
                                             cumulus_meta['execution_name'],
                                             task_meta['arn'])
            event['meta']['workflow_tasks'][task_name] = task_meta
        return event

    def __get_jsonschema(self, schema_type):
        schemas = self.schemas
        root_dir = os.environ.get("LAMBDA_TASK_ROOT", '')
        has_schema = schemas and schemas.get(schema_type)
        rel_filepath = schemas.get(schema_type) if has_schema else f'schemas/{schema_type}.json'
        filepath = os.path.join(root_dir, rel_filepath)
        return filepath if os.path.exists(filepath) else None

    def __validate_json(self, document, schema_type):
        """
        check that json is valid based on a schema
        """
        schema_filepath = self.__get_jsonschema(schema_type)
        if schema_filepath:
            schema = json.load(open(schema_filepath))
            try:
                validate(document, schema)
            except Exception as exception:
                exception.message = f'{schema_type} schema: {str(exception)}'
                raise exception

    def load_nested_event(self, event, context):
        """
        * Interprets an incoming event as a Cumulus workflow message
        *
        * @param {*} event The input message sent to the Lambda
        * @returns {*} message that is ready to pass to an inner task
        """
        config = load_config(event, context)
        final_config = resolve_config_templates(event, config)
        final_payload = resolve_input(event, config)
        response = {'input': final_payload}
        self.__validate_json(final_payload, 'input')
        self.__validate_json(final_config, 'config')
        if final_config is not None:
            response['config'] = final_config
        if 'cumulus_message' in config:
            response['messageConfig'] = config['cumulus_message']

        # add cumulus_config property, only selective attributes from event.cumulus_meta are added
        if 'cumulus_meta' in event:
            response['cumulus_config'] = {}
            # add both attributes or none of them
            attributes = ['state_machine', 'execution_name']
            if all(attribute in event['cumulus_meta'] for attribute in attributes):
                for attribute in attributes:
                    response['cumulus_config'][attribute] = event['cumulus_meta'][attribute]

            # add attribute cumulus_context
            if 'cumulus_context' in event['cumulus_meta']:
                cumulus_context = event['cumulus_meta']['cumulus_context']
                response['cumulus_config']['cumulus_context'] = cumulus_context

            if not response['cumulus_config']:
                del response['cumulus_config']

        return response


    @staticmethod
    def __assign_outputs(handler_response, event, message_config):
        """
        * Applies a task's return value to an output message as defined in config.cumulus_message
        *
        * @param {*} handler_response The task's return value
        * @param {*} event The output message to apply the return value to
        * @param {*} messageConfig The cumulus_message configuration
        * @returns {*} The output message with the nested response applied
        """
        result = deepcopy(event)
        if message_config is not None and 'outputs' in message_config:
            outputs = message_config['outputs']
            result['payload'] = {}
            for output in outputs:
                source_path = output['source']
                dest_path = output['destination']
                dest_json_path = dest_path.lstrip('{').rstrip('}')
                value = resolve_path_str(handler_response, source_path)
                result = assign_json_path_value(result, dest_json_path, value)
        else:
            result['payload'] = handler_response

        return result

    def __parse_remote_config_from_event(self, replace_config):
        source_path = replace_config['Path']
        target_path = replace_config.get('TargetPath', replace_config['Path'])
        max_size = replace_config.get('MaxSize', self.REMOTE_DEFAULT_MAX_SIZE)
        parsed_json_path = parse(source_path)

        return {
            'target_path': target_path,
            'max_size': max_size,
            'parsed_json_path': parsed_json_path,
        }

    def __store_remote_response(self, incoming_event):
        """
        * Stores part of a response message in S3 if it is too big to send to StepFunctions
        * @param {*} event The response message
        * @returns {*} A response message, possibly referencing an S3 object for its contents
        """
        event = deepcopy(incoming_event)
        replace_config = event.get('ReplaceConfig', None)
        if not replace_config:
            return event
        # Set default value if FullMessage flag set
        if replace_config.get('FullMessage', False):
            replace_config['Path'] = '$'

        replace_config_values = self.__parse_remote_config_from_event(replace_config)

        for key in self.CMA_CONFIG_KEYS:
            if event.get(key):
                del event[key]
        cumulus_meta = deepcopy(event['cumulus_meta'])
        replacement_data = replace_config_values['parsed_json_path'].find(event)
        if len(replacement_data) != 1:
            raise Exception(f'JSON path invalid: {replace_config_values["parsed_json_path"]}')
        replacement_data = replacement_data[0]

        estimated_data_size = len(json.dumps(replacement_data.value))
        if sys.version_info.major > 3:
            estimated_data_size = len(json.dumps(replacement_data.value).encode(('utf-8')))

        if estimated_data_size < replace_config_values['max_size']:
            return event

        _s3 = s3()
        s3_bucket = event['cumulus_meta']['system_bucket']
        s3_key = ('/').join(['events', str(uuid.uuid4())])
        s3_params = {
            'Expires': datetime.utcnow() + timedelta(days=7),  # Expire in a week
            'Body': json.dumps(replacement_data.value)
        }
        _s3.Object(s3_bucket, s3_key).put(**s3_params)

        try:
            replacement_data.value.clear()
        except AttributeError:
            replace_config_values['parsed_json_path'].update(event, '')

        remote_configuration = {'Bucket': s3_bucket, 'Key': s3_key,
                                'TargetPath': replace_config_values['target_path']}
        event['cumulus_meta'] = event.get('cumulus_meta', cumulus_meta)
        event['replace'] = remote_configuration
        return event

    def create_next_event(self, handler_response, event, message_config):
        """
        * Creates the output message returned by a task
        *
        * @param {*} handler_response The response returned by the inner task code
        * @param {*} event The input message sent to the Lambda
        * @param {*} message_config The cumulus_message object configured for the task
        * @returns {*} the output message to be returned
        """
        self.__validate_json(handler_response, 'output')

        result = self.__assign_outputs(handler_response, event, message_config)
        if not result.get('exception'):
            result['exception'] = 'None'
        if 'replace' in result:
            del result['replace']
        return self.__store_remote_response(result)
