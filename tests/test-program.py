"""
Tests for cumulus-message-adapter command-line interface
"""
import os
import json
import subprocess
import unittest

class Test(unittest.TestCase):
    """ Test class """
    test_folder = os.path.join(os.getcwd(), 'examples/messages')
    os.environ["LAMBDA_TASK_ROOT"] = os.path.join(os.getcwd(), 'examples')

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

    def test_basic(self):
        """ test basic message """
        self.transformMessages('basic')

    def test_jsonpath(self):
        """ test jsonpath message """
        self.transformMessages('jsonpath')

    def test_meta(self):
        """ test meta message """
        self.transformMessages('meta')

    def test_context(self):
        """ test storing taskmeta in message """
        self.transformMessages('context', {
            'function_name': 'fakeStep',
            'function_version': 1,
            'invoked_function_arn': 'arn:aws:lambda:us-east-1:123:function:fakeStep:1'
        })

    def test_remote(self):
        """ test remote message """
        self.transformMessages('meta')

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
