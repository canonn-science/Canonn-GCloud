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

#TODO

Sanitise functions to remove sensitive features and check in to source control. 


