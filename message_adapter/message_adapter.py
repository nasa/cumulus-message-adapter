import os
import json

from copy import deepcopy
from jsonschema import validate

from .util import assign_json_path_value
from .cumulus_message import (resolve_config_templates, resolve_input,
                              resolve_path_str, load_config, load_remote_event,
                              store_remote_response)


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

        if context and 'meta' in event:
            task_meta = {}
            task_meta['name'] = context.get('function_name', context.get('functionName'))
            task_meta['version'] = context.get('function_version', context.get('functionVersion'))
            task_meta['arn'] = context.get('invoked_function_arn',
                                           context.get('invokedFunctionArn',
                                                       context.get('activityArn')))
            if not 'workflow_tasks' in event['meta']:
                event['meta']['workflow_tasks'] = {}
            task_index = len(event['meta']['workflow_tasks'])
            event['meta']['workflow_tasks'][task_index] = task_meta
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
            with open(schema_filepath, encoding='utf-8') as schema_handle:
                schema = json.load(schema_handle)
                try:
                    validate(document, schema)
                except Exception as exception:
                    exception.message = f'{schema_type} schema: {str(exception)}'
                    raise exception

    def load_nested_event(self, event):
        """
        * Interprets an incoming event as a Cumulus workflow message
        *
        * @param {*} event The input message sent to the Lambda
        * @returns {*} message that is ready to pass to an inner task
        """
        config = load_config(event)
        final_config = resolve_config_templates(event, config)
        final_payload = resolve_input(event, config)
        response = {'input': final_payload}
        self.__validate_json(final_payload, 'input')
        if final_config:
            self.__validate_json(final_config, 'config')
            response['config'] = final_config
        else:
            response['config'] = {}
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
        return store_remote_response(result, self.REMOTE_DEFAULT_MAX_SIZE, self.CMA_CONFIG_KEYS)
