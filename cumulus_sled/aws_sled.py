import boto3
import os

localhost_s3_url = 'http://localhost:4572'

def s3():
  if ('ENV' in os.environ) and (os.environ["ENV"] == 'testing'):
    return boto3.resource(service_name='s3', endpoint_url=localhost_s3_url)
  else:
    return boto3.resource('s3')
