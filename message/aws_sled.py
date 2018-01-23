""" Determines the correct AWS endpoint for AWS services """

import os
import boto3


def s3():
    """ Determines the endpoint for the S3 service """

    if 'LOCALSTACK_HOST' in os.environ:
        localhost_s3_url = 'http://%s:4572' % os.environ['LOCALSTACK_HOST']
    else:
        localhost_s3_url = 'http://localhost:4572'

    if ('ENV' in os.environ) and (os.environ['ENV'] == 'testing'):
        return boto3.resource(service_name='s3', endpoint_url=localhost_s3_url)
    return boto3.resource('s3')
