import os
import json
import re
import sys

from copy import deepcopy
from datetime import datetime, timedelta
import uuid
from jsonpath_ng import parse
from jsonschema import validate
from .aws import stepFn, s3


class MessageAdapter:
    """
    transforms the cumulus message
    """
    REMOTE_DEFAULT_MAX_SIZE = 0
    CMA_CONFIG_KEYS = ['ReplaceConfig', 'task_config']

    def __init__(self, schemas=None):
        self.schemas = schemas

    def __get_sfn_execution_arn_by_name(self, state_machine_arn, execution_name):
        """
        * Given a state machine arn and execution name, returns the execution's ARN
        * @param {string} state_machine_arn The ARN of the state machine containing the execution
        * @param {string} execution_name The name of the execution
        * @returns {string} The execution's ARN
        """
        return (':').join([state_machine_arn.replace(':stateMachine:', ':execution:'),
                           execution_name])

    def __get_task_name_from_execution_history(self, execution_history, arn):
        """
        * Given an execution history object returned by the StepFunctions API and an optional
        * Activity or Lambda ARN returns the most recent task name started for the given ARN,
        * or if no ARN is supplied, the most recent task started.
        *
        * IMPORTANT! If no ARN is supplied, this message assumes that the most recently started
        * execution is the desired execution. This WILL BREAK parallel executions, so always supply
        * this if possible.
        *
        * @param {dict} executionHistory The execution history returned by getExecutionHistory,
        * assumed to be sorted so most recent executions come last
        * @param {string} arn An ARN to an Activity or Lambda to find. See "IMPORTANT!"
        * @throws If no matching task is found
        * @returns {string} The matching task name
        """
        events_by_id = {}

        # Create a lookup table for finding events by their id
        for event in execution_history['events']:
            events_by_id[event['id']] = event

        for step in execution_history['events']:
            # Find the ARN in thie history (the API is awful here).  When found, return its
            # previousEventId's (TaskStateEntered) name
            if (arn is not None and
                    ((step['type'] == 'LambdaFunctionScheduled' and
                      step['lambdaFunctionScheduledEventDetails']['resource'] == arn) or
                     (step['type'] == 'ActivityScheduled' and
                      step['activityScheduledEventDetails']['resource'] == arn)) and
                    'stateEnteredEventDetails' in events_by_id[step['previousEventId']]):
                return events_by_id[step['previousEventId']]['stateEnteredEventDetails']['name']
            elif step['type'] == 'TaskStateEntered':
                return step['stateEnteredEventDetails']['name']
        raise LookupError('No task found for ' + arn)

    def __get_current_sfn_task(self, state_machine_arn, execution_name, arn):
        """
        * Given a state machine ARN, an execution name, and an optional Activity or Lambda ARN
        * returns the most recent task name started for the given ARN in that execution,
        * or if no ARN is supplied, the most recent task started.
        *
        * IMPORTANT! If no ARN is supplied, this message assumes that the most recently started
        * execution is the desired execution. This WILL BREAK parallel executions, so always supply
        * this if possible.
        *
        * @param {string} state_machine_arn The ARN of the state machine containing the execution
        * @param {string} execution_name The name of the step function execution to look up
        * @param {string} arn An ARN to an Activity or Lambda to find. See "IMPORTANT!"
        * @returns {string} The name of the task being run
        """
        sfn = stepFn()
        execution_arn = self.__get_sfn_execution_arn_by_name(state_machine_arn, execution_name)
        execution_history = sfn.get_execution_history(
            executionArn=execution_arn,
            maxResults=40,
            reverseOrder=True
        )
        return self.__get_task_name_from_execution_history(execution_history, arn)

    ##################################
    #  Input message interpretation  #
    ##################################

    def __parse_parameter_configuration(self, event):
        parsed_event = event
        if event.get('cma'):
            updated_event = {k: v for (k, v) in event['cma'].items() if k != 'event'}
            parsed_event = event['cma']['event']
            parsed_event.update(updated_event)
        return parsed_event

    def __load_remote_event(self, event):
        if 'replace' in event:
            local_exception = event.get('exception', None)
            _s3 = s3()
            data = _s3.Object(event['replace']['Bucket'],
                              event['replace']['Key']).get()
            target_json_path = event['replace']['TargetPath']
            parsed_json_path = parse(target_json_path)
            if data is not None:
                remote_event = json.loads(data['Body'].read().decode('utf-8'))
                replacement_targets = parsed_json_path.find(event)
                if not replacement_targets or len(replacement_targets) != 1:
                    raise Exception(f'Remote event configuration target {target_json_path} invalid')
                try:
                    replacement_targets[0].value.update(remote_event)
                except AttributeError:
                    parsed_json_path.update(event, remote_event)

                event.pop('replace')
                exception_bool = (local_exception and local_exception != 'None')
                if exception_bool and (not event['exception'] or event['exception'] == 'None'):
                    event['exception'] = local_exception
        return event

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
            event = self.__load_remote_event(event['cma'].get('event'))
            cma_event['cma']['event'].update(event)
            event = self.__parse_parameter_configuration(cma_event)
        else:
            event = self.__load_remote_event(event)

        if context and 'meta' in event and 'workflow_tasks' in event['meta']:
            cumulus_meta = event['cumulus_meta']
            task_meta = {}
            task_meta['name'] = context.get('function_name', context.get('functionName'))
            task_meta['version'] = context.get('function_version', context.get('functionVersion'))
            task_meta['arn'] = context.get('invoked_function_arn',
                                           context.get('invokedFunctionArn',
                                                       context.get('activityArn')))
            task_name = self.__get_current_sfn_task(cumulus_meta['state_machine'],
                                                    cumulus_meta['execution_name'],
                                                    task_meta['arn'])
            event['meta']['workflow_tasks'][task_name] = task_meta
        return event

    # Loading task configuration from workload template

    def __get_config(self, event, task_name):
        """
        * Returns the configuration for the task with the given name, or an empty object if no
        * such task is configured.
        * @param {*} event An event in the Cumulus message format with remote parts resolved
        * @param {*} task_name The name of the Cumulus task
        * @returns {*} The configuration object
        """
        config = {}
        if ('workflow_config' in event and task_name in event['workflow_config']):
            config = event['workflow_config'][task_name]
        return config

    def __load_step_function_task_name(self, event, context):
        """
        * For StepFunctions, returns the configuration corresponding to the current execution
        * @param {*} event An event in the Cumulus message format with remote parts resolved
        * @param {*} context The context object passed to AWS Lambda or containing an activityArn
        * @returns {*} The task's configuration
        """
        meta = event['cumulus_meta']
        if 'invokedFunctionArn' in context:
            arn = context['invokedFunctionArn']
        else:
            arn = context.get('invoked_function_arn', context.get('activityArn'))
        return self.__get_current_sfn_task(meta['state_machine'], meta['execution_name'], arn)

    def __load_config(self, event, context):
        """
        * Given a Cumulus message and context, returns the config object for the task
        * @param {*} event An event in the Cumulus message format with remote parts resolved
        * @param {*} context The context object passed to AWS Lambda or containing an activityArn
        * @returns {*} The task's configuration
        """
        if 'task_config' in event:
            return event['task_config']
        # Maintained for backwards compatibility
        source = event['cumulus_meta']['message_source']
        if source is None:
            raise LookupError('cumulus_meta requires a message_source')
        elif source == 'local':
            task_name = event['cumulus_meta']['task']
        elif source == 'sfn':
            task_name = self.__load_step_function_task_name(event, context)
        else:
            raise LookupError('Unknown event source: ' + source)
        return self.__get_config(event, task_name) if task_name is not None else None

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

    # Config templating
    def __resolve_path_str(self, event, json_path_string):
        """
        * Given a Cumulus message (AWS Lambda event) and a string containing a JSONPath
        * template to interpret, returns the result of interpreting that template.
        *
        * Templating comes in three flavors:
        *   1. Single curly-braces within a string ("some{$.path}value"). The JSONPaths
        *      are replaced by the first value they match, coerced to string
        *   2. A string surrounded by double curly-braces ("{{$.path}}").  The function
        *      returns the first object matched by the JSONPath
        *   3. A string surrounded by curly and square braces ("{[$.path]}"). The function
        *      returns an array of all object matching the JSONPath
        *
        * It's likely we'll need some sort of bracket-escaping at some point down the line
        *
        * @param {*} event The Cumulus message
        * @param {*} json_path_string A string containing a JSONPath template to resolve
        * @returns {*} The resolved object
        """
        value_regex = r"^{[^\[\]].*}$"
        array_regex = r"^{\[.*\]}$"
        template_regex = '{[^}]+}'

        if re.search(value_regex, json_path_string):
            match_data = parse(json_path_string.lstrip('{').rstrip('}')).find(event)
            return match_data[0].value if match_data else None

        elif re.search(array_regex, json_path_string):
            parsed_json_path = json_path_string.lstrip('{').rstrip('}').lstrip('[').rstrip(']')
            match_data = parse(parsed_json_path).find(event)
            return [item.value for item in match_data] if match_data else []

        elif re.search(template_regex, json_path_string):
            matches = re.findall(template_regex, json_path_string)
            for match in matches:
                match_data = parse(match.lstrip('{').rstrip('}')).find(event)
                if match_data:
                    json_path_string = json_path_string.replace(match, match_data[0].value)
            return json_path_string

        return json_path_string

    def __resolve_config_object(self, event, config):
        """
        * Recursive helper for resolveConfigTemplates
        *
        * Given a config object containing possible JSONPath-templated values, resolves
        * all the values in the object using JSONPaths into the provided event.
        *
        * @param {*} event The event that paths resolve against
        * @param {*} config A config object, containing paths
        * @returns {*} A config object with all JSONPaths resolved
        """

        if isinstance(config, str):
            return self.__resolve_path_str(event, config)

        if isinstance(config, list):
            for i in range(0, len(config)):  # pylint: disable=consider-using-enumerate
                config[i] = self.__resolve_config_object(event, config[i])
            return config

        elif (config is not None and isinstance(config, dict)):
            result = {}
            for key in config.keys():
                result[key] = self.__resolve_config_object(event, config[key])
            return result

        return config

    def __resolve_config_templates(self, event, config):
        """
        * Given a config object containing possible JSONPath-templated values, resolves
        * all the values in the object using JSONPaths into the provided event.
        *
        * @param {*} event The event that paths resolve against
        * @param {*} config A config object, containing paths
        * @returns {*} A config object with all JSONPaths resolved
        """
        task_config = config.copy()
        if 'cumulus_message' in task_config:
            del task_config['cumulus_message']
        return self.__resolve_config_object(event, task_config)

    # Payload determination
    def __resolve_input(self, event, config):
        """
        * Given a Cumulus message and its config, returns the input object to send to the
        * task, as defined under config.cumulus_message
        * @param {*} event The Cumulus message
        * @param {*} config The config object
        * @returns {*} The object to place on the input key of the task's event
        """
        if ('cumulus_message' in config and 'input' in config['cumulus_message']):
            input_path = config['cumulus_message']['input']
            return self.__resolve_path_str(event, input_path)
        return event.get('payload')

    def load_nested_event(self, event, context):
        """
        * Interprets an incoming event as a Cumulus workflow message
        *
        * @param {*} event The input message sent to the Lambda
        * @returns {*} message that is ready to pass to an inner task
        """
        config = self.__load_config(event, context)
        final_config = self.__resolve_config_templates(event, config)
        final_payload = self.__resolve_input(event, config)
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

    #############################
    # Output message creation   #
    #############################

    def __assign_json_path_value(self, message, jspath, value):
        """
        * Assign (update or insert) a value to message based on jsonpath.
        * Create the keys if jspath doesn't already exist in the message. In this case, we
        * support 'simple' jsonpath like $.path1.path2.path3....
        * @param {*} message The message to be update
        * @return {*} updated message
        """
        if not parse(jspath).find(message):
            paths = jspath.lstrip('$.').split('.')
            current_item = message
            key_not_found = False
            for path in paths:
                if key_not_found or path not in current_item:
                    key_not_found = True
                    new_path_dict = {}
                    # Add missing key to existing dict
                    current_item[path] = new_path_dict
                    # Set current item to newly created dict
                    current_item = new_path_dict
                else:
                    current_item = current_item[path]
        parse(jspath).update(message, value)
        return message

    def __assign_outputs(self, handler_response, event, message_config):
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
                value = self.__resolve_path_str(handler_response, source_path)
                self.__assign_json_path_value(result, dest_json_path, value)
        else:
            result['payload'] = handler_response

        return result

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

        source_path = replace_config['Path']
        target_path = replace_config.get('TargetPath', replace_config['Path'])
        max_size = replace_config.get('MaxSize', self.REMOTE_DEFAULT_MAX_SIZE)

        for key in self.CMA_CONFIG_KEYS:
            if event.get(key):
                del event[key]

        cumulus_meta = deepcopy(event['cumulus_meta'])
        parsed_json_path = parse(source_path)
        replacement_data = parsed_json_path.find(event)
        if len(replacement_data) != 1:
            raise Exception(f'JSON path invalid: {parsed_json_path}')
        replacement_data = replacement_data[0]

        estimated_data_size = len(json.dumps(replacement_data.value))
        if sys.version_info.major > 3:
            estimated_data_size = len(json.dumps(replacement_data.value).encode(('utf-8')))

        if estimated_data_size < max_size:
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
            parsed_json_path.update(event, '')

        remote_configuration = {'Bucket': s3_bucket, 'Key': s3_key,
                                'TargetPath': target_path}
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
