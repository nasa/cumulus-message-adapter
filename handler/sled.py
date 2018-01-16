from os import path
import json
from jsonschema import validate

def sled_handler(event, context, handler_fn, handler_config):
    """
    Interprets incoming messages, passes them to an inner handler, gets the response
    and transforms it into an outgoing message, returned by Lambda.
    """
    
    # task triggered:
    # use handler_config or get config via read_json_file cumulus.json
    config = handler_config if handler_config else read_json_file('cumulus.json')
    task_config = config.task

    # TODO: message.load_remote_event
    # TODO: message.load_nested_event

    schemas = task_config.schemas;

    # validate_json_document event.input schemas.input
    if (schemas and schemas.input)
        validate_json_document(event.input, schemas.input)

    # validate_json_document event.config schemas.configs
    if (schemas and schemas.config)
        validate_json_document(event.config, schemas.config)

    # handler_fn, event, context
    handler_response = handler_fn(event, context)

    # validate_json_document handler_response schemas.output
    if (schemas and schemas.output)
        validate_json_document(handler_response, schemas.output)

    # TODO: return message.create_next_event


def task_path(relative_filepath):
    return path.join(path.dirname, '..', relative_filepath)

def read_json_file(relative_filepath):
    filepath = task_path(relative_filepath);
    return json.load(open(filepath))

# TODO: double check that validate raises an exception as needed
def validate_json_document(document, schema_filepath):
    schema = read_json_file(schema_filepath)
    return validate(document, schema)
