"""
Tests for cumulus-message-adapter command-line interface
"""
import os
import json
import subprocess
import unittest

from message_adapter import aws

class Test(unittest.TestCase):
    """ Test class """
    test_folder = os.path.join(os.getcwd(), 'examples/messages')
    os.environ["LAMBDA_TASK_ROOT"] = os.path.join(os.getcwd(), 'examples')

    def placeRemoteMessage(self, in_msg):
        """
        Place the remote message on S3 before test
        """
        self.s3 = aws.s3()
        bucket_name = in_msg['replace']['Bucket']
        key_name = in_msg['replace']['Key']
        data_filename = os.path.join(self.test_folder, key_name)
        with open(data_filename, 'r') as f: datasource = json.load(f)
        self.s3.Bucket(bucket_name).create()
        self.s3.Object(bucket_name, key_name).put(Body=json.dumps(datasource))
        return { 'bucket_name': bucket_name, 'key_name': key_name }

    def cleanUpRemoteMessage(self, bucket_name, key_name):
        delete_objects_object = {'Objects': [{'Key': key_name}]}
        self.s3.Bucket(bucket_name).delete_objects(Delete=delete_objects_object)
        self.s3.Bucket(bucket_name).delete()

    def executeCommand(self, cmd, inputMessage):
        """
        execute an external command command, and returns command exit status, stdout and stderr
        """
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        outstr, errorstr = process.communicate(
            input=inputMessage.encode())
        exitstatus = process.poll()
        if errorstr:
            print (errorstr.decode()) # pylint: disable=superfluous-parens
        return exitstatus, outstr.decode(), errorstr.decode()

    def transformMessages(self, testcase, context={}): #pylint: disable=too-many-locals
        """
        transform cumulus messages, and check if the command return status and outputs are correct.
        Each test case (such as 'basic') has its corresponding example messages and schemas.
        """
        inp = open(os.path.join(self.test_folder, '{}.input.json'.format(testcase)))
        in_msg = json.loads(inp.read())
        s3meta = None
        if ('replace' in in_msg):
            s3meta = self.placeRemoteMessage(in_msg)
        schemas = {
            'input': 'schemas/exmaples-messages.output.json',
            'output': 'schemas/exmaples-messages.output.json',
            'config': 'schemas/examples-messages.config.json'
        }

        allInput = {'event': in_msg, 'context': context, 'schemas': schemas}
        currentDirectory = os.getcwd()
        remoteEventCmd = ['python', currentDirectory, 'loadAndUpdateRemoteEvent']
        (exitstatus, remoteEvent, errorstr) = self.executeCommand( # pylint: disable=unused-variable
            remoteEventCmd, json.dumps(allInput))
        assert exitstatus == 0
        fullEvent = json.loads(remoteEvent)

        allInput = {'event': fullEvent, 'context': context, 'schemas': schemas}
        loadNestedEvent = ['python', currentDirectory, 'loadNestedEvent']
        (exitstatus, nestedEvent, errorstr) = self.executeCommand( # pylint: disable=unused-variable
            loadNestedEvent, json.dumps(allInput))
        assert exitstatus == 0

        msg = json.loads(nestedEvent)
        messageConfig = msg.get('messageConfig')
        if 'messageConfig' in msg:
            del msg['messageConfig']
        allInput = {'handler_response': msg, 'event': fullEvent,
                    'message_config': messageConfig, 'schemas': schemas}
        createNextEvent = ['python', currentDirectory, 'createNextEvent']
        (exitstatus, nextEvent, errorstr) = self.executeCommand(
            createNextEvent, json.dumps(allInput))
        assert exitstatus == 0

        out = open(os.path.join(self.test_folder, '{}.output.json'.format(testcase)))
        out_msg = json.loads(out.read())
        assert json.loads(nextEvent) == out_msg

        if s3meta is not None:
            self.cleanUpRemoteMessage(s3meta['bucket_name'], s3meta['key_name'])

    def test_basic(self):
        """ test basic message """
        self.transformMessages('basic')

    def test_exception(self):
        """ test remote message with exception """
        self.transformMessages('exception')

    def test_jsonpath(self):
        """ test jsonpath message """
        self.transformMessages('jsonpath')

    def test_meta(self):
        """ test meta message """
        self.transformMessages('meta')

    def test_remote(self):
        """ test remote message """
        self.transformMessages('remote')

    def test_templates(self):
        """ test templates message """
        self.transformMessages('templates')

    def test_validation_failure_case(self):
        """ test validation failure case """
        try:
            self.transformMessages("invalidinput")
        except AssertionError:
            return
        assert False
