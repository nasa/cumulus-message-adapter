"""
Interprets incoming messages, passes them to an inner handler, gets the response
and transforms it into an outgoing message, returned by Lambda.
"""

from os import path
import json
from jsonschema import validate

import message

def sled_handler(event, context, handler_fn=None, handler_config=None):
    """
    Interprets incoming messages, passes them to an inner handler, gets the response
    and transforms it into an outgoing message, returned by Lambda.

    Arguments:
        event -- aws lambda event object
        context -- aws lambda context object
        handler_fn -- the handler function for the task
        handler_config -- configuration for the handler function
    """

    # instantiate message parser
    msg = message()

    # use handler_config or get config via read_json_file cumulus.json
    config = handler_config if handler_fn else read_json_file('cumulus.json')

    # in the node.js handler task_root is attached to module.exports
    # for now i'm passing it in as config
    task_root = config.task.root
    schemas = config.task.schemas

    def task_path(relative_filepath):
        """
        get absolute path of file in task
        """
        print path.join(task_root, relative_filepath)
        return path.join(task_root, relative_filepath)

    def read_json_file(relative_filepath):
        """
        read a json file given a filepath relative to a task
        """
        filepath = task_path(relative_filepath)
        return json.load(open(filepath))

    def validate_json_document(document, schema_filepath):
        """
        check that json is valid based on a schema
        """
        schema = read_json_file(schema_filepath)
        return validate(document, schema)

    # TODO: finish implementation
    # def get_nested_handler(handler_string):
    #     parts = handler_string.split('.')
    #     module_name = parts[0]
    #     handler_name = parts[1]

    full_event = msg.loadRemoteEvent(event)
    nested_event = msg.loadNestedEvent(full_event, context)
    message_config = nested_event.message_config

    # validate the input
    if (schemas and schemas.input):
        validate_json_document(event.input, schemas.input)

    # validate the config
    if (schemas and schemas.config):
        validate_json_document(event.config, schemas.config)

    # call the handler function
    # TODO: this doesn't handle calling a function dynamically yet
    # only a function that's passed to this one
    handler_response = handler_fn(nested_event, context)

    # validate the output
    if (schemas and schemas.output):
        validate_json_document(handler_response, schemas.output)

    return msg.createNextEvent(handler_response, full_event, message_config)
