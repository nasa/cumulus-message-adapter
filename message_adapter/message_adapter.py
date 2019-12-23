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

class message_adapter:
    """
    transforms the cumulus message
    """
    REMOTE_DEFAULT_MAX_SIZE = 0
    CMA_CONFIG_KEYS = ['ReplaceConfig', 'task_config']

    def __init__(self, schemas=None):
        self.schemas = schemas

    def __getSfnExecutionArnByName(self, stateMachineArn, executionName):
        """
        * Given a state machine arn and execution name, returns the execution's ARN
        * @param {string} stateMachineArn The ARN of the state machine containing the execution
        * @param {string} executionName The name of the execution
        * @returns {string} The execution's ARN
        """
        return (':').join([stateMachineArn.replace(':stateMachine:', ':execution:'), executionName])

    def __getTaskNameFromExecutionHistory(self, executionHistory, arn):
        """
        * Given an execution history object returned by the StepFunctions API and an optional Activity
        * or Lambda ARN returns the most recent task name started for the given ARN, or if no ARN is
        * supplied, the most recent task started.
        *
        * IMPORTANT! If no ARN is supplied, this message assumes that the most recently started execution
        * is the desired execution. This WILL BREAK parallel executions, so always supply this if possible.
        *
        * @param {dict} executionHistory The execution history returned by getExecutionHistory, assumed
        *                             to be sorted so most recent executions come last
        * @param {string} arn An ARN to an Activity or Lambda to find. See "IMPORTANT!"
        * @throws If no matching task is found
        * @returns {string} The matching task name
        """
        eventsById = {}

        # Create a lookup table for finding events by their id
        for event in executionHistory['events']:
            eventsById[event['id']] = event

        for step in executionHistory['events']:
            # Find the ARN in thie history (the API is awful here).  When found, return its
            # previousEventId's (TaskStateEntered) name
            if (arn is not None and
                    ((step['type'] == 'LambdaFunctionScheduled' and
                      step['lambdaFunctionScheduledEventDetails']['resource'] == arn) or
                     (step['type'] == 'ActivityScheduled' and
                      step['activityScheduledEventDetails']['resource'] == arn)) and
                    'stateEnteredEventDetails' in eventsById[step['previousEventId']]):
                return eventsById[step['previousEventId']]['stateEnteredEventDetails']['name']
            elif step['type'] == 'TaskStateEntered':
                return step['stateEnteredEventDetails']['name']
        raise LookupError('No task found for ' + arn)

    def __getCurrentSfnTask(self, stateMachineArn, executionName, arn):
        """
        * Given a state machine ARN, an execution name, and an optional Activity or Lambda ARN returns
        * the most recent task name started for the given ARN in that execution, or if no ARN is
        * supplied, the most recent task started.
        *
        * IMPORTANT! If no ARN is supplied, this message assumes that the most recently started execution
        * is the desired execution. This WILL BREAK parallel executions, so always supply this if possible.
        *
        * @param {string} stateMachineArn The ARN of the state machine containing the execution
        * @param {string} executionName The name of the step function execution to look up
        * @param {string} arn An ARN to an Activity or Lambda to find. See "IMPORTANT!"
        * @returns {string} The name of the task being run
        """
        sfn = stepFn()
        executionArn = self.__getSfnExecutionArnByName(stateMachineArn, executionName)
        executionHistory = sfn.get_execution_history(
            executionArn=executionArn,
            maxResults=40,
            reverseOrder=True
        )
        return self.__getTaskNameFromExecutionHistory(executionHistory, arn)

    ##################################
    #  Input message interpretation  #
    ##################################

    def __parseParameterConfiguration(self, event):
        parsed_event = event
        if event.get('cma'):
            updated_event = {k:v for (k,v) in event['cma'].items() if k != 'event'}
            parsed_event = event['cma']['event']
            parsed_event.update(updated_event)
        return parsed_event


    def __loadRemoteEvent(self, event):
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
                    raise Exception('Remote event configuration target {} invalid'.format(target_json_path))
                try:
                    replacement_targets[0].value.update(remote_event)
                except AttributeError:
                    parsed_json_path.update(event, remote_event)

                event.pop('replace')
                if (local_exception and local_exception != 'None') and (not event['exception'] or event['exception'] == 'None'):
                    event['exception'] = local_exception
        return event

    def loadAndUpdateRemoteEvent(self, incoming_event, context):
        """
        * Looks at a Cumulus message. If the message has part of its data stored remotely in
        * S3, fetches that data, otherwise it returns the full message, both cases updated with task metadata.
        * If event uses parameterized configuration, converts message into a
        * Cumulus message and ensures that incoming parameter keys are not overridden
        * @param {*} event The input Lambda event in the Cumulus message protocol
        * @returns {*} the full event data
        """
        event = deepcopy(incoming_event)

        if incoming_event.get('cma'):
            cmaEvent = deepcopy(incoming_event)
            event = self.__loadRemoteEvent(event['cma'].get('event'))
            cmaEvent['cma']['event'].update(event)
            event = self.__parseParameterConfiguration(cmaEvent)
        else:
            event = self.__loadRemoteEvent(event)

        if context and 'meta' in event and 'workflow_tasks' in event['meta']:
            cumulus_meta = event['cumulus_meta']
            taskMeta = {}
            taskMeta['name'] = context.get('function_name', context.get('functionName'))
            taskMeta['version'] = context.get('function_version', context.get('functionVersion'))
            taskMeta['arn'] = context.get('invoked_function_arn', context.get('invokedFunctionArn', context.get('activityArn')))
            taskName = self.__getCurrentSfnTask(cumulus_meta['state_machine'], cumulus_meta['execution_name'], taskMeta['arn'])
            event['meta']['workflow_tasks'][taskName] = taskMeta
        return event

    # Loading task configuration from workload template

    def __getConfig(self, event, taskName):
        """
        * Returns the configuration for the task with the given name, or an empty object if no
        * such task is configured.
        * @param {*} event An event in the Cumulus message format with remote parts resolved
        * @param {*} taskName The name of the Cumulus task
        * @returns {*} The configuration object
        """
        config = {}
        if ('workflow_config' in event and taskName in event['workflow_config']):
            config = event['workflow_config'][taskName]
        return config

    def __loadStepFunctionTaskName(self, event, context):
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
        return self.__getCurrentSfnTask(meta['state_machine'], meta['execution_name'], arn)

    def __loadConfig(self, event, context):
        """
        * Given a Cumulus message and context, returns the config object for the task
        * @param {*} event An event in the Cumulus message format with remote parts resolved
        * @param {*} context The context object passed to AWS Lambda or containing an activityArn
        * @returns {*} The task's configuration
        """
        if ('task_config' in event):
            return event['task_config']
        # Maintained for backwards compatibility
        source = event['cumulus_meta']['message_source']
        if (source is None):
            raise LookupError('cumulus_meta requires a message_source')
        elif (source == 'local'):
            taskName = event['cumulus_meta']['task']
        elif (source == 'sfn'):
            taskName = self.__loadStepFunctionTaskName(event, context)
        else:
            raise LookupError('Unknown event source: ' + source)
        return self.__getConfig(event, taskName) if taskName is not None else None

    def __get_jsonschema(self, schema_type):
        schemas = self.schemas
        root_dir = os.environ.get("LAMBDA_TASK_ROOT", '')
        has_schema = schemas and schemas.get(schema_type)
        rel_filepath = schemas.get(schema_type) if has_schema else 'schemas/{}.json'.format(schema_type)
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
            except Exception as e:
                e.message = '{} schema: {}'.format(schema_type, e.message)
                raise e

    # Config templating
    def __resolvePathStr(self, event, jsonPathString):
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
        * @param {*} jsonPathString A string containing a JSONPath template to resolve
        * @returns {*} The resolved object
        """
        valueRegex = r"^{[^\[\]].*}$"
        arrayRegex = r"^{\[.*\]}$"
        templateRegex = '{[^}]+}'

        if re.search(valueRegex, jsonPathString):
            matchData = parse(jsonPathString.lstrip('{').rstrip('}')).find(event)
            return matchData[0].value if matchData else None

        elif re.search(arrayRegex, jsonPathString):
            parsedJsonPath = jsonPathString.lstrip('{').rstrip('}').lstrip('[').rstrip(']');
            matchData = parse(parsedJsonPath).find(event)
            return [item.value for item in matchData] if matchData else []

        elif re.search(templateRegex, jsonPathString):
            matches = re.findall(templateRegex, jsonPathString)
            for match in matches:
                matchData = parse(match.lstrip('{').rstrip('}')).find(event)
                if matchData:
                    jsonPathString = jsonPathString.replace(match, matchData[0].value)
            return jsonPathString

        return jsonPathString

    def __resolveConfigObject(self, event, config):
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
        try:
            unicode
        except NameError:
            if isinstance(config, str):
                return self.__resolvePathStr(event, config)
        else:
            if isinstance(config, unicode):
                return self.__resolvePathStr(event, config)

        if isinstance(config, list):
            for i in range(0, len(config)):
                config[i] = self.__resolveConfigObject(event, config[i])
            return config

        elif (config is not None and isinstance(config, dict)):
            result = {}
            for key in config.keys():
                result[key] = self.__resolveConfigObject(event, config[key])
            return result

        return config

    def __resolveConfigTemplates(self, event, config):
        """
        * Given a config object containing possible JSONPath-templated values, resolves
        * all the values in the object using JSONPaths into the provided event.
        *
        * @param {*} event The event that paths resolve against
        * @param {*} config A config object, containing paths
        * @returns {*} A config object with all JSONPaths resolved
        """
        taskConfig = config.copy()
        if 'cumulus_message' in taskConfig:
            del taskConfig['cumulus_message']
        return self.__resolveConfigObject(event, taskConfig)

    # Payload determination
    def __resolveInput(self, event, config):
        """
        * Given a Cumulus message and its config, returns the input object to send to the
        * task, as defined under config.cumulus_message
        * @param {*} event The Cumulus message
        * @param {*} config The config object
        * @returns {*} The object to place on the input key of the task's event
        """
        if ('cumulus_message' in config and 'input' in config['cumulus_message']):
            inputPath = config['cumulus_message']['input']
            return self.__resolvePathStr(event, inputPath)
        return event.get('payload')

    def loadNestedEvent(self, event, context):
        """
        * Interprets an incoming event as a Cumulus workflow message
        *
        * @param {*} event The input message sent to the Lambda
        * @returns {*} message that is ready to pass to an inner task
        """
        config = self.__loadConfig(event, context)
        finalConfig = self.__resolveConfigTemplates(event, config)
        finalPayload = self.__resolveInput(event, config)
        response = {'input': finalPayload}
        self.__validate_json(finalPayload, 'input')
        self.__validate_json(finalConfig, 'config')
        if finalConfig is not None:
            response['config'] = finalConfig
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
                response['cumulus_config']['cumulus_context'] = event['cumulus_meta']['cumulus_context']

            if not response['cumulus_config']:
                del response['cumulus_config']

        return response

    #############################
    # Output message creation   #
    #############################

    def __assignJsonPathValue(self, message, jspath, value):
        """
        * Assign (update or insert) a value to message based on jsonpath.
        * Create the keys if jspath doesn't already exist in the message. In this case, we
        * support 'simple' jsonpath like $.path1.path2.path3....
        * @param {*} message The message to be update
        * @return {*} updated message
        """
        if not parse(jspath).find(message):
            paths = jspath.lstrip('$.').split('.')
            currentItem = message
            keyNotFound = False
            for path in paths:
                if keyNotFound or path not in currentItem:
                    keyNotFound = True
                    newPathDict = {}
                    # Add missing key to existing dict
                    currentItem[path] = newPathDict
                    # Set current item to newly created dict
                    currentItem = newPathDict
                else:
                    currentItem = currentItem[path]
        parse(jspath).update(message, value)
        return message

    def __assignOutputs(self, handlerResponse, event, messageConfig):
        """
        * Applies a task's return value to an output message as defined in config.cumulus_message
        *
        * @param {*} handlerResponse The task's return value
        * @param {*} event The output message to apply the return value to
        * @param {*} messageConfig The cumulus_message configuration
        * @returns {*} The output message with the nested response applied
        """
        result = deepcopy(event)
        if messageConfig is not None and 'outputs' in messageConfig:
            outputs = messageConfig['outputs']
            result['payload'] = {}
            for output in outputs:
                sourcePath = output['source']
                destPath = output['destination']
                destJsonPath = destPath.lstrip('{').rstrip('}')
                value = self.__resolvePathStr(handlerResponse, sourcePath)
                self.__assignJsonPathValue(result, destJsonPath, value)
        else:
            result['payload'] = handlerResponse

        return result

    def __storeRemoteResponse(self, incoming_event):
        """
        * Stores part of a response message in S3 if it is too big to send to StepFunctions
        * @param {*} event The response message
        * @returns {*} A response message, possibly referencing an S3 object for its contents
        """
        event = deepcopy(incoming_event)
        replace_config = event.get('ReplaceConfig', None)
        if not (replace_config):
            return event

        # Set default value if FullMessage flag set
        if replace_config.get('FullMessage', False):
            replace_config['Path'] = '$'

        source_path = replace_config['Path']
        target_path = replace_config.get('TargetPath', replace_config['Path'])
        max_size = replace_config.get('MaxSize', self.REMOTE_DEFAULT_MAX_SIZE)

        [event.pop(key) for key in self.CMA_CONFIG_KEYS if event.get(key)]

        cumulus_meta = deepcopy(event['cumulus_meta'])
        parsed_json_path = parse(source_path)
        replacement_data = parsed_json_path.find(event)
        if len(replacement_data) != 1:
            raise Exception('JSON path invalid: {}'.format(parsed_json_path))
        replacement_data = replacement_data[0]

        estimated_data_size = len(json.dumps(replacement_data.value))
        if sys.version_info.major > 3:
            estimated_data_size = len(json.dumps(replacement_data.value).encode(('utf-8')))

        if estimated_data_size < max_size:
            return event

        _s3 = s3()
        s3Bucket = event['cumulus_meta']['system_bucket']
        s3Key = ('/').join(['events', str(uuid.uuid4())])
        s3Params = {
            'Expires': datetime.utcnow() + timedelta(days=7),  # Expire in a week
            'Body': json.dumps(replacement_data.value)
        }
        _s3.Object(s3Bucket, s3Key).put(**s3Params)

        try:
            replacement_data.value.clear()
        except AttributeError:
            parsed_json_path.update(event, '')

        remoteConfiguration = {'Bucket': s3Bucket, 'Key': s3Key,
                               'TargetPath': target_path}
        event['cumulus_meta'] = event.get('cumulus_meta', cumulus_meta)
        event['replace'] = remoteConfiguration
        return event

    def createNextEvent(self, handlerResponse, event, messageConfig):
        """
        * Creates the output message returned by a task
        *
        * @param {*} handlerResponse The response returned by the inner task code
        * @param {*} event The input message sent to the Lambda
        * @param {*} messageConfig The cumulus_message object configured for the task
        * @returns {*} the output message to be returned
        """
        self.__validate_json(handlerResponse, 'output')

        result = self.__assignOutputs(handlerResponse, event, messageConfig)
        if not result.get('exception'):
            result['exception'] = 'None'
        if 'replace' in result:
            del result['replace']
        return self.__storeRemoteResponse(result)
