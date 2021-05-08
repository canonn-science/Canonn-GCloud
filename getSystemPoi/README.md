# getSystemPoi

This is a cloud function that accepts a system name and a commander name and returns all the POI information for that system.

The data is captured from the following journal events

* CodexEntry
* SAASignalFound
* FSSSignalDiscovered

In addition in uses POI data recorded by the specified commander using the "*canonn capture*" command

[https://us-central1-canonn-api-236217.cloudfunctions.net/getSystemPoi?system=Merope&cmdr=Syleo](https://us-central1-canonn-api-236217.cloudfunctions.net/getSystemPoi?system=Merope&cmdr=Syleo "Get system POIs for Merope")

