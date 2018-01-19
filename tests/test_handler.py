import unittest
from os import path
from cumulus_sled.handler import handler

def create_event ():
    return {
      "workflow_config": {},
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
            "root": path.join(path.realpath(__file__), "fixtures"),
            "entrypoint": "fixtures.handler",
            "schemas": {
                "input": "schemas/input.json",
                "config": "schemas/config.json",
                "output": "schemas/output.json"
            }
        }
     }

    handler(event, {}, handler_fn, handler_config) 

class TestSledHandler(unittest.TestCase):

    def test_working(self):
        def test_fn(event, context):
            return event

        response = run_test_handler(create_event(), test_fn)
        print response
        self.assertTrue(response)

if __name__ == "__main__":
    unittest.main()
