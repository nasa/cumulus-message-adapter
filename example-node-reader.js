const cp = require('child_process');

const child = cp.spawn('./cumulus-sled');

child.stdout.pipe(process.stdout);
child.stderr.pipe(process.stderr);

child.stdin.write('loadNestedEvent\n');
// example event object
child.stdin.write('{\"workflow_config\": {\"Example\": {\"inlinestr\": \"prefix{meta.foo}suffix\",\"array\": \"{[$.meta.foo]}\",\"object\": \"{{$.meta}}\"}},\"cumulus_meta\": {\"message_source\": \"sfn\",\"state_machine\": \"arn:aws:states:us-east-1:1234:stateMachine:MySfn\",\"execution_name\": \"MyExecution__id-1234\",\"id\": \"id-1234\"},\"meta\": {\"foo\": \"bar\"},\"payload\": {\"anykey\": \"anyvalue\"}}\n');
// example context object
child.stdin.write('{\"invokedFunctionArn\": \"arn:aws:lambda:us-west-2:123456789012:function:ExampleCloudFormationStackName-ExampleLambdaFunctionResourceName-AULC3LB8Q02F\"}\n');

child.stdin.end();
