"""
Tests for cumulus-message-adapter command-line interface
"""

import json
import os

# import subprocess
from subprocess import (
    Popen,
    PIPE,
)
import unittest
from typing import Dict, Literal, Tuple, Optional, cast, List, IO
from typing_extensions import TypedDict, NotRequired, Protocol

from mypy_boto3_s3.type_defs import DeleteTypeDef

from message_adapter import aws
from message_adapter.CMATypes import (
    CumulusMessage,
    AllInput,
    CumulusSchemas,
    CumulusContext,
)


class TransformParams(TypedDict):
    context: NotRequired[CumulusContext]
    schemas: NotRequired[CumulusSchemas]
    testcase: str


class BufferLike(Protocol):
    # pylint: disable=missing-function-docstring
    def write(self, string: bytes) -> None: ...
    def flush(self) -> None: ...


class Test(unittest.TestCase):
    # pylint: disable=attribute-defined-outside-init
    # pylint: disable=too-many-locals

    """Test class"""
    test_folder = os.path.join(os.getcwd(), "examples/messages")
    os.environ["LAMBDA_TASK_ROOT"] = os.path.join(os.getcwd(), "examples")

    def place_remote_message(
        self, in_msg: CumulusMessage
    ) -> Dict[Literal["bucket_name", "key_name"], str]:
        """
        Place the remote message on S3 before test
        """
        self.s3 = aws.s3()  # pylint: disable=invalid-name
        bucket_name = in_msg["replace"]["Bucket"]
        key_name = in_msg["replace"]["Key"]
        data_filename = os.path.join(self.test_folder, key_name)
        with open(data_filename, "r", encoding="utf-8") as data_file:
            datasource = json.load(data_file)
        self.s3.Bucket(bucket_name).create()
        self.s3.Object(bucket_name, key_name).put(Body=json.dumps(datasource))
        return {"bucket_name": bucket_name, "key_name": key_name}

    def clean_up_remote_message(self, bucket_name: str, key_name: str) -> None:
        """
        cleans up the remote message from the s3 bucket
        """
        delete_objects_object: DeleteTypeDef = {"Objects": [{"Key": key_name}]}
        self.s3.Bucket(bucket_name).delete_objects(Delete=delete_objects_object)
        self.s3.Bucket(bucket_name).delete()

    @staticmethod
    def execute_command(
        cmd: List[str], input_message: str
    ) -> Tuple[Optional[int], str, str]:
        """
        execute an external command command, and returns command exit status, stdout and stderr
        """

        with Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE) as process:
            outstr, errorstr = process.communicate(input=input_message.encode())
            exitstatus = process.poll()
        if errorstr:
            print(errorstr.decode())  # pylint: disable=superfluous-parens
        return exitstatus, outstr.decode(), errorstr.decode()

    @staticmethod
    def read_streaming_output(
        stream_process: Popen[bytes],
    ) -> CumulusMessage:
        """
        Given a subprocess, read stdout from that process until <EOC> line recieved
        """
        proc_stdout = stream_process.stdout
        if proc_stdout is None:
            raise ValueError("bad stream process in test")
        buffer = ""
        itercount = 0
        eoc_count = 0
        while not stream_process.poll() and itercount < 1000:
            itercount += 1
            next_line = proc_stdout.readline().decode("utf-8").rstrip("\n")
            if next_line != "<EOC>":
                buffer += next_line
            else:
                eoc_count += 1
                return cast(CumulusMessage, json.loads(buffer))
        proc_stderr = stream_process.stderr
        if proc_stderr is None:
            raise ValueError("bad stream process in test")

        err_string = "".join([x.decode("utf-8") for x in proc_stderr.readlines()])
        raise RuntimeError(err_string)

    @staticmethod
    def write_streaming_input(
        command: str, proc_input: AllInput, p_stdin: Optional[IO[bytes]]
    ) -> None:
        """
        Given a stdin pipe for a subprocess, write command/proc input to CMA subprocess
        """
        assert p_stdin is not None
        p_stdin.write((command + "\n").encode("utf-8"))
        p_stdin.write(json.dumps(proc_input).encode("utf-8"))
        p_stdin.write("\n".encode("utf-8"))
        p_stdin.write("<EOC>\n".encode("utf-8"))
        p_stdin.flush()

    def transform_messages_streaming(self, params: TransformParams) -> None:
        """
        Given a testcase, run 'streaming' interface against input and check if outputs are correct
        """

        schemas: CumulusSchemas = {
            "input": "schemas/examples-messages.input.json",
            "output": "schemas/examples-messages.output.json",
            "config": "schemas/examples-messages.config.json",
        }
        context = params.get("context", {})
        schemas = params.get("schemas", schemas)
        testcase = params["testcase"]

        with open(
            os.path.join(self.test_folder, f"{testcase}.input.json"), encoding="utf-8"
        ) as inp:
            in_msg = json.load(inp)
        s3meta = None
        if "replace" in in_msg:
            s3meta = self.place_remote_message(in_msg)

        cma_input: AllInput = {"event": in_msg, "context": context, "schemas": schemas}
        current_directory = os.getcwd()

        with Popen(
            ["python", current_directory, "stream"],
            stdin=PIPE,
            stdout=PIPE,
            stderr=PIPE,
        ) as stream_process:

            self.write_streaming_input(
                "loadAndUpdateRemoteEvent", cma_input, stream_process.stdin
            )
            load_and_update_remote_event_response = self.read_streaming_output(
                stream_process
            )
            cma_input = {
                "event": load_and_update_remote_event_response,
                "context": context,
                "schemas": schemas,
            }
            self.write_streaming_input(
                "loadNestedEvent", cma_input, stream_process.stdin
            )
            load_nested_event_response = self.read_streaming_output(stream_process)

            message_config = load_nested_event_response.get("messageConfig")
            if "messageConfig" in load_nested_event_response:
                del load_nested_event_response["messageConfig"]
            cma_input = {
                "handler_response": load_nested_event_response,
                "event": load_and_update_remote_event_response,
                "message_config": message_config,
                "schemas": schemas,
            }
            self.write_streaming_input(
                "createNextEvent", cma_input, stream_process.stdin
            )
            create_next_event_response = self.read_streaming_output(stream_process)
            stream_stdin = stream_process.stdin
            assert stream_stdin is not None
            stream_stdin.write("<EXIT>\n".encode("utf-8"))
            stream_stdin.flush()
            exit_code = stream_process.wait(20)
            assert exit_code == 0

        with open(
            os.path.join(self.test_folder, f"{testcase}.output.json"), encoding="utf-8"
        ) as out:
            out_msg = json.load(out)
        assert create_next_event_response == out_msg

        if s3meta is not None:
            self.clean_up_remote_message(s3meta["bucket_name"], s3meta["key_name"])

    def transform_messages(self, params: TransformParams) -> None:
        """
        transform cumulus messages, and check if the command return status and outputs are correct.
        Each test case (such as 'basic') has its corresponding example messages and schemas.
        """

        schemas: CumulusSchemas = {
            "input": "schemas/examples-messages.input.json",
            "output": "schemas/examples-messages.output.json",
            "config": "schemas/examples-messages.config.json",
        }
        context = params.get("context", None)
        schemas = params.get("schemas", schemas)
        testcase = params["testcase"]

        with open(
            os.path.join(self.test_folder, f"{testcase}.input.json"), encoding="utf-8"
        ) as inp:
            in_msg = json.load(inp)
        s3meta = None
        if "replace" in in_msg:
            s3meta = self.place_remote_message(in_msg)

        all_input = {"event": in_msg, "context": context, "schemas": schemas}
        current_directory = os.getcwd()
        remote_event_command = ["python", current_directory, "loadAndUpdateRemoteEvent"]
        (exitstatus, remote_event, _) = self.execute_command(
            remote_event_command, json.dumps(all_input)
        )
        assert exitstatus == 0
        full_event = json.loads(remote_event)

        all_input = {"event": full_event, "context": context, "schemas": schemas}
        load_nested_event = ["python", current_directory, "loadNestedEvent"]
        (exitstatus, nested_event, _) = self.execute_command(
            load_nested_event, json.dumps(all_input)
        )
        assert exitstatus == 0

        msg = json.loads(nested_event)
        message_config = msg.get("messageConfig")
        if "messageConfig" in msg:
            del msg["messageConfig"]
        all_input = {
            "handler_response": msg,
            "event": full_event,
            "message_config": message_config,
            "schemas": schemas,
        }
        create_next_event = ["python", current_directory, "createNextEvent"]
        (exitstatus, next_event, _) = self.execute_command(
            create_next_event, json.dumps(all_input)
        )
        assert exitstatus == 0

        with open(
            os.path.join(self.test_folder, f"{testcase}.output.json"), encoding="utf-8"
        ) as out:
            out_msg = json.load(out)
        print("Comparing expected event to actual event:\n\n")
        print("\n-=-=-=-=-=-=-=-=-\n")
        print(out_msg)
        print("\n-=-=-=-=-=-=-=-=-\n")
        print(next_event)
        print("\n-=-=-=-=-=-=-=-=-\n")
        assert json.loads(next_event) == out_msg

        if s3meta is not None:
            self.clean_up_remote_message(s3meta["bucket_name"], s3meta["key_name"])

    def test_basic(self) -> None:
        """test basic message"""
        self.transform_messages({"testcase": "basic"})
        self.transform_messages_streaming({"testcase": "basic"})

    def test_basic_no_config(self) -> None:
        """test basic no config message"""
        schemas: CumulusSchemas = {
            "input": "schemas/examples-messages.input.json",
            "output": "schemas/examples-messages-no-config.output.json",
        }
        self.transform_messages({"testcase": "basic_no_config", "schemas": schemas})
        self.transform_messages_streaming(
            {"testcase": "basic_no_config", "schemas": schemas}
        )

    def test_exception(self) -> None:
        """test remote message with exception"""
        self.transform_messages({"testcase": "exception"})
        self.transform_messages_streaming({"testcase": "exception"})

    def test_jsonpath(self) -> None:
        """test jsonpath message"""
        self.transform_messages({"testcase": "jsonpath"})
        self.transform_messages_streaming({"testcase": "jsonpath"})

    def test_meta(self) -> None:
        """test meta message"""
        self.transform_messages({"testcase": "meta"})
        self.transform_messages_streaming({"testcase": "meta"})

    def test_remote(self) -> None:
        """test remote message"""
        self.transform_messages({"testcase": "remote"})
        self.transform_messages_streaming({"testcase": "remote"})

    def test_templates(self) -> None:
        """test templates message"""
        self.transform_messages({"testcase": "templates"})
        self.transform_messages_streaming({"testcase": "templates"})

    def test_validation_failure_case(self) -> None:
        """test validation failure case"""
        try:
            self.transform_messages({"testcase": "invalidinput"})
        except AssertionError:
            return
        assert False

    def test_workflow_task_meta(self) -> None:
        """test meta.workflow task"""
        context: CumulusContext = {
            "functionName": "first_function",
            "invokedFunctionArn": "fakearn",
            "functionVersion": "1",
        }
        self.transform_messages({"testcase": "workflow_tasks", "context": context})
        self.transform_messages_streaming(
            {"testcase": "workflow_tasks", "context": context}
        )

    def test_multiple_workflow_tasks_meta(self) -> None:
        """test multiple meta.workflow_task entries"""
        context: CumulusContext = {
            "functionName": "second_function",
            "invokedFunctionArn": "fakearn2",
            "functionVersion": "2",
        }
        self.transform_messages(
            {"testcase": "workflow_tasks_multiple", "context": context}
        )
        self.transform_messages_streaming(
            {"testcase": "workflow_tasks_multiple", "context": context}
        )
