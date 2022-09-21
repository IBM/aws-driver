# Helm Chart

The Helm chart for this driver includes the following features:

- A Deployment to create pods for your driver application
- A Service to expose your application internally and externally (with a NodePort/Route)
- Configurable options for:
    - Location and version of Docker image
    - Number of replicas of the driver
    - Property groups configured on your application (i.e. override the properties in the default_config file)
    - Log level
    - uWSGI container used by your application
    - Pod affinity/anti-affinity
    - Node affinity/anti/affinity
    - NodePort
    - Resources
- Necessary Deployment labels so logs from the driver may be viewed in the dashboard provided with LM (Kibana)

# Build Helm Chart

To build the Helm chart you will need to install Helm and initialise it (e.g. `helm init --client-only` on your local machine).

Build the chart with the package command:

```
helm package helm/aws-driver
```

The command will print the location of the generated `.tgz` Helm package.

# Deploy Helm Chart

To deploy the Helm chart will need Helm installed and initialised against a Kubernetes cluster (e.g. `helm init` on your Kubernetes cluster master node).

Install the chart with the default configuration using the install command and in the namespace where siteplanner installed:

```
helm install --name aws-driver <path to chart> -n <namespace>
```

Configuration for the Helm deployment can be provided with a **Helm values file** on the `-f` option. 

```
helm install --name aws-driver <path to chart> -f <path to Helm values file>
```

By default, the Deployment included in this chart will expect the driver docker image to be available on the Kubernetes worker node (e.g. the image can be seen in the list returned by `docker images`). If the image is not on the node, you should [transfer the image to the node](#transfer-docker-image-to-node) or [use a docker registry](#use-docker-registry).

To override configuration for your driver application (e.g. Kafka address, other property groups configured by the user), add the following to a custom **Helm values file**:

```
app:
  override:
    ## Add the properties to configure as YAML here
    propA: valueA 
```

Once you have installed the chart you can check the status of your deployment with:

```
kubectl get pods
```

Or:

```
helm status aws-driver
```

## Transfer Docker Image to Node

To transfer it to the node you can use `docker save` locally, then `docker load` on the node:

Locally:
```
docker save -o aws-driver-img.tar aws-driver:<release version number>
```

Transfer the file using scp:
```
scp aws-driver-img.tar <user>@<worker-node-ip>:/home/<user>
```

On Node:
```
docker load -i /home/<user>/aws-driver-img.tar
```

## Use Docker Registry

In a custom **Helm values file** add the following:

```
docker:
  image: <registry host and port>/aws-driver
  version: 1.0.0
  imagePullPolicy: IfNotPresent
```

Include this values file on the Helm install command with the `-f` option.

Note: if the Docker registry is insecure you need to inform the docker daemon (usually by adding it to a "insecure-registries" in `/etc/docker/daemon.json`).

## Scalability

   With Gunicorn support, aws-driver can handle huge traffic by configuring no of processes and threads.

   There are two ways to scale the aws-driver to address  production grade traffic

   ### 1. By increasing no of processes and threads

      Configure with helm install command as below

      ```
         helm install aws-driver aws-driver-<version>.tgz --set docker.image=aws-driver--set docker.version=<version> --set app.config.env.NUM_PROCESSES=<processes> --set --set app.config.env.NUM_THREADS=<threads> --set resources.requests.cpu=2*<processes>+1  --set resources.limits.cpu=2*<processes>+1 -n <namespace>
      ```
      Note: Default no of processes are 9 and no of threads are 8 which are typically sufficient for production grade applications. Whenever you are increasing the no of processes, the cpu resources also should be increased accordingly as mentioned in the above command. There may be a need to increase the memory if required.

   ### 2. By scaling out the pod instances
     
    The easiest way to handle huge traffic if the default values are not sufficient is to increase the pod replicas

  ```
    oc scale deploy aws-driver --replicas <required-pod-replicas> -n <namespace>
  ```

# Configure driver to resource manager

  ## 1. Configure lmctl
     
    Please refer the document to configure lmctl

    [LMCTL](https://pages.github.ibm.com/tnc/tnc.github.io/technical/development-environment/openshift-development-environment#lmctl)


  ## 2. Get the cert file from secret

     ```
        oc get secret aws-driver-tls -o jsonpath="{.data['tls\.crt']}" | base64 -d > aws-driver-tls.pem -n <namespace>
     ```

  ## 3. Delete if the driver already exists.
       
      This step is optional. User can apply this if driver is already onboarded

     
     ```
        lmctl resourcedriver delete --type aws <lmctl-env-name>
     ```

  ## 4. Add AWS driver to resource manager

     ```
        lmctl resourcedriver add --type aws --url https://aws-driver:7276 --certificate aws-driver-tls.pem <lmctl-env-name>
     ```

    With this, resource manager will know there is a driver of type 'aws' and how it can reach the reach the driver.