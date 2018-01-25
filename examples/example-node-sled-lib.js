#!/usr/bin/env node
const assert = require('assert');
const cp = require('child_process');
const fs = require('fs');

// Set CUMULUS_ENV=testing so we don't make real requests to AWS APIs
const env = Object.create(process.env);
env.CUMULUS_ENV = 'testing';

function loadJsonFromFile(fileName) {
  return fs.readFileSync(fileName, 'utf8').replace(/(\s)/gm,"");
}

/**
* Integration Test for loadRemoteEvent
*/
var child = cp.spawn('python', ['./cumulus-sled.zip', 'loadRemoteEvent'], { env: env });

child.stderr.pipe(process.stderr);

// example event object
const eventObject = JSON.parse(loadJsonFromFile('examples/messages/sfn.input.json'));

child.stdin.write(JSON.stringify({'event': eventObject}));
child.stdin.end();

child.stdout.on('data', (data) => {
  const expectedResponse = eventObject;
  assert.deepEqual(JSON.parse(data.toString()), expectedResponse);
  console.log('loadRemoteEvent test passed');
});

/**
* WIP Integration Test for loadNestedEvent
*/

/**
* This will fail with "Lookup error: 'events'". * At the moment localstack
* doesn't support step functions so there is no way to do a complete integration
* test :(.
* TODO(aimee) Mock the response from AWS Step Functions API.
*/
var child = cp.spawn('python', ['./cumulus-sled.zip', 'loadNestedEvent'], { env: env });

child.stderr.pipe(process.stderr);

// example context object
const contextObject = JSON.parse(loadJsonFromFile('examples/contexts/simple-context.json'));

const fullInput = JSON.stringify({'event': eventObject, 'context': contextObject});
child.stdin.write(fullInput);
child.stdin.end();

/*
* Integration Test for createNextEvent 
*/
var child = cp.spawn('python', ['./cumulus-sled.zip', 'createNextEvent']);

child.stderr.pipe(process.stderr);

// example handler response
const exampleResponseObject = JSON.parse(loadJsonFromFile('examples/responses/meta.response.json'));

// example event object
const eventWithMetaObject = JSON.parse(loadJsonFromFile('examples/messages/meta.input.json'));

// example messageConfigObject
const messageConfig = eventWithMetaObject.workflow_config['Example'].cumulus_message;

child.stdin.write(JSON.stringify({
  'handler_response': exampleResponseObject,
  'event': eventWithMetaObject,
  'message_config': messageConfig
}));

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
