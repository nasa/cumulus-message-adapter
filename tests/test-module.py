"""
Tests for cumulus-message-adapter
"""
import os
import json
import unittest
from mock import patch
from jsonschema.exceptions import ValidationError

from message_adapter import aws, message_adapter

class Test(unittest.TestCase):
    """ Test class """

    s3_object = {'input': ':blue_whale:'}
    bucket_name = 'testing-internal'
    key_name = 'blue_whale-event.json'
    event_with_replace = {'replace': {'Bucket': bucket_name, 'Key': key_name, 'TargetPath': '$'}}
    event_without_replace = {'input': ':baby_whale:'}
    test_uuid = 'aad93279-95d4-4ada-8c43-aa5823f8bbbc'
    next_event_object_key_name = "events/{0}".format(test_uuid)
    s3 = aws.s3()
    cumulus_message_adapter = message_adapter.message_adapter()
    test_folder = os.path.join(os.getcwd(), 'examples/messages')
    context_folder = os.path.join(os.getcwd(), 'examples/contexts')
    schemas_folder = os.path.join(os.getcwd(), 'examples/schemas')
    os.environ["LAMBDA_TASK_ROOT"] = os.path.join(os.getcwd(), 'examples')

    def setUp(self):
        self.nested_response = {
            'input': {
                'dataLocation': 's3://source.jpg'
            }
        }

        self.s3.Bucket(self.bucket_name).create()
        self.s3.Object(self.bucket_name, self.key_name).put(Body=json.dumps(self.s3_object))

    def tearDown(self):
        delete_objects_object = {
            'Objects': [{'Key': self.key_name}, {'Key': self.next_event_object_key_name}]
        }
        self.s3.Bucket(self.bucket_name).delete_objects(Delete=delete_objects_object)
        self.s3.Bucket(self.bucket_name).delete()

    # loadAndUpdateRemoteEvent tests
    def test_returns_remote_s3_object(self):
        """ Test remote s3 event is returned when 'replace' key is present """
        result = self.cumulus_message_adapter.loadRemoteEvent(self.event_with_replace)
        assert result == self.s3_object

    def test_returns_event(self):
        """ Test event argument is returned when 'replace' key is not present """
        result = self.cumulus_message_adapter.loadRemoteEvent(self.event_without_replace)
        assert result == self.event_without_replace

    # loadNestedEvent tests
    def test_returns_loadNestedEvent_local(self):
        """
        Test returns 'config', 'input' and 'messageConfig' in expected format
        - 'input' in return value is from 'payload' in first argument object
        - 'config' in return value is the task ($.cumulus_meta.task) configuration
           with 'cumulus_message' excluded
        - 'messageConfig' in return value is the cumulus_message.input of the task configuration
        """

        nested_event_local = {
            "workflow_config": {
                "Example": {
                    "bar": "baz",
                    "cumulus_message": {
                        "input": "{{$.payload.input}}",
                        "outputs": [{"source": "{{$.input.anykey}}",
                                    "destination": "{{$.payload.out}}"}]
                    }
                }
            },
            "cumulus_meta": {"task": "Example", "message_source": "local", "id": "id-1234"},
            "meta": {"foo": "bar"},
            "payload": {"input": {"anykey": "anyvalue"}}
        }

        nested_event_local_return = {
            'input': {'anykey': 'anyvalue'},
            'config': {'bar': 'baz'},
            'messageConfig': {
                'input': '{{$.payload.input}}',
                'outputs': [{'source': '{{$.input.anykey}}',
                            'destination': '{{$.payload.out}}'}]}
        }

        result = self.cumulus_message_adapter.loadNestedEvent(nested_event_local, {})
        assert result == nested_event_local_return

    # assignOutputs tests
    def test_result_payload_without_config(self):
        """ Test nestedResponse is returned when no config argument is passed """
        result = self.cumulus_message_adapter._message_adapter__assignOutputs( # pylint: disable=no-member
            self.nested_response, {}, None)
        assert result['payload'] == self.nested_response

    def test_result_payload_without_config_outputs(self):
        """ Test nestedResponse is returned when config has no outputs key/value """
        message_config_without_outputs = {}
        result = self.cumulus_message_adapter._message_adapter__assignOutputs( # pylint: disable=no-member
            self.nested_response, {}, message_config_without_outputs)
        assert result['payload'] == self.nested_response

    def test_result_payload_with_simple_config_outputs(self):
        """ Test payload value is updated when messageConfig contains outputs templates """
        # messageConfig objects
        message_config_with_simple_outputs = {
            'outputs': [{
                'source': '{{$.input.dataLocation}}',
                'destination': '{{$.payload}}'
            }]
        }

        result = self.cumulus_message_adapter._message_adapter__assignOutputs( # pylint: disable=no-member
            self.nested_response, {}, message_config_with_simple_outputs)
        assert result['payload'] == 's3://source.jpg'

    def test_result_payload_with_nested_config_outputs(self):
        """
        Test nested payload value is updated when messageConfig contains
        outputs templates with child nodes
        """
        message_config_with_nested_outputs = {
            'outputs': [{
                'source': '{{$.input.dataLocation}}',
                'destination': '{{$.payload.dataLocation}}'
            }]
        }

        result = self.cumulus_message_adapter._message_adapter__assignOutputs( # pylint: disable=no-member
            self.nested_response, {}, message_config_with_nested_outputs)
        assert result['payload'] == {'dataLocation': 's3://source.jpg'}

    # createNextEvent tests
    def test_with_replace(self):
        """
        Test 'replace' key is deleted from value returned from createNextEvent
        """
        result = self.cumulus_message_adapter.createNextEvent(
            self.nested_response, self.event_with_replace, None)
        assert 'replace' not in result

    def test_small_result_returns_event(self):
        """ Test return result is the event result when it's not too big """
        result = self.cumulus_message_adapter.createNextEvent(
            self.nested_response, self.event_without_replace, None)
        expected_result = {
            'input': ':baby_whale:',
            'exception': 'None',
            'payload': {
                'input': {'dataLocation': 's3://source.jpg'}
            }
        }
        assert result == expected_result

    @patch.object(cumulus_message_adapter, 'MAX_NON_S3_PAYLOAD_SIZE', 1)
    @patch('uuid.uuid4')
    def test_big_result_stored_remotely(self, uuid_mock):
        """
        Test remote event is stored in S3 and return value points
        to remote location with 'replace' key/value
        """

        event_with_ingest = {
            'cumulus_meta': {
                'workflow': 'testing',
                "system_bucket": self.bucket_name
            }
        }

        uuid_mock.return_value = self.test_uuid
        create_next_event_result = self.cumulus_message_adapter.createNextEvent(
            self.nested_response, event_with_ingest, None)
        expected_create_next_event_result = {
            'cumulus_meta': {
                'workflow': 'testing',
                'system_bucket': self.bucket_name
            },
            'replace': {'Bucket': self.bucket_name, 'Key': self.next_event_object_key_name}
        }
        remote_event = self.s3.Object(self.bucket_name, self.next_event_object_key_name).get()
        remote_event_object = json.loads(
            remote_event['Body'].read().decode('utf-8'))
        expected_remote_event_object = {
            'cumulus_meta': {
                'workflow': 'testing',
                'system_bucket': self.bucket_name
            },
            'exception': 'None',
            'payload': {'input': {'dataLocation': 's3://source.jpg'}}
        }
        assert remote_event_object == expected_remote_event_object
        assert create_next_event_result == expected_create_next_event_result

    def test_basic(self):
        """ test basic.input.json """
        inp = open(os.path.join(self.test_folder, 'basic.input.json'))
        out = open(os.path.join(self.test_folder, 'basic.output.json'))
        in_msg = json.loads(inp.read())
        out_msg = json.loads(out.read())

        msg = self.cumulus_message_adapter.loadNestedEvent(in_msg, {})
        messageConfig = msg.get('messageConfig')
        if 'messageConfig' in msg: del msg['messageConfig']
        result = self.cumulus_message_adapter.createNextEvent(msg, in_msg, messageConfig)
        assert result == out_msg

    def test_exception(self):
        """ test exception.input.json """
        inp = open(os.path.join(self.test_folder, 'exception.input.json'))
        out = open(os.path.join(self.test_folder, 'exception.output.json'))
        in_msg = json.loads(inp.read())
        out_msg = json.loads(out.read())

        bucket_name = in_msg['replace']['Bucket']
        key_name = in_msg['replace']['Key']
        data_filename = os.path.join(self.test_folder, key_name)
        with open(data_filename, 'r') as f: datasource = json.load(f)
        self.s3.Bucket(bucket_name).create()
        self.s3.Object(bucket_name, key_name).put(Body=json.dumps(datasource))

        remoteEvent = self.cumulus_message_adapter.loadAndUpdateRemoteEvent(in_msg, {})
        msg = self.cumulus_message_adapter.loadNestedEvent(remoteEvent, {})
        messageConfig = msg.get('messageConfig')
        if 'messageConfig' in msg: del msg['messageConfig']
        result = self.cumulus_message_adapter.createNextEvent(msg, remoteEvent, messageConfig)

        delete_objects_object = {'Objects': [{'Key': key_name}]}
        self.s3.Bucket(bucket_name).delete_objects(Delete=delete_objects_object)
        self.s3.Bucket(bucket_name).delete()
        assert result == out_msg

    def test_jsonpath(self):
        """ test jsonpath.input.json """
        inp = open(os.path.join(self.test_folder, 'jsonpath.input.json'))
        out = open(os.path.join(self.test_folder, 'jsonpath.output.json'))
        in_msg = json.loads(inp.read())
        out_msg = json.loads(out.read())

        msg = self.cumulus_message_adapter.loadNestedEvent(in_msg, {})
        messageConfig = msg.get('messageConfig')
        if 'messageConfig' in msg: del msg['messageConfig']
        result = self.cumulus_message_adapter.createNextEvent(msg, in_msg, messageConfig)
        assert result == out_msg

    def test_meta(self):
        """ test meta.input.json """
        inp = open(os.path.join(self.test_folder, 'meta.input.json'))
        out = open(os.path.join(self.test_folder, 'meta.output.json'))
        in_msg = json.loads(inp.read())
        out_msg = json.loads(out.read())

        msg = self.cumulus_message_adapter.loadNestedEvent(in_msg, {})
        messageConfig = msg.get('messageConfig')
        if 'messageConfig' in msg: del msg['messageConfig']
        result = self.cumulus_message_adapter.createNextEvent(msg, in_msg, messageConfig)
        assert result == out_msg

    def test_remote(self):
        """ test remote.input.json """
        inp = open(os.path.join(self.test_folder, 'remote.input.json'))
        out = open(os.path.join(self.test_folder, 'remote.output.json'))
        in_msg = json.loads(inp.read())
        out_msg = json.loads(out.read())

        bucket_name = in_msg['replace']['Bucket']
        key_name = in_msg['replace']['Key']
        data_filename = os.path.join(self.test_folder, key_name)
        with open(data_filename, 'r') as f: datasource = json.load(f)
        self.s3.Bucket(bucket_name).create()
        self.s3.Object(bucket_name, key_name).put(Body=json.dumps(datasource))

        remoteEvent = self.cumulus_message_adapter.loadAndUpdateRemoteEvent(in_msg, {})
        msg = self.cumulus_message_adapter.loadNestedEvent(remoteEvent, {})
        messageConfig = msg.get('messageConfig')
        if 'messageConfig' in msg: del msg['messageConfig']
        result = self.cumulus_message_adapter.createNextEvent(msg, remoteEvent, messageConfig)

        delete_objects_object = {'Objects': [{'Key': key_name}]}
        self.s3.Bucket(bucket_name).delete_objects(Delete=delete_objects_object)
        self.s3.Bucket(bucket_name).delete()

        assert result == out_msg

    @patch.object(cumulus_message_adapter, '_message_adapter__getCurrentSfnTask', return_value="Example")
    def test_sfn(self, getCurrentSfnTask_function):
        """ test sfn.input.json """
        inp = open(os.path.join(self.test_folder, 'sfn.input.json'))
        out = open(os.path.join(self.test_folder, 'sfn.output.json'))
        in_msg = json.loads(inp.read())
        out_msg = json.loads(out.read())

        msg = self.cumulus_message_adapter.loadNestedEvent(in_msg, {})
        messageConfig = msg.get('messageConfig')
        if 'messageConfig' in msg: del msg['messageConfig']
        result = self.cumulus_message_adapter.createNextEvent(msg, in_msg, messageConfig)
        assert result == out_msg

    @patch.object(cumulus_message_adapter, '_message_adapter__getCurrentSfnTask', return_value="Example")
    def test_context(self, getCurrentSfnTask_function):
        """ test storing context metadata """
        inp = open(os.path.join(self.test_folder, 'context.input.json'))
        out = open(os.path.join(self.test_folder, 'context.output.json'))
        ctx = open(os.path.join(self.context_folder, 'lambda-context.json'))
        in_msg = json.loads(inp.read())
        out_msg = json.loads(out.read())
        context = json.loads(ctx.read())

        rem = self.cumulus_message_adapter.loadAndUpdateRemoteEvent(in_msg, context)
        msg = self.cumulus_message_adapter.loadNestedEvent(rem, context)
        messageConfig = msg.get('messageConfig')
        if 'messageConfig' in msg:
            del msg['messageConfig']
        result = self.cumulus_message_adapter.createNextEvent(msg, in_msg, messageConfig)
        assert result == out_msg

    @patch.object(cumulus_message_adapter, '_message_adapter__getCurrentSfnTask', return_value="Example")
    def test_inline_template(self, getCurrentSfnTask_function):
        """ test inline_template.input.json """
        inp = open(os.path.join(self.test_folder, 'inline_template.input.json'))
        out = open(os.path.join(self.test_folder, 'inline_template.output.json'))
        in_msg = json.loads(inp.read())
        out_msg = json.loads(out.read())

        msg = self.cumulus_message_adapter.loadNestedEvent(in_msg, {})
        messageConfig = msg.get('messageConfig');
        if 'messageConfig' in msg: del msg['messageConfig'];
        result = self.cumulus_message_adapter.createNextEvent(msg, in_msg, messageConfig)
        assert result == out_msg

    def test_templates(self):
        """ test templates.input.json """
        inp = open(os.path.join(self.test_folder, 'templates.input.json'))
        out = open(os.path.join(self.test_folder, 'templates.output.json'))
        in_msg = json.loads(inp.read())
        out_msg = json.loads(out.read())

        msg = self.cumulus_message_adapter.loadNestedEvent(in_msg, {})
        messageConfig = msg.get('messageConfig')
        if 'messageConfig' in msg: del msg['messageConfig']
        result = self.cumulus_message_adapter.createNextEvent(msg, in_msg, messageConfig)
        assert result == out_msg

    @patch.object(cumulus_message_adapter, '_message_adapter__getCurrentSfnTask', return_value="Example")
    def test_cumulus_context(self, getCurrentSfnTask_function):
        """ test storing cumulus_context metadata """
        inp = open(os.path.join(self.test_folder, 'cumulus_context.input.json'))
        out = open(os.path.join(self.test_folder, 'cumulus_context.output.json'))
        in_msg = json.loads(inp.read())
        out_msg = json.loads(out.read())

        msg = self.cumulus_message_adapter.loadNestedEvent(in_msg, {})
        messageConfig = msg.get('messageConfig')
        if 'messageConfig' in msg: del msg['messageConfig']
        result = self.cumulus_message_adapter.createNextEvent(msg, in_msg, messageConfig)
        assert result == out_msg

    def test_input_jsonschema(self):
        """ test a working input schema """
        inp = open(os.path.join(self.test_folder, 'templates.input.json'))
        schemas = { 'input': 'input.json' }
        adapter = message_adapter.message_adapter(schemas)
        in_msg = json.loads(inp.read())
        in_msg["payload"]= { "hello": "world" }
        msg = adapter.loadNestedEvent(in_msg, {})
        assert msg["input"]["hello"] == "world"

    def test_failing_input_jsonschema(self):
        """ test a failing input schema """
        inp = open(os.path.join(self.test_folder, 'templates.input.json'))
        schemas = { 'input': 'input.json' }
        adapter = message_adapter.message_adapter(schemas)
        in_msg = json.loads(inp.read())
        in_msg["payload"]= { "hello": 1 }
        try:
            adapter.loadNestedEvent(in_msg, {})
        except ValidationError as e:
            assert e.message == "input schema: 1 is not of type u'string'"
            pass

    def test_config_jsonschema(self):
        """ test a working config schema """
        inp = open(os.path.join(self.test_folder, 'templates.input.json'))
        schemas = { 'config': 'config.json' }
        adapter = message_adapter.message_adapter(schemas)
        in_msg = json.loads(inp.read())
        msg = adapter.loadNestedEvent(in_msg, {})
        assert msg["config"]["inlinestr"] == 'prefixbarsuffix'

    def test_failing_config_jsonschema(self):
        """ test a failing input schema """
        inp = open(os.path.join(self.test_folder, 'templates.input.json'))
        schemas = { 'config': 'config.json' }
        adapter = message_adapter.message_adapter(schemas)
        in_msg = json.loads(inp.read())
        in_msg["workflow_config"]["Example"]["boolean_option"] = '{{$.meta.boolean_option}}'
        in_msg["meta"]["boolean_option"] = "notgoingtowork"
        try:
            adapter.loadNestedEvent(in_msg, {})
        except ValidationError as e:
            assert e.message == "config schema: 'notgoingtowork' is not of type u'boolean'"
            pass

    def test_output_jsonschema(self):
        """ test a working output schema """
        inp = open(os.path.join(self.test_folder, 'templates.input.json'))
        schemas = { 'output': 'output.json' }
        adapter = message_adapter.message_adapter(schemas)
        in_msg = json.loads(inp.read())
        msg = adapter.loadNestedEvent(in_msg, {})
        messageConfig = msg.get('messageConfig')
        handler_response = { "goodbye": "world" }
        result = adapter.createNextEvent(handler_response, in_msg, messageConfig)
        assert result["payload"]["goodbye"] == "world"

    def test_failing_output_jsonschema(self):
        """ test a working output schema """
        inp = open(os.path.join(self.test_folder, 'templates.input.json'))
        schemas = { 'output': 'output.json' }
        adapter = message_adapter.message_adapter(schemas)
        in_msg = json.loads(inp.read())
        msg = adapter.loadNestedEvent(in_msg, {})
        messageConfig = msg.get('messageConfig')
        handler_response = { "goodbye": 1 }
        try:
            adapter.createNextEvent(handler_response, in_msg, messageConfig,)
        except ValidationError as e:
            assert e.message == "output schema: 1 is not of type u'string'"
            pass

