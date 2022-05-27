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

## Scalability

   With Gunicorn support, aws-driver can handle huge traffic by configuring no of processes and threads.

   There are two ways to scale the aws-driver to address  production grade traffic

   ### 1. By increasing no of processes and threads

      With Gunicorn support, aws-driver can handle huge traffic by configuring no of processes and threads to the helm install command as below

      ```
         helm install aws-driver aws-driver-0.0.2.tgz --set docker.image=aws-driver--set docker.version=0.0.2 --set app.config.env.NUM_PROCESSES=<processes> --set --set app.config.env.NUM_THREADS=<threads> --set resources.requests.cpu=2*<processes>+1  --set resources.limits.cpu=2<processes>+1 -n <namespace>
      ```
      Note: Default no of processes are 9 and no of threads are 8 which are typically sufficient for production grade applications. Whenever you are increasing the no of processes, the cpu resources also should be increased accordingly as mentioned in the above command. There may be a need to increase the memory if required.

   ### 2. By scaling out the pod instances
     
    The easiest way to handle huge traffic if the default values are not sufficient is to increase the pod replicas

      ```
        oc scale deploy aws-driver --replicas <required-pod-replicas>
      ```