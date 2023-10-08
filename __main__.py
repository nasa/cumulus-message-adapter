#!/usr/bin/env python
# coding=utf-8
import json
import sys
import signal


class MessageProcessor:
    def __init__(self, schemas=None):
        self.schemas = schemas

    def load_and_update_remote_event(self, event, context):
        """Load and update a remote event."""
        if context:
            result = f"Loaded and updated: {event} with context {context}"
        else:
            result = f"Loaded and updated: {event} without context"
        return {"result": result}

    def load_nested_event(self, event):
        """Load a nested event."""
        nested_data = event.get("nested_data", "Default value if key not found")
        return {"nested_data": nested_data}

    def create_next_event(self, handler_response, event, message_config=None):
        """Create the next event based on the handler response and current event."""
        result = {"handler_response": handler_response, "event": event}
        if message_config:
            result["message_config_applied"] = True
        return result


def call_message_processor_function(function_name, all_input, processor):
    """
    CLI helper method to handle 'single command' calls to MessageProcessor methods

    Parameters:
    function_name (str): Name of the method to run
    all_input (dict): Dict object representing a parsed cumulus message
    processor (MessageProcessor): An instance of MessageProcessor

    Returns:
    dict: JSON response to pass to the next event
    """
    method = getattr(processor, function_name, None)
    if method is None or not callable(method):
        raise ValueError(f"Invalid method name: {function_name}")

    return method(all_input['event'], all_input.get('context'), all_input.get('message_config'))


def handle_exit(_signum, _frame):
    """Method that explicitly flushes stderr/stdout before exiting with code 1"""
    sys.stdout.flush()
    sys.stderr.flush()
    sys.exit(1)


def stream_commands(processor):
    """
    Method that runs and reads messages on STDIN in the format:

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

    while cont:
        next_line = sys.stdin.readline().rstrip('\n')
        if next_line == '<EXIT>':
            cont = False
        elif next_line == '<EOC>':
            json_obj = json.loads(buffer)
            result = call_message_processor_function(command, json_obj, processor)
            sys.stdout.write(json.dumps(result) + "\n<EOC>\n")
            sys.stdout.flush()
            buffer = ''
            command = ''
        else:
            if not command:
                command = next_line.strip()
                sys.stderr.write(f'Warning: Setting command to {command}\n')
            else:
                buffer += next_line


def single_command(function_name, processor):
    """Executes a single MessageProcessor method"""
    all_input = json.loads(input())
    result = call_message_processor_function(function_name, all_input, processor)
    if result and len(result) > 0:
        sys.stdout.write(json.dumps(result))
        sys.stdout.flush()


def cma_cli():
    """
    Top-level CMA CLI method, calls correct stream/single command run mode, handles errors
    """
    exit_code = 1
    try:
        if len(sys.argv) < 2:
            raise ValueError("Function name not provided. Usage: script.py <function_name>")

        function_name = sys.argv[1]
        processor = MessageProcessor()
        signal.signal(signal.SIGINT, handle_exit)
        signal.signal(signal.SIGTERM, handle_exit)

        if function_name == 'stream':
            stream_commands(processor)
            exit_code = 0
        else:
            single_command(function_name, processor)
            exit_code = 0

    except ValueError as ve:
        sys.stderr.write(f"ValueError: {ve}\n")
    except Exception as e:  # pylint: disable=broad-except
        sys.stderr.write(f'Unexpected Error {type(e)}. {e}\n')
    sys.exit(exit_code)


if __name__ == '__main__':
    cma_cli()
