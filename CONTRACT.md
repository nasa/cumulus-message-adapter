# `cumulus-message-adapter` Contract

`cumulus-message-adapter` is a command-line interface for preparing and outputting Cumulus Messages for Cumulus Tasks. This contract defines how libraries should call `cumulus-message-adapter` to integrate a task into a Cumulus Workflow.

Every Cumulus Task includes a business function. `cumulus-message-adapter` and a language-specific library for interacting with `cumulus-message-adapter` are required to integrate a business function as a Cumulus Task into a Cumulus Workflow.

## Command Interface

`cumulus-message-adapter` functions are invoked via the command line and read from stdin. Calling `./cumulus-message-adapter <function_name>` should be followed by a json blob sent to stdin as detailed below.

Note: The `python ./cumulus-message-adapter.zip` is interchangeable with `__main__.py` if the `cumulus-message-adapter.zip` is up-to-date with the code.

```bash
# Cumulus Message or Cumulus Remote Message in:
python ./cumulus-message-adapter.zip loadAndUpdateRemoteEvent
'{
  "event": <event_json>
}'

# Cumulus Message, Lambda Context, and schemas in:
python ./cumulus-message-adapter.zip loadNestedEvent
'{
  "event": <event_json>,
  "context": <context_json>,
  "schemas": <schemas_json>
}'

# Call inner handler

# Send result as <handler_response_json> to produce Cumulus Message out:
python ./cumulus-message-adapter.zip createNextEvent
'{
  "event": <event_json>,
  "handler_response": <handler_response_json>,
  "message_config": <message_config_json>,
  "schemas": <schemas_json>
}'
```

These functions should be run in the order outlined above. The output of `loadAndUpdateRemoteEvent` should be sent as `<event_json>` to `createNextEvent`. The output of the `loadNestedEvent` should be fed to a "business function" and the output should be the `<handler_response_json>` sent to `createNextEvent`. More details on these values is provided in sections below.

## Streaming Interface

The CMA also offers a streaming interface that utilizes the commands listed above, but allows for a command/response to be issued without incurring the overhead of loading a subprocess/reloading python dependencies repeatedly:

```bash
python ./cumulus_message_adapter.zip stream
```

With the above invocation, commands can be run by outputting to STDIN in the following format:

```text
COMMAND
{ JSON PAYLOAD (may be multi-line) }
<EOC>
```

The CMA will respond with a JSON response string if the command is successful, else throw an error and output to STDERR as with the single-command invocation:

```text
{ JSON OUTPUT }
<EOC>
```

To signal an end to the process, send the following input:

```text
<EXIT>
```

## Cumulus Message schemas

Cumulus Messages come in 2 flavors: The full **Cumulus Message** and the **Cumulus Remote Message**.

 Because of the potential size of a Cumulus message, mainly the `"payload"` field, a task can be set via configuration to store a portion of its output on S3 with a message key `Remote Message` that defines how to retrieve it and an empty JSON object `{}` in its place.   If the portion of the message targeted exceeds the configured `MaxSize` (defaults to 0 bytes) it will be written to S3.

### Remote Message Configuration

The CMA remote message functionality can be configured using parameters in several ways:

**Please note** that the parameter `event.$: '$'` is *required* when using Step Function parameters to configure the CMA.

#### Partial Message

Setting the `Path`/`Target` path in the `ReplaceConfig` parameter (and optionally a non-default `MaxSize`)

```yaml
DiscoverGranules:
  Parameters:
    cma:
      event.$: '$'
      ReplaceConfig:
        MaxSize: 1
        Path: '$.payload'
        TargetPath: '$.payload'
```

will result in any `payload` output larger than the `MaxSize` (in bytes)  to be written to S3.  The CMA will then mark that the key has been replaced via a `replace` key on the event. When the CMA picks up the `replace` key in future steps, it will attempt to retrieve the output from S3 and write it back to `payload`.

Note that you can optionally use a different `TargetPath` than `Path`, however as the target is a JSON path there must be a key to target for replacement in the output of that step.    Also note that the JSON path specified must target *one* node, otherwise the CMA will error, as it does not support multiple replacement targets.

If `TargetPath` is omitted, it will default to the value for `Path`.

#### Full Message

Setting the following parameters for a lambda:

```yaml
DiscoverGranules:
  Parameters:
    cma:
      event.$: '$'
      ReplaceConfig:
        FullMessage: true
```

will result in the CMA assuming the entire inbound message should be stored to S3 if it exceeds the default max size.

This is effectively the same as doing:

