# Cumulus Message Adapter

[![CircleCI](https://circleci.com/gh/cumulus-nasa/cumulus-message-adapter.svg?style=svg)](https://circleci.com/gh/cumulus-nasa/cumulus-message-adapter)

## Development

### Dependency Installation

    $ pip install -r requirements-dev.txt
    $ pip install -r requirements.txt

### Running Tests

Running tests requires [localstack](https://github.com/localstack/localstack).

Tests only require localstack running S3, which can be initiated with the following command:

```
$ SERVICES=s3 localstack start
```

And then you can check tests pass with the following nosetests command:

```
$ CUMULUS_ENV=testing nosetests -v -s
```

### Linting

     $ pylint message

### Contributing

If changes are made to the codebase, you can create the cumulus-message-adapter zip archive for testing libraries that require it:

```bash
$ make clean
$ make cumulus-message-adapter.zip
```

Then you can run some integration tests:

```bash
./examples/example-node-message-adapter-lib.js 
```
