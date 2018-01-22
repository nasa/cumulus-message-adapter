# `cumulus-sled` Contract

`cumulus-sled` is a command-line interface for preparing and outputting Cumulus Messages for Cumulus Tasks. This contract defines how libraries should call `cumulus-sled` to integrate a task into a Cumulus Workflow.

Every Cumulus Task includes a business function. `cumulus-sled` and a language-specific library for interacting with `cumulus-sled` are required to integrate a business function as a Cumulus Task into a Cumulus Workflow.

**NOTE: This should be updated to call `cumulus-sled.zip` once we have created that package.**

All `cumulus-sled` functions below are invoked via command line:

```
python ./message/message.py loadRemoteEvent '<event_json>'
python ./message/message.py loadNestedEvent '<event_json>' '<context_json>'
python ./message/message.py createNextEvent '<nested_event_json>' '<event_json>' '<message_config_json>'
```

These functions should be run in the order outlined above, but the output of the `loadNestedEvent` should be fed to a "business function" and the output should be the `<nested_event_json>` sent to `createNextEvent`.

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


## `loadRemote` input and output

### `loadRemote` input

* `<event_json>` to cumulus-sled `loadRemote` should be either a full Cumulus Message or a Cumulus Remote Message, as defined above


### `loadRemote` output

loadRemote output is a full Cumulus Message as defined returned as a json blob.

## `loadNestedEvent`

### `loadNestedEvent` input

* `<event_json>` to cumulus-sled `loadNestedEvent` should be a full Cumulus Message as defined above.

* `<context_json>` to cumulus-sled `loadNestedEvent` should be the context from the lambda.

**Details:** `loadNestedEvent` requests metadata from the AWS Step Function API and uses that metadata to self-identify what is the running task - something like asking `Who am I?`. The task name found associated with the running task is used to look up the task-specific `workflow_config` configuration. This configuration is used to template variables for input and config keys which are meant for submission to the "business function".


### `loadNestedEvent` output

The output of `loadNestedEvent` is a json blob containing the keys `input`, `config` and `messageConfig`.

## `createNextEvent` input and output

### `createNextEvent` input

* `<nested_event_json>` is arbitrary json - whatever the "business function" returns.
* `<event_json>` is a full Cumulus Message and should be whatever is returned from `loadRemoteEvent`.
* `<message_config_json>` should be the value of the `messageConfig` key returned from `loadNestedEvent`.

### `createNextEvent` output

A Cumulus Message or a Cumulus Remote Message.
