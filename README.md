# Cumulus Sled Message Transformation

[![CircleCI](https://circleci.com/gh/cumulus-nasa/cumulus-sled.svg?style=svg)](https://circleci.com/gh/cumulus-nasa/cumulus-sled)

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
$ ENV=testing nosetests -v -s
```

### Linting

     $ pylint message
