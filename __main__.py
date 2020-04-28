#!/usr/bin/env python
# coding=utf-8
import json
import sys

from message_adapter.message_adapter import MessageAdapter


def callMessageAdapterFunction(functionName, allInput):
    if 'schemas' in allInput:
        schemas = allInput['schemas']
    else:
        schemas = None
    transformer = MessageAdapter(schemas)
    event = allInput['event']
    context = allInput.get('context')
    if functionName == 'loadAndUpdateRemoteEvent':
        result = transformer.load_and_update_remote_event(event, context)
    elif functionName == 'loadNestedEvent':
        result = transformer.load_nested_event(event, context)
    elif functionName == 'createNextEvent':
        handlerResponse = allInput['handler_response']
        if 'message_config' in allInput:
            messageConfig = allInput['message_config']
        else:
            messageConfig = None
        result = transformer.create_next_event(handlerResponse, event, messageConfig)
    return result


def streamCommands():
    cont = True
    buffer = ""
    command = ""
    jsonObj = {}
    while cont:
        next_line = sys.stdin.readline().rstrip('\n')
        if next_line == '<EOC>':
            sys.stderr.write('\nBUFFER:' + buffer)
            sys.stderr.write('\n')
            sys.stderr.flush()
            jsonObj = json.loads(buffer)
            result = callMessageAdapterFunction(command, jsonObj)
            sys.stdout.write(json.dumps(result) + "\n")
            sys.stdout.write('<EOC>\n')
            sys.stdout.flush()
            buffer = ""
            command = ""
        else:
            if not command:
                command = next_line.strip()
                sys.stderr.write(f'warning setting command to {command}\n')
            else:
                buffer += next_line
        if next_line == '<EXIT>':
            cont = False


def singleCommand(functionName):
    allInput = json.loads(input())
    return callMessageAdapterFunction(functionName, allInput)


def cmaCli():
    exitCode = 1
    functionName = sys.argv[1]
    try:
        if functionName == 'stream':
            streamCommands()
            exitCode = 0
        else:
            result = singleCommand(functionName)
            if (result is not None and len(result) > 0):
                sys.stdout.write(json.dumps(result))
                sys.stdout.flush()
                exitCode = 0

    except LookupError as le:
        sys.stderr.write("Lookup error: " + str(le))
    except Exception:  # pylint: disable=broad-except
        sys.stderr.write(f'Unexpected Error {str(sys.exc_info()[0])}. {str(sys.exc_info()[1])}')
    sys.exit(exitCode)

if __name__ == '__main__':
    cmaCli()
