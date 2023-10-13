"""
Tests for cumulus-message-adapter
"""
import os
import json
import unittest
from mock import patch
from jsonschema.exceptions import ValidationError
from message_adapter import aws, message_adapter


class Test(unittest.TestCase):  # pylint: disable=too-many-public-methods
    # pylint: disable=no-member, protected-access
    """ Test class """

    s3_object = {'input': ':blue_whale:'}
    config_s3_object = {'task_config': 'bad value', 'input': ':blue_whale:'}
    bucket_name = 'testing-internal'
    key_name = 'blue_whale-event.json'
    config_key_name = 'cma_config_blue_whale-event.json'
    event_with_cma = {'cma': {'foo': 'bar', 'event': {'some': 'object'}}}
    event_with_replace = {'replace': {'Bucket': bucket_name, 'Key': key_name, 'TargetPath': '$'}}
    config_event_with_replace = {
        'cma':
            {
                'task_config': 'foo_bar',
                'event': {
                    'replace': {'Bucket': bucket_name, 'Key': config_key_name, 'TargetPath': '$'}
                }
            }
    }
    event_without_replace = {'input': ':baby_whale:'}
    test_uuid = 'aad93279-95d4-4ada-8c43-aa5823f8bbbc'
    next_event_object_key_name = f'events/{test_uuid}'
    s3 = aws.s3()
    cumulus_message_adapter = message_adapter.MessageAdapter()
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
        self.s3.Object(self.bucket_name, self.config_key_name).put(
            Body=json.dumps(self.config_s3_object)
        )

    def tearDown(self):
        delete_objects_object = {
            'Objects': [{'Key': self.key_name}, {'Key': self.next_event_object_key_name},
                        {'Key': self.config_key_name}]
        }
        self.s3.Bucket(self.bucket_name).delete_objects(Delete=delete_objects_object)
        self.s3.Bucket(self.bucket_name).delete()
    # load_and_update_remote_event tests

    def test_returns_remote_s3_object(self):
        """ Test remote s3 event is returned when 'replace' key is present """
        result = self.cumulus_message_adapter.load_and_update_remote_event(
            self.event_with_replace, None)
        assert result == self.s3_object

    def test_returns_event(self):
        """ Test event argument is returned when 'replace' key is not present """
        result = self.cumulus_message_adapter.load_and_update_remote_event(
            self.event_without_replace, None)
        assert result == self.event_without_replace

    def test_load_and_update_remote_event_handles_cma_parameter(self):
        """ Test incoming event with 'cma' parameter is assembled into CMA message """
        result = self.cumulus_message_adapter.load_and_update_remote_event(
            self.event_with_cma, None)
        expected = {'foo': 'bar', 'some': 'object'}
        self.assertEqual(expected, result)

    def test_load_and_update_remote_event_does_not_overwrite_configuration(self):
        """ Test incoming event with configuration is not overwritten by key in remote event """
        result = self.cumulus_message_adapter.load_and_update_remote_event(
            self.config_event_with_replace, None)
        expected = {'task_config': self.config_event_with_replace['cma']['task_config'],
                    'input': ':blue_whale:',
                    'replace': self.config_event_with_replace['cma']['event']['replace']}
        self.assertEqual(expected, result)


    # load_nested_event task_config tests
    def test_returns_load_nested_event_local_with_task_config(self):
        """
        Test returns 'config', 'input' and 'messageConfig' in expected format from task_config with
        no taskName
        - 'input' in return value is from 'payload' in first argument object
        - 'config' in return value is the task ($.task_config) configuration
           with 'cumulus_message' excluded
        - 'messageConfig' in return value is the cumulus_message.input of the task configuration
        """

        nested_event_local = {
            "task_config": {
                "bar": "baz",
                "cumulus_message": {
                    "input": "{$.payload.input}",
                    "outputs": [{"source": "{$.input.anykey}",
                                 "destination": "{$.payload.out}"}]
                }
            },
            "cumulus_meta": {"message_source": "local", "id": "id-1234"},
            "meta": {"foo": "bar"},
            "payload": {"input": {"anykey": "anyvalue"}}
        }

        nested_event_local_return = {
            'input': {'anykey': 'anyvalue'},
            'config': {'bar': 'baz'},
            'messageConfig': {
                'input': '{$.payload.input}',
                'outputs': [{'source': '{$.input.anykey}',
                             'destination': '{$.payload.out}'}]}
        }

        result = self.cumulus_message_adapter.load_nested_event(nested_event_local)
        assert result == nested_event_local_return

    # assign_outputs tests
    def test_result_payload_without_config(self):
        """ Test nestedResponse is returned when no config argument is passed """
        result = self.cumulus_message_adapter._MessageAdapter__assign_outputs(
            self.nested_response, {}, None)
        assert result['payload'] == self.nested_response

    def test_result_payload_without_config_outputs(self):
        """ Test nestedResponse is returned when config has no outputs key/value """
        message_config_without_outputs = {}
        result = self.cumulus_message_adapter._MessageAdapter__assign_outputs(
            self.nested_response, {}, message_config_without_outputs)
        assert result['payload'] == self.nested_response

    def test_result_payload_with_simple_config_outputs(self):
        """ Test payload value is updated when messageConfig contains outputs templates """
        # messageConfig objects
        message_config_with_simple_outputs = {
            'outputs': [{
                'source': '{$.input.dataLocation}',
                'destination': '{$.payload}'
            }]
        }

        result = self.cumulus_message_adapter._MessageAdapter__assign_outputs(
            self.nested_response, {}, message_config_with_simple_outputs)
        assert result['payload'] == 's3://source.jpg'

    def test_result_payload_with_nested_config_outputs(self):
        """
        Test nested payload value is updated when messageConfig contains
        outputs templates with child nodes
        """
        message_config_with_nested_outputs = {
            'outputs': [{
                'source': '{$.input.dataLocation}',
                'destination': '{$.payload.dataLocation}'
            }]
        }

        result = self.cumulus_message_adapter._MessageAdapter__assign_outputs(
            self.nested_response, {}, message_config_with_nested_outputs)
        assert result['payload'] == {'dataLocation': 's3://source.jpg'}

    def test_result_payload_with_nested_sibling_config_outputs(self):
        """
        Test nested payload value is updated when messageConfig contains
        outputs templates where sibling nodes exist
        """
        message_config_with_nested_outputs = {
            'outputs': [{
                'source': '{$.input.dataLocation}',
                'destination': '{$.test.dataLocation}'
            }]
        }

        event = {
            'test': {
                'key': 'value'
            }
        }

        result = self.cumulus_message_adapter._MessageAdapter__assign_outputs(
            self.nested_response, event, message_config_with_nested_outputs)
        assert result['test'] == {
            'dataLocation': 's3://source.jpg',
            'key': 'value'
        }

    # create_next_event tests
    def test_with_replace(self):
        """
        Test 'replace' key is deleted from value returned from create_next_event
        """
        result = self.cumulus_message_adapter.create_next_event(
            self.nested_response, self.event_with_replace, None)
        assert 'replace' not in result

    def test_small_result_returns_event(self):
        """ Test return result is the event result when it's not too big """
        result = self.cumulus_message_adapter.create_next_event(
            self.nested_response, self.event_without_replace, None)
        expected_result = {
            'input': ':baby_whale:',
            'exception': 'None',
            'payload': {
                'input': {'dataLocation': 's3://source.jpg'}
            }
        }
        assert result == expected_result

    @patch('uuid.uuid4')
    def test_configured_big_result_stored_remotely(self, uuid_mock):
        """
        Test remote payload is stored in S3 and return value points
        to remote location with 'replace' key/value and correct configuration
        """
        event_with_ingest = {
            'cumulus_meta': {
                'workflow': 'testing',
                'system_bucket': self.bucket_name
            },
            'meta': 'some meta object',
            'ReplaceConfig': {
                'Path': '$.payload',
                'MaxSize': 1,
                'TargetPath': '$.payload'
            },
        }
        expected_create_next_event_result = {
            'cumulus_meta': {
                'workflow': 'testing',
                'system_bucket': self.bucket_name
            },
            'meta': 'some meta object',
            'payload': {},
            'exception': 'None',
            'replace': {'Bucket': self.bucket_name, 'Key': self.next_event_object_key_name,
                        'TargetPath': '$.payload'}
        }
        expected_remote_event_object = {
            'input': {'dataLocation': 's3://source.jpg'}
        }

        uuid_mock.return_value = self.test_uuid
        create_next_event_result = self.cumulus_message_adapter.create_next_event(
            self.nested_response, event_with_ingest, None)

        remote_event = self.s3.Object(self.bucket_name, self.next_event_object_key_name).get()
        remote_event_object = json.loads(
            remote_event['Body'].read().decode('utf-8'))

        self.assertEqual(remote_event_object, expected_remote_event_object)
        self.assertEqual(create_next_event_result, expected_create_next_event_result)

    @patch('uuid.uuid4')
    def test_configured_big_result_with_non_dict_target_stored_remotely(self, uuid_mock):
        """
        Test ReplaceConfig/associated logic handles a JSON path that targets a key
        with a non-dict value
        """
        event_with_ingest = {
            'cumulus_meta': {
                'workflow': 'testing',
                'system_bucket': self.bucket_name
            },
            'meta': {
                'another_key': {
                    'some_meta_key': 'some_meta_object'
                }},
            'ReplaceConfig': {
                'Path': '$.meta.another_key.some_meta_key',
                'MaxSize': 1,
                'TargetPath': '$.meta.another_key.some_meta_key'
            }
        }

        expected_create_next_event_result = {
            'cumulus_meta': {
                'workflow': 'testing',
                'system_bucket': self.bucket_name
            },
            'meta': {
                'another_key': {
                    'some_meta_key': ''
                }
            },
            'payload': self.nested_response,
            'exception': 'None',
            'replace': {'Bucket': self.bucket_name, 'Key': self.next_event_object_key_name,
                        'TargetPath': '$.meta.another_key.some_meta_key'}
        }
        expected_remote_event_object = 'some_meta_object'

        uuid_mock.return_value = self.test_uuid
        create_next_event_result = self.cumulus_message_adapter.create_next_event(
            self.nested_response, event_with_ingest, None)

        remote_event = self.s3.Object(self.bucket_name, self.next_event_object_key_name).get()
        remote_event_object = json.loads(
            remote_event['Body'].read().decode('utf-8'))

        self.assertEqual(remote_event_object, expected_remote_event_object)
        self.assertEqual(create_next_event_result, expected_create_next_event_result)

    @patch('uuid.uuid4')
    def test_big_result_stored_remotely(self, uuid_mock):
        """
        Test remote event is stored in S3 and return value points
        to remote location with 'replace' key/value
        """

        event_with_ingest = {
            'cumulus_meta': {
                'workflow': 'testing',
                'system_bucket': self.bucket_name
            },
            'ReplaceConfig': {
                'FullMessage': 'true',
                'MaxSize': 1,
            }
        }
        expected_create_next_event_result = {
            'cumulus_meta': {
                'workflow': 'testing',
                'system_bucket': self.bucket_name
            },
            'replace': {'Bucket': self.bucket_name, 'Key': self.next_event_object_key_name,
                        'TargetPath': '$'}
        }
        expected_remote_event_object = {
            'cumulus_meta': {
                'workflow': 'testing',
                'system_bucket': self.bucket_name
            },
            'exception': 'None',
            'payload': {'input': {'dataLocation': 's3://source.jpg'}}
        }

        uuid_mock.return_value = self.test_uuid
        create_next_event_result = self.cumulus_message_adapter.create_next_event(
            self.nested_response, event_with_ingest, None)

        remote_event = self.s3.Object(self.bucket_name, self.next_event_object_key_name).get()
        remote_event_object = json.loads(
            remote_event['Body'].read().decode('utf-8'))

        self.assertEqual(remote_event_object, expected_remote_event_object)
        self.assertEqual(create_next_event_result, expected_create_next_event_result)

    def test_basic(self):
        """ test basic.input.json """
        inp = open(os.path.join(self.test_folder, 'basic.input.json'), encoding='utf-8')
        out = open(os.path.join(self.test_folder, 'basic.output.json'), encoding='utf-8')
        in_msg = json.loads(inp.read())
        out_msg = json.loads(out.read())

        msg = self.cumulus_message_adapter.load_nested_event(in_msg)
        message_config = msg.get('messageConfig')
        if 'messageConfig' in msg:
            del msg['messageConfig']
        result = self.cumulus_message_adapter.create_next_event(msg, in_msg, message_config)
        assert result == out_msg

    def test_exception(self):
        """ test exception.input.json """
        inp = open(os.path.join(self.test_folder, 'exception.input.json'), encoding='utf-8')
        out = open(os.path.join(self.test_folder, 'exception.output.json'), encoding='utf-8')
        in_msg = json.loads(inp.read())
        out_msg = json.loads(out.read())

        bucket_name = in_msg['replace']['Bucket']
        key_name = in_msg['replace']['Key']
        data_filename = os.path.join(self.test_folder, key_name)
        with open(data_filename, 'r', encoding='utf-8') as file_data:
            datasource = json.load(file_data)
        self.s3.Bucket(bucket_name).create()
        self.s3.Object(bucket_name, key_name).put(Body=json.dumps(datasource))

        remote_event = self.cumulus_message_adapter.load_and_update_remote_event(in_msg, {})
        msg = self.cumulus_message_adapter.load_nested_event(remote_event)
        message_config = msg.get('messageConfig')
        if 'messageConfig' in msg:
            del msg['messageConfig']
        result = self.cumulus_message_adapter.create_next_event(msg, remote_event, message_config)

        delete_objects_object = {'Objects': [{'Key': key_name}]}
        self.s3.Bucket(bucket_name).delete_objects(Delete=delete_objects_object)
        self.s3.Bucket(bucket_name).delete()
        assert result == out_msg

    def test_jsonpath(self):
        """ test jsonpath.input.json """
        inp = open(os.path.join(self.test_folder, 'jsonpath.input.json'), encoding='utf-8')
        out = open(os.path.join(self.test_folder, 'jsonpath.output.json'), encoding='utf-8')
        in_msg = json.loads(inp.read())
        out_msg = json.loads(out.read())

        msg = self.cumulus_message_adapter.load_nested_event(in_msg)
        message_config = msg.get('messageConfig')
        if 'messageConfig' in msg:
            del msg['messageConfig']
        result = self.cumulus_message_adapter.create_next_event(msg, in_msg, message_config)
        assert result == out_msg

    def test_meta(self):
        """ test meta.input.json """
        inp = open(os.path.join(self.test_folder, 'meta.input.json'), encoding='utf-8')
        out = open(os.path.join(self.test_folder, 'meta.output.json'), encoding='utf-8')
        in_msg = json.loads(inp.read())
        out_msg = json.loads(out.read())

        msg = self.cumulus_message_adapter.load_nested_event(in_msg)
        message_config = msg.get('messageConfig')
        if 'messageConfig' in msg:
            del msg['messageConfig']
        result = self.cumulus_message_adapter.create_next_event(msg, in_msg, message_config)
        assert result == out_msg

    def test_remote(self):
        """ test remote.input.json """
        inp = open(os.path.join(self.test_folder, 'remote.input.json'), encoding='utf-8')
        out = open(os.path.join(self.test_folder, 'remote.output.json'), encoding='utf-8')
        in_msg = json.loads(inp.read())
        out_msg = json.loads(out.read())

        bucket_name = in_msg['replace']['Bucket']
        key_name = in_msg['replace']['Key']
        data_filename = os.path.join(self.test_folder, key_name)
        with open(data_filename, 'r', encoding='utf-8') as file_data:
            datasource = json.load(file_data)
        self.s3.Bucket(bucket_name).create()
        self.s3.Object(bucket_name, key_name).put(Body=json.dumps(datasource))

        remote_event = self.cumulus_message_adapter.load_and_update_remote_event(in_msg, {})
        msg = self.cumulus_message_adapter.load_nested_event(remote_event)
        message_config = msg.get('messageConfig')
        if 'messageConfig' in msg:
            del msg['messageConfig']
        result = self.cumulus_message_adapter.create_next_event(msg, remote_event, message_config)

        delete_objects_object = {'Objects': [{'Key': key_name}]}
        self.s3.Bucket(bucket_name).delete_objects(Delete=delete_objects_object)
        self.s3.Bucket(bucket_name).delete()
        assert result == out_msg

    def test_configured_remote(self):
        """ test configured_remote.input.json """
        inp = open(os.path.join(self.test_folder, 'configured_remote.input.json'), encoding='utf-8')
        out = open(os.path.join(self.test_folder,
                                'configured_remote.output.json'), encoding='utf-8')
        in_msg = json.loads(inp.read())
        out_msg = json.loads(out.read())

        bucket_name = in_msg['cma']['event']['replace']['Bucket']
        key_name = in_msg['cma']['event']['replace']['Key']
        data_filename = os.path.join(self.test_folder, key_name)
        with open(data_filename, 'r', encoding='utf-8') as file_data:
            datasource = json.load(file_data)
        self.s3.Bucket(bucket_name).create()
        self.s3.Object(bucket_name, key_name).put(Body=json.dumps(datasource))

        remote_event = self.cumulus_message_adapter.load_and_update_remote_event(in_msg, {})
        msg = self.cumulus_message_adapter.load_nested_event(remote_event)
        message_config = msg.get('messageConfig')
        if 'messageConfig' in msg:
            del msg['messageConfig']
        result = self.cumulus_message_adapter.create_next_event(msg, remote_event, message_config)

        delete_objects_object = {'Objects': [{'Key': key_name}]}
        self.s3.Bucket(bucket_name).delete_objects(Delete=delete_objects_object)
        self.s3.Bucket(bucket_name).delete()
        self.assertEqual(result, out_msg)

    def test_non_object_configured_remote(self):
        """ test_non_object_configured_remote.input.json """
        inp = open(
            os.path.join(
                self.test_folder,
                'configured_non_object_remote.input.json'
            ),
            encoding='utf-8'
        )
        out = open(
            os.path.join(
                self.test_folder,
                'configured_non_object_remote.output.json'
            ),
            encoding='utf-8'
        )
        in_msg = json.loads(inp.read())
        out_msg = json.loads(out.read())

        bucket_name = in_msg['cma']['event']['replace']['Bucket']
        key_name = in_msg['cma']['event']['replace']['Key']
        data_filename = os.path.join(self.test_folder, key_name)
        with open(data_filename, 'r', encoding='utf-8') as file_data:
            datasource = json.load(file_data)
        self.s3.Bucket(bucket_name).create()
        self.s3.Object(bucket_name, key_name).put(Body=json.dumps(datasource))

        remote_event = self.cumulus_message_adapter.load_and_update_remote_event(in_msg, {})
        msg = self.cumulus_message_adapter.load_nested_event(remote_event)
        message_config = msg.get('messageConfig')
        if 'messageConfig' in msg:
            del msg['messageConfig']
        result = self.cumulus_message_adapter.create_next_event(msg, remote_event, message_config)

        delete_objects_object = {'Objects': [{'Key': key_name}]}
        self.s3.Bucket(bucket_name).delete_objects(Delete=delete_objects_object)
        self.s3.Bucket(bucket_name).delete()
        self.assertEqual(result, out_msg)

    def test_sfn(self):
        """ test sfn.input.json """
        inp = open(os.path.join(self.test_folder, 'sfn.input.json'), encoding='utf-8')
        out = open(os.path.join(self.test_folder, 'sfn.output.json'), encoding='utf-8')
        in_msg = json.loads(inp.read())
        out_msg = json.loads(out.read())

        msg = self.cumulus_message_adapter.load_nested_event(in_msg)
        message_config = msg.get('messageConfig')
        if 'messageConfig' in msg:
            del msg['messageConfig']
        result = self.cumulus_message_adapter.create_next_event(msg, in_msg, message_config)
        assert result == out_msg

    def test_context(self):
        """ test storing context metadata """
        inp = open(os.path.join(self.test_folder, 'context.input.json'), encoding='utf-8')
        out = open(os.path.join(self.test_folder, 'context.output.json'), encoding='utf-8')
        ctx = open(os.path.join(self.context_folder, 'lambda-context.json'), encoding='utf-8')
        in_msg = json.loads(inp.read())
        out_msg = json.loads(out.read())
        context = json.loads(ctx.read())

        rem = self.cumulus_message_adapter.load_and_update_remote_event(in_msg, context)
        msg = self.cumulus_message_adapter.load_nested_event(rem)
        message_config = msg.get('messageConfig')
        if 'messageConfig' in msg:
            del msg['messageConfig']
        result = self.cumulus_message_adapter.create_next_event(msg, in_msg, message_config)
        assert result == out_msg

    def test_inline_template(self):
        """ test inline_template.input.json """
        inp = open(os.path.join(self.test_folder, 'inline_template.input.json'), encoding='utf-8')
        out = open(os.path.join(self.test_folder, 'inline_template.output.json'), encoding='utf-8')
        in_msg = json.loads(inp.read())
        out_msg = json.loads(out.read())

        msg = self.cumulus_message_adapter.load_nested_event(in_msg)
        message_config = msg.get('messageConfig')
        if 'messageConfig' in msg:
            del msg['messageConfig']
        result = self.cumulus_message_adapter.create_next_event(msg, in_msg, message_config)
        assert result == out_msg

    def test_templates(self):
        """ test templates.input.json """
        inp = open(os.path.join(self.test_folder, 'templates.input.json'), encoding='utf-8')
        out = open(os.path.join(self.test_folder, 'templates.output.json'), encoding='utf-8')
        in_msg = json.loads(inp.read())
        out_msg = json.loads(out.read())

        msg = self.cumulus_message_adapter.load_nested_event(in_msg)
        message_config = msg.get('messageConfig')
        if 'messageConfig' in msg:
            del msg['messageConfig']
        result = self.cumulus_message_adapter.create_next_event(msg, in_msg, message_config)
        assert result == out_msg

    def test_cumulus_context(self):
        """ test storing cumulus_context metadata """
        inp = open(os.path.join(self.test_folder, 'cumulus_context.input.json'), encoding='utf-8')
        out = open(os.path.join(self.test_folder, 'cumulus_context.output.json'), encoding='utf-8')
        in_msg = json.loads(inp.read())
        out_msg = json.loads(out.read())

        msg = self.cumulus_message_adapter.load_nested_event(in_msg)
        message_config = msg.get('messageConfig')
        if 'messageConfig' in msg:
            del msg['messageConfig']
        result = self.cumulus_message_adapter.create_next_event(msg, in_msg, message_config)
        assert result == out_msg

    def test_input_jsonschema(self):
        """ test a working input schema """
        inp = open(os.path.join(self.test_folder, 'templates.input.json'), encoding='utf-8')
        schemas = {'input': 'input.json'}
        adapter = message_adapter.MessageAdapter(schemas)
        in_msg = json.loads(inp.read())
        in_msg["payload"] = {"hello": "world"}
        msg = adapter.load_nested_event(in_msg)
        assert msg["input"]["hello"] == "world"

    def test_failing_input_jsonschema(self):
        """ test a failing input schema """
        inp = open(os.path.join(self.test_folder, 'templates.input.json'), encoding='utf-8')
        schemas = {'input': 'input.json'}
        adapter = message_adapter.MessageAdapter(schemas)
        in_msg = json.loads(inp.read())
        in_msg["payload"] = {"hello": 1}
        try:
            adapter.load_nested_event(in_msg)
        except ValidationError as e:
            assert e.message == "input schema: 1 is not of type u'string'"

    def test_config_jsonschema(self):
        """ test a working config schema """
        inp = open(os.path.join(self.test_folder, 'templates.input.json'), encoding='utf-8')
        schemas = {'config': 'config.json'}
        adapter = message_adapter.MessageAdapter(schemas)
        in_msg = json.loads(inp.read())
        msg = adapter.load_nested_event(in_msg)
        assert msg["config"]["inlinestr"] == 'prefixbarsuffix'

    def test_failing_config_jsonschema(self):
        """ test a failing input schema """
        inp = open(os.path.join(self.test_folder, 'templates.input.json'), encoding='utf-8')
        schemas = {'config': 'config.json'}
        adapter = message_adapter.MessageAdapter(schemas)
        in_msg = json.loads(inp.read())
        in_msg["task_config"]["boolean_option"] = '{$.meta.boolean_option}'
        in_msg["meta"]["boolean_option"] = "notgoingtowork"
        try:
            adapter.load_nested_event(in_msg)
        except ValidationError as e:
            assert e.message == "config schema: 'notgoingtowork' is not of type u'boolean'"

    def test_output_jsonschema(self):
        """ test a working output schema """
        inp = open(os.path.join(self.test_folder, 'templates.input.json'), encoding='utf-8')
        schemas = {'output': 'output.json'}
        adapter = message_adapter.MessageAdapter(schemas)
        in_msg = json.loads(inp.read())
        msg = adapter.load_nested_event(in_msg)
        message_config = msg.get('messageConfig')
        handler_response = {"goodbye": "world"}
        result = adapter.create_next_event(handler_response, in_msg, message_config)
        assert result["payload"]["goodbye"] == "world"

    def test_failing_output_jsonschema(self):
        """ test a working output schema """
        inp = open(os.path.join(self.test_folder, 'templates.input.json'), encoding='utf-8')
        schemas = {'output': 'output.json'}
        adapter = message_adapter.MessageAdapter(schemas)
        in_msg = json.loads(inp.read())
        msg = adapter.load_nested_event(in_msg)
        messageConfig = msg.get('messageConfig')
        handler_response = {"goodbye": 1}
        try:
            adapter.create_next_event(handler_response, in_msg, messageConfig,)
        except ValidationError as e:
            assert e.message == "output schema: 1 is not of type u'string'"
