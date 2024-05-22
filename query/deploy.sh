#!/bin/bash
entrypoint=payload
fname=$(basename $(pwd))

cd function
cp $HOME/.ssh/gcf_rsa.prv .


if [[ "$1" == "local" ]] ; then
    unset INSTANCE_CONNECTION_NAME
    functions-framework  --debug --target $entrypoint --host $(hostname -I | awk '{print $1}')
fi

if [[ "$1" == "live" ]] ; then
    INSTANCE_CONNECTION_NAME=canonn-api-236217:europe-north1:canonnpai ; export INSTANCE_CONNECTION_NAME
    gcloud functions deploy $fname  \
        --allow-unauthenticated \
        --runtime python312 \
        --entry-point $entrypoint \
        --trigger-http  \
        --timeout 90  \
        --max-instances 10 \
        --set-env-vars=MYSQL_USER=$MYSQL_USER,MYSQL_PASSWORD=$MYSQL_PASSWORD,INSTANCE_CONNECTION_NAME=canonn-api-236217:europe-north1:canonnpai
fi

if [[ "$1" == "test" ]] ; then
    unset INSTANCE_CONNECTION_NAME
    # we are using defaulst from the 
    TUNNEL_KEY=$TUNNEL_KEY
    TUNNEL_HOST=$TUNNEL_HOST
    #We will set up a tunnel on 3308
    #If the database connection is 3308 then the tunnel will route to the destination on 3306
    #So MYSQL_PORT = local_port = 3308
    MYSQL_HOST=localhost ; export MYSQL_HOST
    MYSQL_PORT=3308 ; export MYSQL_PORT
    MYSQL_PASSWORD=$TEST_PASSWORD ; export MYSQL_PASSWORD
    functions-framework  --debug --target $entrypoint --host $(hostname -I | awk '{print $1}')
fi

if [[ "$1" == "newlive" ]] ; then
    unset INSTANCE_CONNECTION_NAME
    #We will set up a tunnel on 3308
    #If the database connection is 3308 then the tunnel will route to the destination on 3306
    #So MYSQL_PORT = local_port = 3308
    gcloud functions deploy $fname  \
        --allow-unauthenticated \
        --runtime python312 \
        --entry-point $entrypoint \
        --trigger-http  \
        --timeout 90  \
        --max-instances 10 \
        --set-env-vars=MYSQL_USER=$MYSQL_USER,MYSQL_PASSWORD=$TEST_PASSWORD,TUNNEL_KEY=$TUNNEL_KEY,TUNNEL_HOST=$TUNNEL_HOST,MYSQL_HOST=localhost,MYSQL_PORT=3308

    fi
