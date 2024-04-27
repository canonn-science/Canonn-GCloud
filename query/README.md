# Query

The query function uses flask routing at enable multiple queries to be served from a single cloud function. This will enacle database connections to be limited and should ensure that the less frequently used queries benefit from the function staying in memory when being used by more frequent queries.

# Usage.

If you wish to access these functions from the above [url](https://us-central1-canonn-api-236217.cloudfunctions.net/query) in your own software we require that you make a formal request to Canonn and that if appropriate you also include code in your application to capture the data from your users so that we can improve our knowledge of the galaxy.

In order to save on bandwidth please use the following headers in the get request so that the gzip transport is used. 

```python
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:20.0) Gecko/20100101 Firefox/20.0",
    "Accept-Encoding": "gzip, deflate",
}
```

# Routes

When executed from the live environment routes must be preceeded by "/query" eg [/query/challenge/next](https://us-central1-canonn-api-236217.cloudfunctions.net/query/challenge/next?cmdr=LCU%20No%20Fool%20Like%20One&system=Sol)

In the local environment you don't need "/query"

# fleetCarrier/<serial>

This function will return the last known location of a specific fleet carrier by serial number

## example

* [CRV Flower of Agatea : Q1L-N1K](https://us-central1-canonn-api-236217.cloudfunctions.net/query/fleetCarrier/Q1L-N1K)

# fleetCarrier/<beginning|ending|like|named>/<text>

This function will search for fleet carriers names in the text. 

## examples

* [Search for Canonn Carriers beginning with CRV](https://us-central1-canonn-api-236217.cloudfunctions.net/query/fleetCarriers/beginning/CRV)
* [Search for Canonn Carriers ending with Inc.](https://us-central1-canonn-api-236217.cloudfunctions.net/query/fleetCarriers/ending/Inc.)
* [Search for Canonn Carriers with Tharg in the name](https://us-central1-canonn-api-236217.cloudfunctions.net/query/fleetCarriers/like/Tharg)
* [Search for Canonn Carriers named "Fleet Carrier"](https://us-central1-canonn-api-236217.cloudfunctions.net/query/fleetCarriers/named/Fleet%20Carrier)




# fleetCarriers/nearest

Given a set of x,y,z coordinates it will show you the nearest known fleet carriers

## parameters

* x,y,z (The coordinates of the reference system)

## example

* [Nearest Carriers to Graveyard Ghosts](https://us-central1-canonn-api-236217.cloudfunctions.net/query/fleetCarriers/nearest?x=0&y=0&z=1000) A GEC POI at [edastro.com/gec](https://edastro.com/gec/view/502)


# fleetCarriers

This will display fleet carriers at one or most system names

## parameters

* systems (a optional comma seperates list of system names)

## examples

* [Show all](https://us-central1-canonn-api-236217.cloudfunctions.net/query/fleetCarriers) 
* [Merope and Varati](https://us-central1-canonn-api-236217.cloudfunctions.net/query/fleetCarriers?systems=Merope,Varati) 

# challenge/next

This function will look up the nearest system containing an unscanned codex entry for a given commander and location. The performance of this function is very  slow because it has to scan codex entries for distance. Please do not execute frequently.

## parameters

* cmdr (the commander name to lookup)
* system (The name of the reference system if x,y,z is available use that instead)
* x,y,z (The coordinates of the reference system)

## example

* [CMDR LCU No Fool Like One from Syriae Thua HQ-E c25-0](https://us-central1-canonn-api-236217.cloudfunctions.net/query/challenge/next?cmdr=LCU%20No%20Fool%20Like%20One&system=Syriae%20Thua%20HQ-E%20c25-0)
* [CMDR LCU No Fool Like One from 0,0,0](https://us-central1-canonn-api-236217.cloudfunctions.net/query/challenge/next?cmdr=LCU%20No%20Fool%20Like%20One&x=0&y=0&z=0)

# challenge/status

This function will return a data structure showing all codex types and the commander's progress in scanning them. 

## parameters

* cmdr (the commander name to lookup)

## example
[CMDR LCU No Fool Like One](https://us-central1-canonn-api-236217.cloudfunctions.net/query/challenge/status?cmdr=LCU%20No%20Fool%20Like%20One)

# codex/ref

Gets a structure of all codex entries used by EDMC-Canonn

## parameters

* hierarchy=1 (An optional parameter that displays the data as a hierarchy)
* category (restricts the query to a category, eg Biology or Geology)
* species (restricts the query to species eg Anomaly or Stratum)
* variant (searches the variant name to filter the results)

##example
[Get Everything](https://us-central1-canonn-api-236217.cloudfunctions.net/query/codex/ref)
[With Hierarchy](https://us-central1-canonn-api-236217.cloudfunctions.net/query/codex/ref?hierarchy=1)
[Just Geology](https://us-central1-canonn-api-236217.cloudfunctions.net/query/codex/ref?category=Geology)
[Just Anemones](https://us-central1-canonn-api-236217.cloudfunctions.net/query/codex/ref?species=Anemone)
[Anything with Yellow in the name](https://us-central1-canonn-api-236217.cloudfunctions.net/query/codex/ref?variant=Yellow)

# challenge/fastest_scans

Canonn Challenge Fastest Scans: Gives fastest times between log and analyse for a specifc commander or the top 20 commanders if no parameter

## parameters

* cmdr (the commander name to lookup)

## example
[Top 20 Commanders](https://us-central1-canonn-api-236217.cloudfunctions.net/query/challenge/fastest_scans)   (NB: This requires a full scan so is quite slow)

[CMDR LCU No Fool Like One](https://us-central1-canonn-api-236217.cloudfunctions.net/query/challenge/fastest_scans?cmdr=LCU%20No%20Fool%20Like%20One)


## example
[Live Codex Reference Data](https://us-central1-canonn-api-236217.cloudfunctions.net/query/codex/ref)

# nearest/codex 

This function will show you the nearest codex entry to your current position. 

## parameters

* x=&y=&z= (provide x,y,z coordinates to avoid an edsm lookup)
* system (if x,y,z is not known you can supply the system name and it will look up edsm)
* name ( The english name of the thing you want to find)

## examples

* [Nearest Entry to Sol using coordinates](https://us-central1-canonn-api-236217.cloudfunctions.net/query/nearest/codex?x=0&y=0&z=0)
* [Nearest Entry to Merope using system name ](https://us-central1-canonn-api-236217.cloudfunctions.net/query/nearest/codex?system=Merope)
* [Nearest Bark Mounds to Merope ](https://us-central1-canonn-api-236217.cloudfunctions.net/query/nearest/codex?system=Merope&name=Bark)


# settlements

## parameters

* systemName|id64 

For a given id64 or systemName get a list of settlements. NB id64 is less likely to contain errored values because the id64 is included in the event and not added by the EDDN client.

## example

* [Settlements in HR 1621 using id64](https://us-central1-canonn-api-236217.cloudfunctions.net/query/settlement/14199809196) 
* [Settlements in Merope using systemName](https://us-central1-canonn-api-236217.cloudfunctions.net/query/settlement/Merope) 

# get_gr_data

This function returns a list of systems with Guardian ruins. Used by the 3D maps

## example

https://us-central1-canonn-api-236217.cloudfunctions.net/query/get_gr_data

# getSystemPoi
Accepts a system name a commander name and returns all the POI information for that system captured in the Canonn database. There is an optional odyssey flag that controls how data from Odyssey and Horizons is used. 

The data is captured from the following journal events

* CodexEntry
* SAASignalFound
* FSSSignalDiscovered

In addition it uses POI data recorded by the specified commander using the "*canonn capture*" command

## example

* [Get system POIs for Merope](https://us-central1-canonn-api-236217.cloudfunctions.net/query/getSystemPoi?system=Merope&cmdr=Syleo&odyssey=Y)


# thargoid/nhss/systems
This returns a list of all systems with NHSS NB this is limited to the first 1000 

## parameters

* system (the name of the system you want to find)
* threat (The threat level you want to see)
* _start (used for paging to represent the start of teh page -  defaults to 1 )
* _limit (used for paging to set a limit on how many pages - defaults to 1000)

## examples

* [Get NHSS for Merope](https://us-central1-canonn-api-236217.cloudfunctions.net/query/thargoid/nhss/systems?system=Merope)
* [Get all systems with threat 0 NHSS](https://us-central1-canonn-api-236217.cloudfunctions.net/query/thargoid/nhss/systems?threat=0)
* [Get the next thousand NHSS system starting with 1000](https://us-central1-canonn-api-236217.cloudfunctions.net/query/thargoid/nhss/systems?_start=1000&_limit=1000)

# thargoid/nhss/reports
This returns a list of all reported NHSS 
NB: this is limited to the first 1000 

## parameters

* system (the name of the system you want to find)
* threat (The threat level you want to see)
* _start (used for paging to represent the start of teh page -  defaults to 1 )
* _limit (used for paging to set a limit on how many pages - defaults to 1000)

## examples

* [Get NHSS for Merope](https://us-central1-canonn-api-236217.cloudfunctions.net/query/thargoid/nhss/reports?system=Merope)
* [Get all systems with threat 0 NHSS](https://us-central1-canonn-api-236217.cloudfunctions.net/query/thargoid/nhss/reports?threat=0)
* [Get the next thousand NHSS system starting with 1000](https://us-central1-canonn-api-236217.cloudfunctions.net/query/thargoid/nhss/reports?_start=1000&_limit=1000)


# thargoid/hyperdiction/reports
This returns a list of all hyperdictions detected since March 2021 with th start location and destination of the jump. It also shows which bubble is nearest to each of those locations. 

NB: this is limited to the first 1000 

## parameters

* system (the name of the system you want to find)
* _start (used for paging to represent the start of teh page -  defaults to 1 )
* _limit (used for paging to set a limit on how many pages - defaults to 1000)

## examples

* [Get Hyperdiction reports for Asterope](https://us-central1-canonn-api-236217.cloudfunctions.net/query/thargoid/hyperdiction/reports?system=Asterope)
* [Get the next thousand Hyperdiction reports starting with 1000](https://us-central1-canonn-api-236217.cloudfunctions.net/query/thargoid/hyperdiction/reports?_start=1000&_limit=1000)


# get_compres

Gets the following informations for all systems in a list. Used by the 3D maps.

* Resource Extraction Site [High]
* Resource Extraction Site [Hazardous]
* Compromised Nav Beacon

# parameters

systems (a comma seperated list of system names)

# example

* [Get Values for Varati and Canonnia](https://us-central1-canonn-api-236217.cloudfunctions.net/query/get_compres?systems=Varati,Canonnia)

# gnosis

Returns a json with the current location of the Gnosis

https://us-central1-canonn-api-236217.cloudfunctions.net/query/gnosis

# gnosis/schedule

returns a json array with the current schedule

https://us-central1-canonn-api-236217.cloudfunctions.net/query/gnosis/schedule

# gnosis/schedule/table

This endpoint generates a png with the Gnosis Schedule. The schedule can be limited to a single system.

## parameters

* system (the name of the system you want to find)

## Example

https://us-central1-canonn-api-236217.cloudfunctions.net/query/gnosis/schedule/table

![](https://us-central1-canonn-api-236217.cloudfunctions.net/query/gnosis/schedule/table)

https://us-central1-canonn-api-236217.cloudfunctions.net/query/gnosis/schedule/table?system=Epsilon%20Indi

![](https://us-central1-canonn-api-236217.cloudfunctions.net/query/gnosis/schedule/table?system=Epsilon%20Indi)

