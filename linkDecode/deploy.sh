#!/bin/bash
entrypoint=payload

if [[ "$1" == "local" ]] ; then
    functions-framework  --debug --target $entrypoint --host $(hostname -I | awk '{print $1}')
else
    gcloud functions deploy basename $(pwd) --allow-unauthenticated --runtime python39 --entry-point $entrypoint --trigger-http  
fi