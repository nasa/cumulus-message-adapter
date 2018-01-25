# `cumulus-sled` Contract

`cumulus-sled` is a command-line interface for preparing and outputting Cumulus Messages for Cumulus Tasks. This contract defines how libraries should call `cumulus-sled` to integrate a task into a Cumulus Workflow.

Every Cumulus Task includes a business function. `cumulus-sled` and a language-specific library for interacting with `cumulus-sled` are required to integrate a business function as a Cumulus Task into a Cumulus Workflow.

`cumulus-sled` functions are invoked via the command line and read from stdin. Calling `./cumulus-sled <function_name>` should be followed by a json blob sent to stdin as detailed below.

Note: The `python ./cumulus-sled.zip` is interchangeable with `__main__.py` if the `cumulus-sled.zip` is up-to-date with the code.

```bash
# Cumulus Message or Cumulus Remote Message in:
python ./cumulus-sled.zip loadRemoteEvent
'{
  "event": <event_json>
}'

# Cumulus Message and Lambda Context in:
python ./cumulus-sled.zip loadNestedEvent
'{
  "event": <event_json>,
  "context": <context_json>
}'

# Call inner handler

# Send result as <handler_response_json> to produce Cumulus Message out:
python ./cumulus-sled.zip createNextEvent
'{
  "event": <event_json>,
  "handler_response": <handler_response_json>,
  "message_config": <message_config_json>
}'
```

These functions should be run in the order outlined above. The output of `loadRemoteEvent` should be sent as `<event_json>` to `createNextEvent`. The output of the `loadNestedEvent` should be fed to a "business function" and the output should be the `<handler_response_json>` sent to `createNextEvent`. More details on these values is provided in sections below.

## Cumulus Message schemas

Cumulus Messages come in 2 flavors: The full **Cumulus Message** and the **Cumulus Remote Message**. The Cumulus Remote Message points to a full Cumulus Message stored in S3 because of size limitations.

#### Cumulus Message example:

```json
{
  "workflow_config": {
    "Example": {
      "inlinestr": "prefix{meta.foo}suffix",
      "array": "{[$.meta.foo]}",
      "object": "{{$.meta}}"
    }
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

```json
{
  "replace": {
    "Bucket": "cumulus-bucket",
    "Key": "my-large-event.json"
  },
  "cumulus_meta": {}
}
```


## `loadRemoteEvent` input and output

### `loadRemoteEvent` input

* `<event_json>` to cumulus-sled `loadRemoteEvent` should be either a full Cumulus Message or a Cumulus Remote Message, as defined above.

### `loadRemoteEvent` output

loadRemote output is a full Cumulus Message as a json blob.

## `loadNestedEvent`

### `loadNestedEvent` input

* `<event_json>` to cumulus-sled `loadNestedEvent` should be a full Cumulus Message as defined above.

* `<context_json>` to cumulus-sled `loadNestedEvent` should be the context from the lambda.

**`loadNestedEvent` Details:**

`loadNestedEvent` requests metadata from the AWS Step Function API and uses that metadata to self-identify by determining which task in the workflow is "in-progress". This is roundabout way of the lambda asking `whoami` and will be removed once AWS updates the lambda context object.

The task name found associated with the running task is used to look up the task-specific configuration and construct the values of `config` and `messageConfig` fields sent to the business function. For example, if the current execution is associated with task named `'Task1'`, then the `config` object sent to the business function is the value of `workflow_config['Task1']` and the `messageConfig` object sent to the business function is the value of `workflow_config['Task1']['cumulus_message']`. These configurations are used to dispatch values to other parts of the Cumulus Message, via URL templates, which are required by the business function or `createNextEvent`.

### `loadNestedEvent` output

The output of `loadNestedEvent` is a json blob containing the keys `input`, `config` and `messageConfig`.


## `createNextEvent` input and output

### `createNextEvent` input

* `<handler_response_json>` is arbitrary json - whatever the "business function" returns.
* `<event_json>` is a full Cumulus Message and should be whatever is returned from `loadRemoteEvent`.
* `<message_config_json>` should be the value of the `messageConfig` key returned from `loadNestedEvent`.

### `createNextEvent` output

A Cumulus Message or a Cumulus Remote Message.
