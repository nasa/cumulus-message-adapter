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
EAGER_SERVICE_LOADING=1 SERVICES=s3 localstack start
```

And then you can check tests pass with the following nosetests command:

```shell
CUMULUS_ENV=testing nose2 -v
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

Before any changes are finalized and released, they should be tested by packaging the cumulus-message-adapter zip archive and testing it in a lambda environment, as that is where it will be utilized.

#### Packaging

Packaging the zip file is probably best done in an environment that closely matches the lambda environment in which it will be run and contains the current Python version, so we are using an AWS Python Lambda image. Certain packages need to be installed, and using a virtual environment is important due to Python pathing.

```shell
docker run -v ~/projects/cumulus-message-adapter/:/cma/ -v ~/tmp/:/tmp/ -v ~/amazon/:/home/amazon/ -it --entrypoint /bin/bash amazon/aws-lambda-python:3.10
yum install -y make binutils zip
cd /cma
pip install --user virtualenv
~/.local/bin/virtualenv ~/venv310
. ~/venv310/bin/activate
pip install .
make clean
make cumulus-message-adapter.zip
```

#### Testing the package in a Lambda Environment

Once the package is created, it should be tested in a Lambda environment. Before doing so, it may be helpful to run the package in the container it was packaged in, immediately after the above commands to see if any errors occur, which will indicate an issue in creating the package `./dist/cma stream`.

If no errors occur immediately, you can optionally test the zip in an AWS Lambda NodeJS image, as that is the target environment. Running in an image may allow for quicker testing and development, but testing in AWS should still be the final test.

```shell
docker run -v ~/projects/cumulus-message-adapter:/zipfile --entrypoint /
bin/bash -it amazon/aws-lambda-nodejs:16
cd /zipfile
cp -r dist /opt/
cd /opt/dist
./cma stream
```

Testing the package in AWS Lambda requires uploading the zip as a layer and then running a Cumulus step function that utilizes that layer. The following instructions are for Cumulus Core team members that have access to a layer specifically set up for this purpose.

* In the AWS console, go to Lambda > Layers > CMA_Test
* Create a new version by uploading the cumulus-message-adapater zip file packaged earlier
* In your /cumulus-tf/terraform.tfvars, replace the `cumulus_message_adapter_lambda_layer_version_arn` value with the newly created Version ARN
* Apply the change with `terraform apply`
* Find any recent successfully run Step Function, and run a New Execution. The 'Functions using this version' tab of the CMA_TEST layer should provide some options.

### Troubleshooting

* Error: "DistutilsOptionError: must supply either home or prefix/exec-prefix — not both" when running `make cumulus-message-adapter.zip`
  * [Solution](https://stackoverflow.com/a/24357384)
