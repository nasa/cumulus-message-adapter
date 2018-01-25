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

def run_test_handler(event, handler_fn):
    handler_config = {
        "task": {
            "root": path.join(path.dirname(path.realpath(__file__)), "fixtures"),
            "schemas": {
                "input": "schemas/input.json",
                "config": "schemas/config.json",
                "output": "schemas/output.json"
            }
        }
    }

    return handler(event, {}, handler_fn, handler_config) 

class TestSledHandler(unittest.TestCase):

    def test_simple_handler(self):
        def test_fn(event, context):
            return event

        response = run_test_handler(create_event(), test_fn)
        self.assertTrue(response['cumulus_meta']['task'] == 'Example')
        self.assertTrue(response['payload']['input']['anykey'] == 'anyvalue')
        self.assertTrue(response)

if __name__ == "__main__":
    unittest.main()
