#!/bin/bash
gcloud functions deploy query --allow-unauthenticated --runtime python39 --entry-point payload --trigger-http 
