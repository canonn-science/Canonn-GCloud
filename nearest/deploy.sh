#!/bin/bash
entrypoint=payload
cd function
if [[ "$1" == "local" ]] ; then
    functions-framework  --debug --target $entrypoint --host $(hostname -I | awk '{print $1}')
fi

if [[ "$1" == "live" ]] ; then
    gcloud functions deploy hcs --project populated --allow-unauthenticated --runtime python39 --entry-point $entrypoint --trigger-http  --max-instances 2 
fi

if [[ "$1" == "test" ]] ; then
    gcloud functions deploy hcstest --project populated --allow-unauthenticated --runtime python39 --entry-point $entrypoint --trigger-http  --max-instances 2 
fi
