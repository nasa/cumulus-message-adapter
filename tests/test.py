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