```yaml
DiscoverGranules:
  Parameters:
    cma:
      event.$: '$'
      ReplaceConfig:
        MaxSize: 10000
        Path: '$'
        TargetPath: '$'
```

#### Cumulus Message example:

```json
{
  "task_config": {
    "inlinestr": "prefix{meta.foo}suffix",
    "array": "{[$.meta.foo]}",
    "object": "{{$.meta}}"
  },
  "cumulus_meta": {
    "message_source": "sfn",
    "state_machine": "arn:aws:states:us-east-1:1234:stateMachine:MySfn",
    "execution_name": "MyExecution__id-1234",
    "id": "id-1234"
  },
  "meta": {
    "foo": "bar"
  },
  "payload": {
    "anykey": "anyvalue"
  }
}
```

#### Cumulus Remote Message example:

The message may contain a reference to an S3 Bucket, Key and TargetPath as follows:

```json
{
  "replace": {
    "Bucket": "cumulus-bucket",
    "Key": "my-large-event.json",
    "TargetPath": "$"
  },
  "cumulus_meta": {}
}
```

### Task Configuration

Task configuration (corresponding to `task_config` shown above) is used to construct the `config` object sent to the business function.

Task configuration can be defined by specifying Parameters on the Lambda Function, e.g.:

```yaml
DiscoverGranules:
  Parameters:
    cma:
      event.$: '$'
      task_config:
        foo: '{{$.meta.foo}}'
        bar: 'fixedValue'
```

## `loadAndUpdateRemoteEvent` input and output

### `loadAndUpdateRemoteEvent` input

* `<event_json>` to cumulus-message-adapter `loadAndUpdateRemoteEvent` should be either a full Cumulus Message or a Cumulus Remote Message, as defined above.

* `<context_json>` to cumulus-message-adapter `loadAndUpdateRemoteEvent` should be the context from the lambda.

### `loadAndUpdateRemoteEvent` output

loadAndUpdateRemote output is a full Cumulus Message as a json blob.

## `loadNestedEvent`

### `loadNestedEvent` input

* `event` should be a full Cumulus Message as defined above, with optional `task_config` section defined.

### `loadNestedEvent` Details

`loadNestedEvent` will read the configuration specified in `task_config`, and return a response object with:

* `input` object for the task function based on the `task_config`.  This defaults to the passed in `payload` object if nothing is specified for the input.
* `config` object based on the configured `task_config`.
* `messageConfig` object if `cumulus_message` is defined in the `task_config`
* `cumulus_config` object containing internal configuration from the `cumulus_meta` key on the event, if provided.

### `loadNestedEvent` output

The output of `loadNestedEvent` is a json blob containing the keys `input`, `config`, `cumulus_config` and `messageConfig`.

## `createNextEvent` input and output

### `createNextEvent` input

* `<handler_response_json>` is arbitrary json - whatever the "business function" returns.
* `<event_json>` is a full Cumulus Message and should be whatever is returned from `loadAndUpdateRemoteEvent`.
* `<message_config_json>` should be the value of the `messageConfig` key returned from `loadNestedEvent`.
* `<schemas_json>` should be an object with filepaths to the json schema for the `output` that a "business function" expects to return.

An example of the `<schemas_json>` that should be passed to `createNextEvent`:

```json
{
  "output": "/filepath/to/output.json"
}
```

### `createNextEvent` output

A Cumulus Message or a Cumulus Remote Message. When a task output message is too big, the Cumulus Message Adapter will store the message to S3 Bucket under `$.cumulus_meta.system_bucket`, and return a new message with an S3 reference as in the input example.

## Error Handling

Errors raised during execution of `cumulus-message-adapter` functions are written to stderr. These errors are integration errors or bugs in the `cumulus-message-adapter` code and should be re-raised by libraries so the root cause can be fixed.

Errors raised during invocation of task application code, may either be the result of a misconfiguration, bug, or task execution error. Libraries should raise errors in the case the origin is misconfiguration or a bug since this should be fixed in source code.

In case there is a task execution error - such as an AWS client error - the error should be caught by the library and returned as an additional `exception` field alongside the full event returned from `loadAndUpdateRemoteEvent`. For example, say:

1. `loadRemoveEvent` successfully returns full Cumulus Message
2. `loadNestedEvent` successfully returns object with input, config and messageConfig keys
3. The library calls task application code an error is thrown
4. Error is caught by library code and library handler returns the full Cumulus Message plus an exception field:

```json
{
  "task_config": {},
  "cumulus_meta": {},
  "meta": {
    "foo": "bar"
  },
  "payload": null,
  "exception": "WorkflowError"
}
```
