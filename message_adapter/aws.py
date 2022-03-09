""" Determines the correct AWS endpoint for AWS services """
import os
from boto3 import resource

def localhost_s3_url():
    """ Returns configured LOCALSTACK_HOST url or default for localstack s3 """
    if 'LOCALSTACK_HOST' in os.environ:
        s3_url = f"http://{os.environ['LOCALSTACK_HOST']}:4566"
    else:
        s3_url = 'http://localhost:4566'
    return s3_url


def s3():
    """ Determines the endpoint for the S3 service """

    if ('CUMULUS_ENV' in os.environ) and (os.environ['CUMULUS_ENV'] == 'testing'):
        return resource(
            service_name='s3',
            endpoint_url=localhost_s3_url(),
            aws_access_key_id='my-id',
            aws_secret_access_key='my-secret',
            region_name='us-east-1',
            verify=False
        )
    return resource('s3')

def _get_sfn_execution_arn_by_name(state_machine_arn, execution_name):
    """
    * Given a state machine arn and execution name, returns the execution's ARN
    * @param {string} state_machine_arn The ARN of the state machine containing the execution
    * @param {string} execution_name The name of the execution
    * @returns {string} The execution's ARN
    """
    return (':').join([state_machine_arn.replace(':stateMachine:', ':execution:'),
                       execution_name])


def _get_task_name_from_execution_history(execution_history, arn):
    """
    * Given an execution history object returned by the StepFunctions API and an optional
    * Activity or Lambda ARN returns the most recent task name started for the given ARN,
    * or if no ARN is supplied, the most recent task started.
    *
    * IMPORTANT! If no ARN is supplied, this message assumes that the most recently started
    * execution is the desired execution. This WILL BREAK parallel executions, so always supply
    * this if possible.
    *
    * @param {dict} executionHistory The execution history returned by getExecutionHistory,
    * assumed to be sorted so most recent executions come last
    * @param {string} arn An ARN to an Activity or Lambda to find. See "IMPORTANT!"
    * @throws If no matching task is found
    * @returns {string} The matching task name
    """
    events_by_id = {}

    # Create a lookup table for finding events by their id
    for event in execution_history['events']:
        events_by_id[event['id']] = event

    for step in execution_history['events']:
        # Find the ARN in the history (the API is awful here).  When found, return its
        # previousEventId's (TaskStateEntered) name
        lambda_of_type_and_matching_arn = (
            (step['type'] == 'LambdaFunctionScheduled' and
             step['lambdaFunctionScheduledEventDetails']['resource'] == arn) or
            (step['type'] == 'ActivityScheduled' and
             step['activityScheduledEventDetails']['resource'] == arn))

        if (arn is not None and lambda_of_type_and_matching_arn and
                'stateEnteredEventDetails' in events_by_id[step['previousEventId']]):
            return events_by_id[step['previousEventId']]['stateEnteredEventDetails']['name']

        if step['type'] == 'TaskStateEntered':
            return step['stateEnteredEventDetails']['name']

    raise LookupError('No task found for ' + arn)
