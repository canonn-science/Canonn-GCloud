#!/bin/bash
entrypoint=entrypoint

if [[ "$1" == "local" ]] ; then
    functions-framework  --debug --target $entrypoint --host $(hostname -I | awk '{print $1}')
else
	gcloud functions deploy $(basename $(pwd)) --allow-unauthenticated --runtime python312 --entry-point $entrypoint --timeout 120 --trigger-http  --max-instances 10 --set-env-vars=MYSQL_USER=$MYSQL_USER,MYSQL_PASSWORD=$MYSQL_PASSWORD
fi
