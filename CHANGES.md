v1.0.4:
- fixed: added another layer of validation to `__getTaskNameFromExecutionHistory` function to prevent unexpected KeyErrors when interacting with the built-in retry mechanism in AWS State Machines [CUMULUS-426] PR #39
v0.0.4:
- fix relative import for compatability with Python3
