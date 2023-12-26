import json
import re
import uuid

from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any, Dict, Union, List, Literal, Optional, Tuple, cast
from jsonpath_ng import parse
from jsonpath_ng import JSONPath
from .aws import s3
from .error import write_error
from .types import (
    CumulusMessage, CumulusTaskConfig, ReplacementConfig,
    GenericCumulusObject, GenericCumulusSubObject
)



def load_config(event: Union[GenericCumulusObject, CumulusMessage]) -> CumulusTaskConfig:
    """
    * Given a Cumulus message and context, returns the config object for the task
    * @param {*} event An event in the Cumulus message format with remote parts resolved
    * @param {*} context The context object passed to AWS Lambda or containing an activityArn
    * @returns {*} The task's configuration
    """
    write_error('Starting load_config')
    # this needs validation of a valid config
    if 'task_config' in event:
        return cast(CumulusTaskConfig, event['task_config'])
    return {}


def load_remote_event(event: CumulusMessage) -> CumulusMessage:
    """
    * Given a Cumulus message, checks for a 'replace' key and fetches a remote stored
    * object from S3 and inserts it into the configured path
    * @param {*} event An event in the Cumulus message format
    * @returns {*} A Cumulus message with the remote message resolved
    """
    write_error('Starting load_remote_event')
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
                raise ValueError(
                    f'Remote event configuration target {target_json_path} invalid')
            try:
                replacement_targets[0].value.update(remote_event)
            except AttributeError:
                parsed_json_path.update(event, remote_event)

            event.pop('replace')
            exception_bool = (local_exception and local_exception != 'None')
            if exception_bool and (not event['exception'] or event['exception'] == 'None'):
                event['exception'] = local_exception
    write_error('Ending load_remote_event')
    return event


# Config templating
def resolve_path_str(
    event: Union[GenericCumulusSubObject, CumulusMessage],
    json_path_string: str
) -> GenericCumulusSubObject:
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
    write_error('Starting resolve_path_str')

    value_regex = r"^{[^\[\]].*}$"
    array_regex = r"^{\[.*\]}$"
    template_regex = '{[^}]+}'

    if re.search(value_regex, json_path_string):
        match_data = parse(json_path_string.lstrip(
            '{').rstrip('}')).find(event)
        return match_data[0].value if match_data else None

    if re.search(array_regex, json_path_string):
        parsed_json_path = json_path_string.lstrip(
            '{').rstrip('}').lstrip('[').rstrip(']')
        match_data = parse(parsed_json_path).find(event)
        return [item.value for item in match_data] if match_data else []

    if re.search(template_regex, json_path_string):
        matches = re.findall(template_regex, json_path_string)
        for match in matches:
            match_data = parse(match.lstrip('{').rstrip('}')).find(event)
            if match_data:
                json_path_string = json_path_string.replace(
                    match, match_data[0].value)
        return json_path_string

    write_error('End resolve_path_str')
    return json_path_string


def resolve_input(
    event: Union[GenericCumulusObject, CumulusMessage],
    config: CumulusTaskConfig
) -> Any:
    """
    * Given a Cumulus message and its config, returns the input object to send to the
    * task, as defined under config.cumulus_message
    * @param {*} event The Cumulus message
    * @param {*} config The config object
    * @returns {*} The object to place on the input key of the task's event
    """
    write_error('Starting resolve_input')
    if ('cumulus_message' in config and 'input' in config['cumulus_message']):
        input_path = config['cumulus_message']['input']
        return resolve_path_str(event, input_path)
    write_error('End resolve_input')
    return event.get('payload')


def resolve_config_templates(
    event: Union[GenericCumulusObject, CumulusMessage],
    config: CumulusTaskConfig
) -> CumulusTaskConfig:
    """
    * Given a config object containing possible JSONPath-templated values, resolves
    * all the values in the object using JSONPaths into the provided event.
    *
    * @param {*} event The event that paths resolve against
    * @param {*} config A config object, containing paths
    * @returns {*} A config object with all JSONPaths resolved
    """
    write_error('Starting resolve_config_templates')
    task_config: CumulusTaskConfig = config.copy()
    if 'cumulus_message' in task_config:
        del task_config['cumulus_message']
    write_error('Ending resolve_config_templates')
    return cast(
        CumulusTaskConfig,
        _resolve_config_object(
            cast(GenericCumulusObject, event),
            cast(GenericCumulusObject, task_config)
        )
    )


