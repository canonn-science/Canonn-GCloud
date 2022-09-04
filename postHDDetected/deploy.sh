#!/bin/bash
entrypoint=payload
cd function


if [[ "$1" == "local" ]] ; then
    functions-framework  --debug --target $entrypoint --host $(hostname -I | awk '{print $1}') 
fi

if [[ "$1" == "live" ]] ; then
    gcloud functions deploy postHDDetected --region "europe-west1" --allow-unauthenticated --runtime python39 --entry-point $entrypoint --trigger-http  --max-instances 2 --set-env-vars=MYSQL_USER=$MYSQL_USER,MYSQL_PASSWORD=$MYSQL_PASSWORD,INSTANCE_CONNECTION_NAME=$INSTANCE_CONNECTION_NAME,MYSQL_DATABASE=$MYSQL_DATABASE
fi

if [[ "$1" == "test" ]] ; then    
    gcloud functions deploy postHDDetected2 --region "europe-west1" --allow-unauthenticated --runtime python39 --entry-point $entrypoint --trigger-http  --max-instances 2 --set-env-vars=MYSQL_USER=$MYSQL_USER,MYSQL_PASSWORD=$MYSQL_PASSWORD,INSTANCE_CONNECTION_NAME=$INSTANCE_CONNECTION_NAME,MYSQL_DATABASE=$MYSQL_DATABASE
fi


