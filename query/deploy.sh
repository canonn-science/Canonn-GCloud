#!/bin/bash
entrypoint=payload

if [[ "$1" == "local" ]] ; then
    functions-framework  --debug --target $entrypoint --host $(hostname -I | awk '{print $1}')
else
    gcloud functions deploy query --allow-unauthenticated --runtime python39 --entry-point $entrypoint --trigger-http  --max-instances 10 --set-env-vars=MYSQL_USER=$MYSQL_USER,MYSQL_PASSWORD=$MYSQL_PASSWORD
fi
