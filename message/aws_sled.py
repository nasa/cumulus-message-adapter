""" Determines the correct AWS endpoint for AWS services """

import os
import boto3


def s3():
    """ Determines the endpoint for the S3 service """

    if ('ENV' in os.environ) and (os.environ['ENV'] == 'testing'):
        if 'LOCALSTACK_HOST' in os.environ:
            localhost_s3_url = 'http://%s:4572' % os.environ['LOCALSTACK_HOST']
        else:
            localhost_s3_url = 'http://localhost:4572'
        return boto3.resource(
            service_name='s3',
            endpoint_url=localhost_s3_url,
            aws_access_key_id='my-id',
            aws_secret_access_key='my-secret',
            region_name='us-east-1',
            verify=False
        )
    return boto3.resource('s3')
