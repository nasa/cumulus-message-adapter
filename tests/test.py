import boto3
import json
from mock import patch
import unittest
import uuid

from message import aws_sled, message

# Setup objects for testing
sled_message = message.message()
s3 = aws_sled.s3()
bucket_name = 'testing-bucket'
key_name = 'blue_whale-event.json'
s3_object = {'input': ':blue_whale:'}

# Event objects
event_with_replace = {'replace': {'Bucket': bucket_name, 'Key': key_name}}
event_without_replace = {'input': ':baby_whale:'}
event_with_ingest = {
    'ingest_meta': {
        'message_bucket': bucket_name
    },
    'cumulus_meta': {
        'workflow': 'testing'
    }
}
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
    "payload": {"input": {"anykey": "anyvalue"}
                }
}
nested_event_local_return = {
    'input': {'anykey': 'anyvalue'},
    'config': {'bar': 'baz'},
    'messageConfig': {
        'input': '{{$.payload.input}}',
        'outputs': [{'source': '{{$.input.anykey}}',
                     'destination': '{{$.payload.out}}'}]}
}

# nestedResponse objects
nestedResponse = {
    'input': {
        'dataLocation': 's3://source.jpg'
    }
}

# messageConfig objects
message_config_with_simple_outputs = {
    'outputs': [{
        'source': '{{$.input.dataLocation}}',
        'destination': '{{$.payload}}'
    }]
}
message_config_with_nested_outputs = {
    'outputs': [{
        'source': '{{$.input.dataLocation}}',
        'destination': '{{$.payload.dataLocation}}'
    }]
}
message_config_without_outputs = {}

test_uuid = 'aad93279-95d4-4ada-8c43-aa5823f8bbbc'
next_event_object_key_name = "events/{0}".format(test_uuid)


class Test(unittest.TestCase):

    def setUp(self):
        s3.Bucket(bucket_name).create()
        s3.Object(bucket_name, key_name).put(Body=json.dumps(s3_object))

    def tearDown(self):
        delete_objects_object = {
            'Objects': [{'Key': key_name}, {'Key': next_event_object_key_name}]
        }
        s3.Bucket(bucket_name).delete_objects(Delete=delete_objects_object)
        s3.Bucket(bucket_name).delete()

    # loadRemoteEvent tests
    def test_returns_remote_s3_object(self):
        """ Test remote s3 event is returned when 'replace' key is present """
        result = sled_message.loadRemoteEvent(event_with_replace)
        assert result == s3_object

    def test_returns_event(self):
        """ Test event argument is returned when 'replace' key is not present """
        result = sled_message.loadRemoteEvent(event_without_replace)
        assert result == event_without_replace

    # loadNestedEvent tests
    def test_returns_loadNestedEvent_local(self):
        """
        Test returns 'config', 'input' and 'messageConfig' in expected format
        - 'input' in return value is from 'payload' in first argument object
        - 'config' in return value is the task ($.cumulus_meta.task) configuration with 'cumulus_message' excluded
        - 'messageConfig' in return value is the cumulus_message.input of the task configuration
        """
        result = sled_message.loadNestedEvent(nested_event_local, {})
        assert result == nested_event_local_return

    # assignOutputs tests
    def test_result_payload_without_config(self):
        """ Test nestedResponse is returned when no config argument is passed """
        result = sled_message._message__assignOutputs(nestedResponse, {}, None)
        assert result['payload'] == nestedResponse

    def test_result_payload_without_config_outputs(self):
        """ Test nestedResponse is returned when config has no outputs key/value """
        result = sled_message._message__assignOutputs(
            nestedResponse, {}, message_config_without_outputs)
        assert result['payload'] == nestedResponse

    def test_result_payload_with_simple_config_outputs(self):
        """ Test payload value is updated when messageConfig contains outputs templates """
        result = sled_message._message__assignOutputs(
            nestedResponse, {}, message_config_with_simple_outputs)
        assert result['payload'] == 's3://source.jpg'

    def test_result_payload_with_nested_config_outputs(self):
        """
        Test nested payload value is updated when messageConfig contains outputs templates with child nodes
        """
        result = sled_message._message__assignOutputs(
            nestedResponse, {}, message_config_with_nested_outputs)
        assert result['payload'] == {'dataLocation': 's3://source.jpg'}

    # createNextEvent tests
    def test_with_replace(self):
        """
        Test 'replace' key is deleted from value returned from createNextEvent
        """
        result = sled_message.createNextEvent(
            nestedResponse, event_with_replace, None)
        assert 'replace' not in result

    def test_small_result_returns_event(self):
        """ Test return result is the event result when it's not too big """
        result = sled_message.createNextEvent(
            nestedResponse, event_without_replace, None)
        expected_result = {
            'input': ':baby_whale:',
            'exception': 'None',
            'payload': {
                'input': {'dataLocation': 's3://source.jpg'}
            }
        }
        assert result == expected_result

    @patch.object(sled_message, 'MAX_NON_S3_PAYLOAD_SIZE', 1)
    @patch('uuid.uuid4')
    def test_big_result_stored_remotely(self, uuid_mock):
        """
        Test remote event is stored in S3 and return value points to remote location with 'replace' key/value
        """
        uuid_mock.return_value = test_uuid
        createNextEvent_result = sled_message.createNextEvent(
            nestedResponse, event_with_ingest, None)
        expected_createNextEvent_result = {
            'cumulus_meta': {'workflow': 'testing'},
            'replace': {'Bucket': bucket_name, 'Key': next_event_object_key_name}
        }
        remote_event = s3.Object(bucket_name, next_event_object_key_name).get()
        remote_event_object = json.loads(
            remote_event['Body'].read().decode('utf-8'))
        expected_remote_event_object = {
            'cumulus_meta': {'workflow': 'testing'},
            'ingest_meta': {'message_bucket': 'testing-bucket'},
            'exception': 'None',
            'payload': {'input': {'dataLocation': 's3://source.jpg'}}
        }
        assert remote_event_object == expected_remote_event_object
        assert createNextEvent_result == expected_createNextEvent_result
