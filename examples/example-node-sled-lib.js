#!/usr/bin/env node
const assert = require('assert');
const cp = require('child_process');

// So we don't make real requests to AWS APIs, set ENV=testing
const env = Object.create(process.env);
env.ENV = 'testing';

// WIP Integration Test for loadNestedEvent - will fail with "Lookup error:
// 'events'".
// At the moment localstack doesn't support step functions so there is
// no way to do a complete integration test :(
var child = cp.spawn('./cumulus-sled', ['loadNestedEvent'], { env: env });

child.stderr.pipe(process.stderr);

// example event object
// TODO(aimee): Write and load these from a file.
child.stdin.write('{\"workflow_config\": {\"Example\": {\"inlinestr\": \"prefix{meta.foo}suffix\",\"array\": \"{[$.meta.foo]}\",\"object\": \"{{$.meta}}\"}},\"cumulus_meta\": {\"message_source\": \"sfn\",\"state_machine\": \"arn:aws:states:us-east-1:1234:stateMachine:MySfn\",\"execution_name\": \"MyExecution__id-1234\",\"id\": \"id-1234\"},\"meta\": {\"foo\": \"bar\"},\"payload\": {\"anykey\": \"anyvalue\"}}\n');
// example context object
child.stdin.write('{\"invokedFunctionArn\": \"arn:aws:lambda:us-west-2:123456789012:function:ExampleCloudFormationStackName-ExampleLambdaFunctionResourceName-AULC3LB8Q02F\"}\n');

child.stdin.end();

// Integration Test for createNextEvent 
var child = cp.spawn('./cumulus-sled', ['createNextEvent']);

child.stderr.pipe(process.stderr);

// example handler response
child.stdin.write('{\"input\": {\"anykey\": \"innerValue\"}}\n');
// example event object
child.stdin.write('{\"workflow_config\": {\"Example\": {\"bar\": \"{meta.foo}\",\"cumulus_message\": {\"outputs\": [{\"source\": \"{{$}}\",\"destination\": \"{{$.payload}}\"},{\"source\": \"{{$.input.anykey}}\",\"destination\": \"{{$.meta.baz}}\"}]}}},\"cumulus_meta\": {\"task\": \"Example\",\"message_source\": \"local\",\"id\": \"id-1234\"},\"meta\": {\"foo\": \"bar\"},\"payload\": {\"anykey\": \"anyvalue\"}}\n');
// example messageConfigObject
child.stdin.write('{\"outputs\": [{\"source\": \"{{$}}\",\"destination\": \"{{$.payload}}\"},{\"source\": \"{{$.input.anykey}}\",\"destination\": \"{{$.meta.baz}}\"}]}\n');

child.stdin.end();
child.stdout.on('data', (data) => {
  const expectedResponse = {
    "cumulus_meta": {
      "message_source": "local",
      "task": "Example",
      "id": "id-1234"
    },
    "meta": {
      "foo": "bar",
      "baz": "innerValue"
    },
    "exception": "None",
    "payload": {
      "input": {
        "anykey": "innerValue"
      }
    },
    "workflow_config": {
      "Example": {
        "bar": "{meta.foo}",
        "cumulus_message": {
          "outputs": [{
            "source": "{{$}}",
            "destination": "{{$.payload}}"
          }, {
            "source": "{{$.input.anykey}}",
            "destination": "{{$.meta.baz}}"
          }]
        }
      }
    }
  }
  assert.deepEqual(JSON.parse(data.toString()), expectedResponse);
  console.log('createNextEvent test passed');
});
