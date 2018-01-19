import boto3
import json

from message import message
from message import aws_sled

# setup
sled_message = message.message()
s3 = aws_sled.s3()
bucket_name = 'testing-bucket'
key_name = 'blue_whale-event.json'
s3_object = {'input': ':blue_whale:'}
event_with_replace = {'replace': { 'Bucket': bucket_name, 'Key': key_name}}
event_without_replace = {'input': ':baby_whale:'}
nested_event_local = {"workflow_config":{
  "Example":{
    "bar":"baz",
    "cumulus_message":{
      "input":"{{$.payload.input}}",
      "outputs":[{"source":"{{$.input.anykey}}",
      "destination":"{{$.payload.out}}"}]}
    }
  },
  "cumulus_meta":{"task":"Example","message_source":"local","id":"id-1234"},
  "meta":{"foo":"bar"},"payload":{"input":{"anykey":"anyvalue"}
  }
};
nested_event_local_return = {
  'input': {'anykey': 'anyvalue'},
  'config': {'bar': 'baz'},
  'messageConfig': {
    'input': '{{$.payload.input}}', 
    'outputs': [{'source': '{{$.input.anykey}}', 
    'destination': '{{$.payload.out}}'}]} 
};

def setup():
  s3.Bucket(bucket_name).create()
  s3.Object(bucket_name, key_name).put(Body=json.dumps(s3_object))

def teardown():
  s3.Object(bucket_name, key_name).delete()
  s3.Bucket(bucket_name).delete()

def test_returns_remote_s3_object():  
  result = sled_message.loadRemoteEvent(event_with_replace)
  assert result == s3_object

def test_returns_event():  
  result = sled_message.loadRemoteEvent(event_without_replace)
  assert result == event_without_replace

def test_returns_loadNestedEvent():
  result = sled_message.loadNestedEvent(nested_event_local, {})
  assert result == nested_event_local_return;

