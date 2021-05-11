#!/bin/bash
gcloud functions deploy query --allow-unauthenticated --runtime python39 --entry-point payload --trigger-http  --max-instances 4 --set-env-vars=MYSQL_USER=$MYSQL_USER,MYSQL_PASSWORD=$MYSQL_PASSWORD
