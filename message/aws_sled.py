import boto3
import os

localhost_s3_url = 'http://localhost:4572'

def s3():
  if ('ENV' in os.environ) and (os.environ["ENV"] == 'testing'):
    return boto3.resource(service_name='s3', endpoint_url=localhost_s3_url)
  else:
    return boto3.resource('s3')

def stepFn():
  region = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
  if ('ENV' in os.environ) and (os.environ["ENV"] == 'testing'):
    return boto3.client(service_name='stepfunctions', endpoint_url=localhost_s3_url, region_name=region)
  else:
    return boto3.client('stepfunctions', region_name=region)
