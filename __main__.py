#!/usr/bin/env python
# coding=utf-8
import json
import sys

from message_adapter import message_adapter

if __name__ == '__main__':
    functionName = sys.argv[1]
    allInput = json.loads(input())
    if 'schemas' in allInput:
        schemas = allInput['schemas']
    else:
        schemas = None
    transformer = message_adapter.message_adapter(schemas)
    exitCode = 1
    event = allInput['event']

    try:
        context = allInput.get('context')
        if (functionName == 'loadAndUpdateRemoteEvent'):
            result = transformer.load_and_update_remote_event(event, context)
        elif (functionName == 'loadNestedEvent'):
            result = transformer.load_nested_event(event, context)
        elif (functionName == 'createNextEvent'):
            handlerResponse = allInput['handler_response']
            if 'message_config' in allInput:
                messageConfig = allInput['message_config']
            else:
                messageConfig = None
            result = transformer.create_next_event(handlerResponse, event, messageConfig)
        if (result is not None and len(result) > 0):
            sys.stdout.write(json.dumps(result))
            sys.stdout.flush()
            exitCode = 0
    except LookupError as le:
        sys.stderr.write("Lookup error: " + str(le))
    except Exception:  # pylint: disable=broad-except
        sys.stderr.write(f'Unexpected Error {str(sys.exc_info()[0])}. {str(sys.exc_info()[1])}')
    sys.exit(exitCode)