def store_remote_response(
    incoming_event: CumulusMessage,
    default_max_size: int,
    config_keys: List[Literal[  # weird naming? this is just a list of keys to delete
        "exception",
        "task_config",
        "replace",
        "ReplaceConfig"
    ]]
) -> CumulusMessage:
    """
    * Stores part of a response message in S3 if it is too big to send to StepFunctions
    * @param {*} incoming_event    - The response message
    * @param {*} default_max_size  - The maximum size (in bytes) a response message portion
    *                                can be before the method will store it in s3
    * @param {*} config_keys       - A list of valid CMA configuration keys
    * @returns {*} A response message, possibly referencing an S3 object for its contents
    """
    write_error('Starting store_remote_response')
    event = deepcopy(incoming_event)
    if 'ReplaceConfig' not in event:
        return event

    replace_config: ReplacementConfig = event['ReplaceConfig']
    # Set default value if FullMessage flag set
    if replace_config.get('FullMessage', False):
        replace_config['Path'] = '$'

    target_path, max_size, parsed_json_path = _parse_remote_config_from_event(
        replace_config, default_max_size)

    for key in config_keys:
        if key in event:
            del event[key]

    cumulus_meta = deepcopy(event['cumulus_meta'])
    replacement_data = parsed_json_path.find(event)
    if len(replacement_data) != 1:
        raise ValueError(
            f'JSON path invalid: {parsed_json_path}')
    replacement_data = replacement_data[0]

    estimated_data_size = len(json.dumps(
        replacement_data.value).encode(('utf-8')))

    if estimated_data_size < max_size:
        return event

    s3_bucket: str = event['cumulus_meta']['system_bucket']
    s3_key = ('/').join(['events', str(uuid.uuid4())])
    s3().Object(s3_bucket, s3_key).put(
        Expires=datetime.utcnow() + timedelta(days=7),  # Expire in a week
        Body=json.dumps(replacement_data.value)
    )

    try:
        replacement_data.value.clear()
    except AttributeError:
        parsed_json_path.update(event, '')

    event['cumulus_meta'] = event.get('cumulus_meta', cumulus_meta)
    event['replace'] = {
        'Bucket': s3_bucket,
        'Key': s3_key,
        'TargetPath': target_path
    }
    write_error('store_remote_response')
    return event


def _resolve_config_object(
    event: GenericCumulusSubObject,
    config: Optional[GenericCumulusSubObject]
) -> Optional[GenericCumulusSubObject]:
    """
    * Recursive helper for resolve_config_templates
    *
    * Given a config object containing possible JSONPath-templated values, resolves
    * all the values in the object using JSONPaths into the provided event.
    *
    * @param {*} event The event that paths resolve against
    * @param {*} config A config object, containing paths
    * @returns {*} A config object with all JSONPaths resolved
    """
    if config is None:
        return config

    if isinstance(config, str):
        return resolve_path_str(event, config)

    if isinstance(config, list):
        for i in range(0, len(config)):  # pylint: disable=consider-using-enumerate
            config[i] = _resolve_config_object(event, config[i])
        return config

    if isinstance(config, dict):
        result: Dict[str, Optional[Any]] = {
            key: _resolve_config_object(event, subcfg)
            for key, subcfg in config.items()
        }
        # subCfg: GenericCumulusObject
        # for key, subCfg in config.items():
        #     result[key] = _resolve_config_object(event, subCfg)
        return result

    return config


def _parse_remote_config_from_event(
    replace_config: ReplacementConfig,
    default_max_size: int
) -> Tuple[str, int, JSONPath]:
    source_path = replace_config['Path']
    target_path = replace_config.get('TargetPath', source_path)
    max_size = replace_config.get('MaxSize', default_max_size)
    parsed_json_path: JSONPath = parse(source_path)

    return target_path, max_size, parsed_json_path
