def sled_handler(event, context, handler_fn, handler_config):
    """
    Interprets incoming messages, passes them to an inner handler, gets the response
    and transforms it into an outgoing message, returned by Lambda.
    """

    # task triggered:
    # use handler_config or get config via read_json_file cumulus.json
    # message.load_remote_event
    # message.load_nested_event
    # validate_json_document event.input schemas.input
    # validate_json_document event.config schemas.configs
    # invoke_handler handler_fn, event, context
    
    # handler response:
    # validate_json_document handler_response schemas.output
    # message.create_next_event

    return { "output": "todo" }

def read_json_file(filepath):
    raise Exception('TODO: implement read_json_file')

def validate_json_document(document, schema_filepath):
    raise Exception('TODO: implement validate_json_document')

def invoke_handler(handler, event, context):
    raise Exception('TODO: implement invoke_handler')
