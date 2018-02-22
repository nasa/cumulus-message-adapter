"""
Tests for cumulus-message-adapter command-line interface
"""
import os
import json
import subprocess
import sys
import unittest

class Test(unittest.TestCase):
    """ Test class """
    test_folder = os.path.join(os.getcwd(), 'examples/messages')
    os.environ["LAMBDA_TASK_ROOT"] = os.path.join(os.getcwd(), 'examples')

    def executeCommand(self, cmd, inputMessage):
        """
        execute an external command command, and returns command exit status, stdout and stderr
        """
        process = subprocess.Popen([cmd], shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        outstr, errorstr = process.communicate(input=inputMessage)
        exitstatus = process.poll()
        return exitstatus, str(outstr), str(errorstr)

    def transformMessages(self, testcase):
        """
        transform cumulus messages, and check if the commands are successful and outputs are correct.
        Each test case (such as 'basic') has its corresponding example messages and schemas.
        """
        inp = open(os.path.join(self.test_folder, '{}.input.json'.format(testcase)))
        in_msg = json.loads(inp.read())
        schemas = {
            'input': 'schemas/exmaples-messages.output.json',
            'output': 'schemas/exmaples-messages.output.json',
            'config': 'schemas/examples-messages.config.json'
        }
        allInput = {'event': in_msg, 'schemas': schemas}
        currentDirectory = os.getcwd()
        remoteEventCmd = ' '.join(['python', currentDirectory, 'loadRemoteEvent'])
        (exitstatus, remoteEvent, errorstr) = self.executeCommand(remoteEventCmd, json.dumps(allInput)) # pylint: disable=unused-variable
        assert exitstatus == 0
        fullEvent = json.loads(remoteEvent)

        allInput = {'event': fullEvent, 'context': {}, 'schemas': schemas}
        loadNestedEvent = ' '.join(['python', currentDirectory, 'loadNestedEvent'])
        (exitstatus, nestedEvent, errorstr) = self.executeCommand(loadNestedEvent, json.dumps(allInput))
        assert exitstatus == 0

        msg = json.loads(nestedEvent)
        messageConfig = msg.get('messageConfig')
        if 'messageConfig' in msg: del msg['messageConfig']
        allInput = {'handler_response':msg, 'event': fullEvent, 'message_config': messageConfig, 'schemas': schemas}
        createNextEvent = ' '.join(['python', currentDirectory, 'createNextEvent'])
        (exitstatus, nextEvent, errorstr) = self.executeCommand(createNextEvent, json.dumps(allInput))
        assert exitstatus == 0

        out = open(os.path.join(self.test_folder, '{}.output.json'.format(testcase)))
        out_msg = json.loads(out.read())
        assert json.loads(nextEvent) == out_msg

    def test_basic(self):
        """ test basic """
        self.transformMessages('basic')

    def test_jsonpath(self):
        """ test jsonpath """
        self.transformMessages('jsonpath')
    
    def test_meta(self):
        """ test meta """
        self.transformMessages('meta')

    def test_remote(self):
        """ test remote """
        self.transformMessages('meta')

    def test_templates(self):
        """ test templates """
        self.transformMessages('templates')

    def test_validation_failure_case(self):
        """ test validation failure case """
        try:
            self.transformMessages("invalidinput")
        except AssertionError:
            pass
            return
        assert False
    