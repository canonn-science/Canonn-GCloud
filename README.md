# Canonn-GCloud
Repository for the google cloud functions used by various Canonn tools mainly used for the EDMC-Canonn and maps, providing data that is not available in the CAPI.

# Overview

Canonn-GCloud uses Google's Serverless [cloud function](https://cloud.google.com/functions "Google Cloud Functions") technology. 

Cloud Functions can be [written](https://cloud.google.com/functions/docs/writing "Writing Cloud Functions") in Node.js, Python, Go, Java, .NET, Ruby, and PHP programming languages, and are executed in language-specific runtimes. Most of the cloud functions used here are written in python.

## Pros
* No server infrastructure to maintain
* Frequently executed functions stay resident
* Automatic scaling. The number of instances are scalled up and down as needed. 

## Cons
* Infrequently used functions can be slow to execute because the runtime needs to be set up before first use.
* Pay as you go model means that compromises and optimisations need to be made.
* Pay as you go model means that software changes in Elite can ramp up costs. 
* While its designed for small simple functions it or better to make complex multifunctional functions performance and scaling considerations

# Design Considerations

## Invocations
When capturing events you should batch them if possible as this helps keep function executions below the billing threshold.  When fleet carriers were introduced the number of FSS events per system when up by two orders or magnitude which by December 2020 pushed monthly invocations to 4.5 million. Batching the FSS events on the EDMC-Canonn plugin reduced invocations to 1.5 million. If you need to fetch multiple items from a database create a single function that returns all the data in one go.

## Mysql connections
When using cloud functions to access a mysql database the connection is cached so that it can be re-used by subsequent function calls. If each function scales up the number of instances then it is possible for the system overall to run out of connections. Ensure that all functions accessing limited shared resources have scaling limits applied and where possible create functions that batch.

## Long running functions
Batched functions can end up taking longer to run so try to ensure that batches are limited to keep execution times below limits and also so that such functions do not block when scaling is limited. 

## Caching
Its possible to implement lazy caching so that data is stored between function executions and can be re-used. This can reduce the need to access the database and improve performance. 

## Paging APIs
When exporting large amounts of data for instance for 3D maps etc you should use a paging model so that if the data grows beyond the function limits, the function will not stop working. 

# Function Testing

It is possible to test functions locally before deploying to the cloud. However as most functions need mysql access you will need to have a few things set up.

## Python 
Most functions have been deployed with python 3.7 but google supports up to 3.9

## Node: 
I have no idea how to run node functions locally and will probably migrate them to python unless you figure it out and document it here

## Sql Cloud Auth Proxy

[Sql Cloud Proxy](https://cloud.google.com/sql/docs/mysql/sql-proxy "Google Sql Cloud Proxy") is used to provide access to the mysql database. You will need a secrets file and a login provided by @NoFoolLikeOne

The way I uses the proxy is set up as a service on a linux box so that I can access it from any PC on my home network. The command it executes is as follows

/usr/local/bin/cloud_sql_proxy -dir=/usr/local/bin/cloud_sql_proxy -instances=canonn-api-236217:europe-north1:canonnpai=tcp:10.0.0.72:3306 -credential_file=/var/local/cloud-sql-proxy/mysql_secret.json

Windows users may need to do [something else](https://github.com/GoogleCloudPlatform/cloudsql-proxy/releases "Cloudsql Proxy Releases")

## Functions Framework
The [Functions Framework](https://cloud.google.com/functions/docs/functions-framework "Functions Framework") lets you execute functions in your own environment. 

In this example the current directory has file main.py with a function called payload. 

First set envionment variables

export MYSQL_USER=yourusername
export MYSQL_PASSWORD=yourpassword
export MYSQL_HOST=localhost

Then start the function framework with the target

functions-framework --target payload --debug 

To execute the function you need to put the url into a browser or use curl

Use the following URL  [http://localhost:8080/?system=Merope&cmdr=LCU No Fool Like One](http://localhost:8080/?system=Merope&cmdr=LCU%20No%20Fool%20Like%20One)

If all went well you would see a list POIs for that system

# TODO

* Sanitise functions to remove sensitive features and check in to source control. 
* Change functions to use the host environment variable so that you can specify the database host



