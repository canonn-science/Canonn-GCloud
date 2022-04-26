#!/bin/bash
entrypoint=payload
cd function

if [[ "$1" == "local" ]] ; then
    functions-framework  --debug --target $entrypoint --host $(hostname -I | awk '{print $1}')
else
    gcloud functions deploy gec --allow-unauthenticated --runtime python39 --entry-point $entrypoint --trigger-http  --max-instances 1 
fi
