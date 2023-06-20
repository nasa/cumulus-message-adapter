
# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).
## [Unreleased]

## Updated

- removed extraneous dependencies from requests.txt
  - typed-ast
  - six (remains as a subdependency)


## [v2.0.2] 2022-01-10

## Fixed

- **CUMULUS-2751**

  - Resolve inter-compatibility bug/regression with cumulus-message-adapter-js, as the current releases strictly check the message return schema 
    for the existence of a config object.   This fix restores the original behavior.

## [v2.0.1] 2022-01-07

### Fixed

- **CUMULUS-2751**
  - Fix regression in 2.0.0 that caused tasks without `task_config` defined cause CMA to fail

## [v2.0.0] 2021-12-17

### BREAKING CHANGES

- **CUMULUS-2751**
  - Changes the key for the values populated in meta.workflow_tasks from the step function node name to an internally indexed integer string
  - Updates `load_nested_event` to no longer do a legacy task name lookup from either the step function API or `cumulus_meta` for configuration from `event.workflow_config`

## [v1.3.1] 2021-11-17

### Updated

- **CUMULUS-2751**
  - Update CMA logging to explicitly flush stderr on log write
  - Add diagnostic logging to CMA 'steps'

## [v1.3.0] 2020-02-14

### BREAKING CHANGES

