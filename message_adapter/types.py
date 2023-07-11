from __future__ import annotations
from typing import Dict, Any, Optional, List, Union, Literal
from typing_extensions import TypedDict, NotRequired

GenericCumulusSubObject = Optional[Union[
    str,
    List['GenericCumulusSubObject'],
    Dict[str, 'GenericCumulusSubObject'],
]]

GenericCumulusObject = Dict[str, GenericCumulusSubObject]


class CumulusInputConfig(TypedDict):
    input: NotRequired[str]


class CumulusTaskConfig(TypedDict):
    inlinestr: NotRequired[str]
    array: NotRequired[str]
    object: NotRequired[str]
    cumulus_message: NotRequired[CumulusInputConfig]


class TaskMeta(TypedDict):
    name: str
    version: str
    arn: str


class CumulusConfig(TypedDict):
    state_machine: NotRequired[str]
    execution_name: NotRequired[str]
    cumulus_context: NotRequired[str]

class CumulusMeta(CumulusConfig):
    message_source: NotRequired[str]
    id: NotRequired[str]
    system_bucket: NotRequired[str]
    message_bucket: NotRequired[str]
    workflow_tasks: NotRequired[Dict[str, TaskMeta]]


class RemoteReplace(TypedDict):
    Bucket: str
    Key: str
    TargetPath: str


class ReplacementConfig(TypedDict):
    Path: str
    FullMessage: NotRequired[bool]
    MaxSize: NotRequired[int]
    TargetPath: NotRequired[str]


class CumulusMessage(TypedDict):
    cumulus_meta: NotRequired[CumulusMeta]
    meta: NotRequired[CumulusMeta]
    payload: NotRequired[GenericCumulusObject]
    exception: NotRequired[Optional[str]]
    task_config: NotRequired[CumulusTaskConfig]
    replace: NotRequired[RemoteReplace]
    ReplaceConfig: NotRequired[ReplacementConfig]
    cumulus_config: NotRequired[CumulusConfig]
    messageConfig: NotRequired[CumulusInputConfig]
    cma: NotRequired[CumulusEventWrapper]

class CumulusEventWrapper(CumulusMessage):
    event: CumulusMessage


# class UnMassagedCumulusMessage(CumulusMessage):
#     cma: NotRequired[CumulusEventWrapper]


class CumulusContext(TypedDict):
    function_name: NotRequired[str]
    functionName: NotRequired[str]
    function_version: NotRequired[str]
    functionVersion: NotRequired[str]
    invoked_function_arn: NotRequired[str]
    invokedFunctionArn: NotRequired[str]
    activityArn: NotRequired[str]


class CumulusHandlerResponse(TypedDict):
    pass


class SDConfig(TypedDict):
    source: str
    destination: str


class CumulusMessageConfig(TypedDict):
    outputs: NotRequired[List[SDConfig]]


class AllInput(TypedDict):
    handler_response: GenericCumulusObject
    event: CumulusMessage
    schemas: NotRequired[GenericCumulusObject]
    context: NotRequired[CumulusContext]
    message_config: NotRequired[CumulusMessageConfig]

