#!/bin/bash

python3 setup.py bdist_wheel
mkdir -p docker/whls
cp dist/awsdriver-0.0.1-py3-none-any.whl docker/whls/

pushd docker
docker build -t aws-driver:0.0.2-dev .
popd

pushd helm
mkdir -p repo
helm package -d repo aws-driver
popd

# Helm chart is in helm/repo/aws-driver-0.0.1.tgz
