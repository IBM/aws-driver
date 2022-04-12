FROM python:3.7-alpine

ARG DRIVER_PORT
ENV DRIVER_PORT ${DRIVER_PORT:-7276}
ARG NUM_PROCESSES
ENV NUM_PROCESSES ${NUM_PROCESSES:-4}
ARG NUM_THREADS
ENV NUM_THREADS ${NUM_THREADS:-2}
ARG WSGI_CONTAINER
ENV WSGI_CONTAINER ${WSGI_CONTAINER:-uwsgi}

COPY whls/*.whl /whls/

RUN addgroup -S awsdriver \
 && adduser -S awsdriver -G awsdriver -u 101 \
 && mkdir -p /var/awsdriver \
 && mkdir -p /home/awsdriver/scripts_workspace \
 # set group to 0 to allow arbitrary users in OCP to write to these directories
 && chown -R awsdriver:0 /var/awsdriver \
 && chmod -R 775 /var/awsdriver \
 && chown -R awsdriver:0 /home/awsdriver \
 && chmod -R 775 /home/awsdriver \
 && apk add --no-cache bash binutils libc-dev \
 # These packages need to be installed so that we can install the Python dependencies.
 # We make this virtual so that we can remove them later
 && apk add --no-cache --virtual .build-deps gcc musl-dev libffi-dev openssl-dev python3-dev make git \
 && for i in /whls/ignition*.whl; do if [ "$i" != "/whls/ignition*.whl" ]; then pip install --no-warn-script-location "$i"; fi done \
 && for i in /whls/*.whl; do pip install "$i"; done \
 && apk del .build-deps gcc musl-dev libffi-dev openssl-dev python3-dev make git

COPY cloudformation_template.yaml /home/awsdriver/scripts_workspace/cloudformation_template.yaml

USER awsdriver
WORKDIR /home/awsdriver
EXPOSE 7276

CMD ["awsdriver"]
