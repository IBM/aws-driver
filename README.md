# AWS Driver

# Build

Use the `build.sh` script to build the Docker image and Helm chart.

# Install

Install using the `helm install` command:

```
# e.g. using Helm 3
helm install aws-driver aws-driver-0.0.1.tgz
```

The Helm chart is currently configured for installation in to an AIO environment, so there's nothing
to override if installing in to AIO.

The Helm chart assumes that the driver Docker image is `aws-driver:0.0.2-dev` i.e. that it is loaded in to the
Docker runtime e.g. using `docker load`:

```
docker save aws-driver:0.0.2-dev -o aws-driver-0.0.2-dev

# copy aws-driver-0.0.1 to target K8s environment, then
docker load -i aws-driver-0.0.2-dev
```

Alternatively, it could be pushed to a Docker registry and installed as follows:

```
helm install aws-driver aws-driver-0.0.1.tgz --set docker.image=[registry]/aws-driver
```

# Deployment Location

The AWS driver expects an `AWS` deployment location with the following properties:

* AWS_ACCESS_KEY_ID: the AWS Access Key Id of your AWS accouunt
* AWS_SECRET_ACCESS_KEY: the AWS Secret Access Key of your AWS accouunt