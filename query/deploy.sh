#!/bin/bash
entrypoint=payload

if [[ "$1" == "local" ]] ; then
    INSTANCE_CONNECTION_NAME=canonn-api-236217:europe-north1:canonnpai ; export INSTANCE_CONNECTION_NAME
    functions-framework  --debug --target $entrypoint --host $(hostname -I | awk '{print $1}')
fi
if [[ "$1" == "live" ]] ; then
    gcloud functions deploy query --allow-unauthenticated --runtime python312 --entry-point $entrypoint --trigger-http  --max-instances 10 --set-env-vars=MYSQL_USER=$MYSQL_USER,MYSQL_PASSWORD=$MYSQL_PASSWORD,INSTANCE_CONNECTION_NAME=canonn-api-236217:europe-north1:canonnpai
fi
if [[ "$1" == "test" ]] ; then
    # Assumed to be using tunnel to the real test server on 3307
    MYSQL_HOST=$(hostname -I | awk '{print $1}') ; export MYSQL_HOST
    MYSQL_PORT=3307 ; export MYSQL_PORT
    MYSQL_PASSWORD=$TEST_PASSWORD ; export MYSQL_PASSWORD
    functions-framework  --debug --target $entrypoint --host $(hostname -I | awk '{print $1}')
fi