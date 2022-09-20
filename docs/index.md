# AWS Driver

Lifecycle driver implementation that uses AWS cloud formation templates to execute operations.

# Replace Content

Replace the content of this file with a user guide for your application

# Install

Install AWS Driver using Helm:

```
helm install --name aws-driver aws-driver-0.0.1.tgz
```

Add configuration through a custom Helm values file:

```
touch custom-values.yaml
```

Add configuration to this file (check [Helm Configuration](#helm-configuration) and [Application Configuration)[#app-configuration] for details of the properties that may be configured):

```
app:
  config:
    override:
      messaging:
        connection_address: cp4na-o-events-kafka-bootstrap:9092
```

Reference the values file on install to apply configuration:

```
helm install --name aws-driver aws-driver-0.0.1.tgz -f custom_values.yaml-
```

## Helm Configuration

The following table lists configurable parameters of the chart:

| Parameter | Description | Default |
| --- | --- | --- |
| docker.image | Name of the image for the driver (may include docker registry information) | aws-driver |
| docker.version | Image tag to deploy | 0.0.1 |
| docker.imagePullPolicy | Image pull policy | IfNotPresent |
| app.replicas | Number of instances of the driver to deploy | 1 |
| app.config.log.level | Level of log messages output by the driver | INFO |
| app.config.env | Environment variables to be passed to the driver | (See below) |
| app.config.env.LOG_TYPE | Log format (leave as logstash) | logstash |
| app.config.env.WSGI_CONTAINER | WSGI container implementation used by the driver (uwsgi or gunicorn) | uwsgi |
| app.config.env.NUM_PROCESSES | Number of processes started by the WSGI container | 4 |
| app.config.env.NUM_THREADS | Number of threads per process | 2 |
| app.config.override | Map to set [Application Configuration)[#app-configuration] properties | See connection_address below and [Application Configuration)[#app-configuration] properties |
| app.config.override.message.connection_address | Kafka address. Default set to address of Kafka installed as standard with LM | cp4na-o-events-kafka-bootstrap:9092 |
| app.affinity | Affinity settings | A pod anti-affinity rule is configured to inform Kubernetes it is preferable to deploy the pods on different Nodes |
| app.tolerations | Tolerations for node taints | [] |
| app.resources | Set requests and limits to CPU and memory resources | resources.limits.cpu: 2 resources.limits.memory: 2Gi resources.requests.cp4: 2 resources.requests.memory: 1Gi |
| service.type | Type of Service to be deployed | NodePort |
| service.nodePort | NodePort used to expose the service | 30259 |
| route.enabled | Flag to disable/enable creation of an route rule for external access | true |

## Application Configuration

The following table lists configurable parameters of the Application, that may be specified in the `app.config.override` value of the Helm chart:

| Parameter | Description | Default |
| --- | --- | --- |
| application.port | Port the application runs on (internal access only) | 7276 | 
| messaging.connection_address | Kafka address | cp4na-o-events-kafka-bootstrap:9092 |


## Configure driver to resource manager

  ### 1. Configure lmctl
     
  Please refer the document to configure lmctl

  [LMCTL]https://pages.github.ibm.com/tnc/tnc.github.io/technical/development-environment/openshift-development-environment#lmctl)


  ### 2. Get the cert file from secret

     
    oc get secret aws-driver-tls -o jsonpath="{.data['tls\.crt']}" | base64 -d > aws-driver-tls.pem
    

  ### 3. Delete if the driver already exists.
       
  This step is optional. User can apply this if driver is already onboarded

     
     ```
        lmctl resourcedriver delete --type aws <lmctl-env-name>
     ```

  ### 4. Add AWS driver to resource manager


    lmctl resourcedriver add --type aws --url https://aws-driver:7276 --certificate aws-driver-tls.pem <lmctl-env-name>
    

  With this, resource manager will know there is a driver of type 'aws' and how it can reach the reach the driver.