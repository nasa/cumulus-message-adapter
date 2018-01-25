import unittest
from os import path
from handler.handler import handler

def create_event ():
    return {
      "workflow_config": {
        "Example": {
            "foo": "wut",
            "cumulus_message": {}
        }
      },
      "cumulus_meta": {
        "task": "Example",
        "message_source": "local",
        "id": "id-1234"
      },
      "meta": { "foo": "bar" },
      "payload": { "anykey": "anyvalue" }
    }

def create_handler_config():
    return {
        "task": {
            "root": path.join(path.dirname(path.realpath(__file__)), "fixtures"),
            "schemas": {
                "input": "schemas/input.json",
                "config": "schemas/config.json",
                "output": "schemas/output.json"
            }
        }
    }

class TestSledHandler(unittest.TestCase):

    def test_simple_handler(self):
        def handler_fn(event, context):
            return event

        handler_config = create_handler_config()
        test_event = create_event()
        response = handler(test_event, {}, handler_fn, handler_config) 

        self.assertTrue(response['cumulus_meta']['task'] == 'Example')
        self.assertTrue(response['payload']['input']['anykey'] == 'anyvalue')
        self.assertTrue(response)
