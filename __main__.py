#!/usr/bin/env python
# coding=utf-8
import json
import sys
import signal
from typing import Any, Dict, cast
from message_adapter.message_adapter import MessageAdapter
from message_adapter.types import CumulusMessage, CumulusMessage, AllInput


def callMessageAdapterFunction(functionName: str, allInput: AllInput) -> CumulusMessage:
    """
    CLI helper method to handle 'single command' calls to CMA 'steps'

    Parameters:
    functionName(string): CMA function to run (one of loadAndUpdateRemoteEvent, loadNestedEvent
                          and createNextEvent
    input(dict):          Dict object representing a parsed cumulus message

    Returns:
    result: JSON response to pass to the next event
    """
    schemas = allInput.get('schemas', None)
    transformer = MessageAdapter(schemas)
    event: CumulusMessage = allInput['event']
    context = allInput.get('context', None)
    #whatif bad function name? this will raise an error around result not functionName
    result: CumulusMessage
    if functionName == 'loadAndUpdateRemoteEvent':
        result = transformer.load_and_update_remote_event(event, context)
    elif functionName == 'loadNestedEvent':
        result = transformer.load_nested_event(event)
    elif functionName == 'createNextEvent':
        handlerResponse = allInput['handler_response']
        if 'message_config' in allInput:
            messageConfig = allInput['message_config']
        else:
            messageConfig = None
        result = transformer.create_next_event(handlerResponse, event, messageConfig)
    return result

def handle_exit() -> None:
    """ Method that explicitly flushes stderr/stdout before exiting 1"""
    sys.stdout.flush()
    sys.stderr.flush()
    sys.exit(1)

def streamCommands() -> None:
    """
    Method that runs, and reads messages on STDIN in the format:

    FunctionName
    JSON string
    <EOC>

    Method writes responses back to STDOUT in the following format:

    JSON string
    <EOC>

    A single line "<EXIT>" input will cause the program to exit
    """

    cont = True
    buffer = ''
    command = ''
    jsonObj = {}

    while cont:
        next_line = sys.stdin.readline().rstrip('\n')
        if next_line == '<EXIT>':
            cont = False
        elif next_line == '<EOC>':
            jsonObj = json.loads(buffer)
            result = callMessageAdapterFunction(command, cast(AllInput, jsonObj))
            sys.stdout.write(json.dumps(result) + "\n")
            sys.stdout.write('<EOC>\n')
            sys.stdout.flush()
            buffer = ''
            command = ''
        else:
            if not command:
                command = next_line.strip()
                sys.stderr.write(f'warning setting command to {command}\n')
            else:
                buffer += next_line


def singleCommand(functionName: str) -> CumulusMessage:
    """Executes a single CMA command"""
    allInput = json.loads(input())
    return callMessageAdapterFunction(functionName, cast(AllInput, allInput))


def cmaCli() -> None:
    """
    Top level CMA cli method, calls correct stream/single command run mode, handles errors
    """
    exitCode = 1
    functionName = sys.argv[1]
    signal.signal(signal.SIGINT, handle_exit)  # type: ignore
    signal.signal(signal.SIGTERM, handle_exit)  # type: ignore

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
