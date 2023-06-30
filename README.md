# Cumulus Message Adapter

[![CircleCI](https://circleci.com/gh/nasa/cumulus-message-adapter.svg?style=svg)](https://circleci.com/gh/nasa/cumulus-message-adapter)

`cumulus-message-adapter` is a command-line interface for preparing and outputting Cumulus Messages for Cumulus Tasks. `cumulus-message-adapter` helps Cumulus developers integrate a task into a Cumulus Workflow.

Read more about how the `cumulus-message-adapter` works in the [CONTRACT.md](./CONTRACT.md).

## Releases

### Release Versions

Please note the following convention for release versions:

X.Y.Z: where:

* X is an organizational release that signifies the completion of a core set of functionality
* Y is a major version release that may include incompatible API changes and/or other breaking changes
* Z is a minor version that includes bugfixes and backwards compatible improvements

### Continuous Integration

[CircleCI](https://circleci.com/gh/nasa/cumulus-message-adapter) manages releases and release assets.

Whenever CircleCI passes on the master branch of cumulus-message-adapter and `message_adapter/version.py` has been updated with a version that doesn't match an existing tag, CircleCI will:

* Create a new tag with `tag_name` of the string in `message_adapter/version.py`
* Create a new release using the new tag, with a name equal to `tag_name` (equal to version).
* Build a `cumulus-message-adapter.zip` file and attach it as a release asset to the newly created release. The zip file is created using the [`Makefile`](./Makefile) in the root of this repository.

These steps are fully detailed in the [`.circleci/config.yml`](./.circleci/config.yml) file.

## Development

### Dependency Installation

```shell
pip install -r requirements-dev.txt
pip install -r requirements.txt
```

### Running Tests

Running tests requires [localstack](https://github.com/localstack/localstack).

Tests only require localstack running S3, which can be initiated with the following command:

```shell
SERVICES=s3 localstack start
```

And then you can check tests pass with the following nosetests command:

```shell
CUMULUS_ENV=testing nosetests -v -s
```

### Linting

```shell
pylint message_adapter
```

### Contributing

If changes are made to the codebase, you can create the cumulus-message-adapter zip archive for testing libraries that require it:

```shell
make clean
make cumulus-message-adapter.zip
```

Then you can run some integration tests:

```shell
./examples/example-node-message-adapter-lib.js
```

### Troubleshooting

* Error: "DistutilsOptionError: must supply either home or prefix/exec-prefix — not both" when running `make cumulus-message-adapter.zip`
  * [Solution](https://stackoverflow.com/a/24357384)
