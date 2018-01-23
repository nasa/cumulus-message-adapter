#!/usr/bin/env node
const assert = require('assert');
const cp = require('child_process');
const fs = require('fs');

// Set ENV=testing so we don't make real requests to AWS APIs
const env = Object.create(process.env);
env.ENV = 'testing';

function loadJsonFromFile(fileName) {
  return fs.readFileSync(fileName, 'utf8').replace(/(\s)/gm,"");
}
/**
* WIP Integration Test for loadNestedEvent
*/

/**
* This will fail with "Lookup error: 'events'". * At the moment localstack
* doesn't support step functions so there is no way to do a complete integration
* test :(.
* TODO(aimee) Mock the response from AWS Step Functions API.
*/
var child = cp.spawn('./cumulus-sled', ['loadNestedEvent'], { env: env });

child.stderr.pipe(process.stderr);

// example event object
const eventJsonContent = loadJsonFromFile('examples/messages/sfn.input.json');
child.stdin.write(eventJsonContent + '\n');

// example context object
const contextJsonContent = loadJsonFromFile('examples/contexts/simple-context.json');
child.stdin.write(contextJsonContent + '\n');
child.stdin.end();

/*
* Integration Test for createNextEvent 
*/
var child = cp.spawn('./cumulus-sled', ['createNextEvent']);

child.stderr.pipe(process.stderr);

// example handler response
const exampleResponseJson = loadJsonFromFile('examples/responses/meta.response.json');
child.stdin.write(exampleResponseJson + '\n');
// example event object
const eventWithMetaJson = loadJsonFromFile('examples/messages/meta.input.json');
child.stdin.write(eventWithMetaJson + '\n');
// example messageConfigObject
const eventWithMetaObject = JSON.parse(eventWithMetaJson);
const messageConfig = eventWithMetaObject.workflow_config['Example'].cumulus_message;
child.stdin.write(JSON.stringify(messageConfig) + '\n');

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
