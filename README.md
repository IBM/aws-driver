[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Build Status](https://travis-ci.com/IBM/aws-driver.svg?branch=master)](https://travis-ci.com/IBM/aws-driver)

# AWS Driver
Lifecycle driver implementation that uses AWS cloud formation templates to execute operations.

Please read the following guides to get started with the lifecycle Driver:

## Developer

- [Developer Docs](./developer_docs/index.md) - docs for developers to install the driver from source or run the unit tests

## User

- [User Guide](./docs/index.md)

# Build

Use the `build.sh` script to build the Docker image and Helm chart.


# Deployment Location

The AWS driver expects an `AWS` deployment location with the following properties:

* AWS_ACCESS_KEY_ID: the AWS Access Key Id of your AWS accouunt
* AWS_SECRET_ACCESS_KEY: the AWS Secret Access Key of your AWS accouunt