- **CUMULUS-1896**
  - CMA precompiled binary files are now copied into a subdirectory `./cma_bin`.  Clients who utilize the pre-compiled binary should update their pathing expectations to make use of that directory. If you are using the CMA via [`cumulus-message-adapter-js`](https://github.com/nasa/cumulus-message-adapter-js), then this change is handled for you transparently as of version 1.2.0.

### Added

- **CUMULUS-1896**
  - Added a 'streaming' mode to the CMA.   This will allow client libraries to avoid requiring three subprocess/python invocations when running the CMA commands in sequence, thus lowering
    the overhead of utilizing the CMA.

## [v1.2.1] 2020-04-21

### Updated

- Updated deployment to not bundle all associated .so files for pyinstaller in the executable.   This results in slightly better performance/memory requirements at the cost of having all of the associated .so files in the layer directory structure. This change should not impact functionality.

## [v1.2.0] 2020-02-14

### BREAKING CHANGES
- **CUMULUS-1486**
  - Removed all python 2 support.

## [v1.1.3]

### Fixed

- Removed unsafe use of `exec` and `eval` in `message_adapter.__assignJsonPathValue`

## [v1.1.2] - 2019-12-13

### Added

- Updated release process to utilize [pyinstaller](https://www.pyinstaller.org/)[CUMULUS-1447] to create a pre-package python+CMA release binary compatible with AWS Linux 2, added as the executable `cma` to the release package.


## [v1.1.1] - 2019-10-03

### Removed

- Removed deprecated function `loadRemoteEvent` and updated tests.

### Fixed

- Fixed issue where remote message stored configuration values would overwrite the config params in the step reading the remote message [CUMULUS-1447]

## [v1.1.0] - 2019-09-16

*Note*:this release was pulled from pypi/releases on github.   Please utilize v1.1.1

### BREAKING CHANGES
### Added
- Updated remote message behavior to be manually configured by step function parameters *only*, this removes the default automatic remote message behavior.  [CUMULUS-1447]

## [v1.0.13] - 2018-11-08

### Added
- Add `cumulus_context` attribute from `cumulus_meta[cumulus_context]` to property `cumulus_config` of task event message [CUMULUS-906]

## [v1.0.12] - 2018-09-28

### Fixed
- Increase number of configured retries in case of sfn ClientError.[CUMULUS-920]

## [v1.0.11] - 2018-09-18

### Fixed
- Fixed rare case where `"exception": null` obscured failures.

## [v1.0.10] - 2018-09-12

### Changed
- Exceptions that occur are now stored in the remote message.

### Fixed
- Exceptions stored in the local message (e.g. by the client libraries) are carried through when the remote message is loaded.

## [v1.0.9] - 2018-08-17

### Fixed
- Fix invocation as subprocess.

## [v1.0.8] - 2018-08-16

### Fixed
- Improve backwards compatibility and add tests.

## [v1.0.7] - 2018-08-16

### Fixed
- Restore backwards compatibility.

## [v1.0.6] - 2018-08-16

### Added
- Record task name and version in message meta if available.

## [v1.0.5] - 2018-07-18

### Added
- add `cumulus_config` property with two attributes `state_machine` and `execution_name` to task event message [CUMULUS-685]

## [v1.0.4] - 2018-03-21

### Fixed
- added another layer of validation to `__getTaskNameFromExecutionHistory` function to prevent unexpected KeyErrors when interacting with the built-in retry mechanism in AWS State Machines [CUMULUS-426] PR #39

## [v1.0.3] - 2018-03-20

### Added
- docs: add troubleshooting section to readme

### Fixed
- fix `sys.exit` indentation to fix lookup errors throwing JSON.parse errors in cumulus-message-adapter-js#index.js because main.py was exiting 0 instead of 1

## [v1.0.2] - 2018-02-28

### Fixed
- fix pypi release to use correct virtualenv

## [v1.0.1] - 2018-02-26

### Added
- add tests for __main__.py

### Changed
- create pypi and github release with python 2.7 instead of python 3.6

## [v1.0.0] - 2018-02-23

### Added
- circleci:
  - run tests in both python 2.7 and 3.6
  - publish to pypi

### Fixed
- parse inline jsonpath templating
- python 3 compatibility fixes

## [v0.0.10] - 2018-02-16

### Fixed
- fix indentation to fix missing result output from __main__.py

## [v0.0.9] - 2018-02-15

### Fixed
- fix indenting in __main__.py to fix catching `LookupError` exceptions

### Changed
- update boto3 dependency from >=1.5.12 to >=1.5.27

## [v0.0.8] - 2018-02-15

### Fixed
- get dependencies from requirements file

## [v0.0.7] - 2018-02-14

### Fixed
- update fix json schema validation to read from task root directory by default

## [v0.0.6] - 2018-02-13

### Added
- add jsonschema validation
- docs: descriptions of cumulus message schemas and the `createNextEvent` output

## [v0.0.5] - 2018-02-13

### Changed
- change bucket location from `cumulus_meta.buckets.internal` to `cumulus_meta.system_bucket`

## [v0.0.4] - 2018-02-13

### Added

- Add Makefile for zip creation

### Fixed
- small test fixes
- python 3 compatibility

## [v0.0.3] - 2018-02-01

### Fixed
- circleci: only build on master

## [v0.0.2] - 2018-02-01

### Added
- Updates `.circleci/config.yml` to tag, release and build `cumulus-message-adapter.zip` whenever `message_adapter/version.py` gets updated.
- add CONTRIBUTING.md file
- retrieve invoked function arn from lambda context

## [v0.0.1] - 2018-01-25

### Added
- Initial release

[Unreleased]: https://github.com/nasa/cumulus-message-adapter/compare/v1.1.2...HEAD
[v1.1.2]: https://github.com/nasa/cumulus-message-adapter/compare/v1.1.1...v1.1.2
[v1.1.1]: https://github.com/nasa/cumulus-message-adapter/compare/v1.1.1...v1.1.2
[v1.1.0]: https://github.com/nasa/cumulus-message-adapter/compare/v1.0.13...v1.1.1
[v1.0.13]: https://github.com/nasa/cumulus-message-adapter/compare/v1.0.12...v1.0.13
[v1.0.5]: https://github.com/nasa/cumulus-message-adapter/compare/v1.0.4...v1.0.5
[v1.0.4]: https://github.com/nasa/cumulus-message-adapter/compare/v1.0.3...v1.0.4
[v1.0.3]: https://github.com/nasa/cumulus-message-adapter/compare/v1.0.2...v1.0.3
[v1.0.2]: https://github.com/nasa/cumulus-message-adapter/compare/v1.0.1...v1.0.2
[v1.0.1]: https://github.com/nasa/cumulus-message-adapter/compare/v1.0.0...v1.0.1
[v1.0.0]: https://github.com/nasa/cumulus-message-adapter/compare/v0.0.10...v1.0.0
[v0.0.10]: https://github.com/nasa/cumulus-message-adapter/compare/v0.0.9...v0.0.10
[v0.0.9]: https://github.com/nasa/cumulus-message-adapter/compare/v0.0.8...v0.0.9
[v0.0.8]: https://github.com/nasa/cumulus-message-adapter/compare/v0.0.7...v0.0.8
[v0.0.7]: https://github.com/nasa/cumulus-message-adapter/compare/v0.0.6...v0.0.7
[v0.0.6]: https://github.com/nasa/cumulus-message-adapter/compare/v0.0.5...v0.0.6
[v0.0.5]: https://github.com/nasa/cumulus-message-adapter/compare/v0.0.4...v0.0.5
[v0.0.4]: https://github.com/nasa/cumulus-message-adapter/compare/v0.0.3...v0.0.4
[v0.0.3]: https://github.com/nasa/cumulus-message-adapter/compare/v0.0.2...v0.0.3
[v0.0.2]: https://github.com/nasa/cumulus-message-adapter/compare/v0.0.1...v0.0.2
[v0.0.1]: https://github.com/nasa/cumulus-message-adapter/compare/35f1cb9fcdb3f3e68f49be92ed84f6d7bad4cfb2...v0.0.1
