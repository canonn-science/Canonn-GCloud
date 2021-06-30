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

# challenge/next

This function will look up the nearest system containing an unscanned codex entry for a given commander and location. The performance of this function is relatively slow because it has to scan codex entries for distance.

## parameters

* cmdr (the commander name to lookup)
* system (The name of the reference system)
* x,y,z (The coordinates of the reference system)

## example

[CMDR LCU No Fool Like One from Sol](https://us-central1-canonn-api-236217.cloudfunctions.net/query/challenge/next?cmdr=LCU%20No%20Fool%20Like%20One&system=Sol)

# challenge/status

This function will return a data structure showing all codex types and the commander's progress in scanning them. 

## parameters

* cmdr (the commander name to lookup)

## example
[CMDR LCU No Fool Like One](https://us-central1-canonn-api-236217.cloudfunctions.net/query/challenge/status?cmdr=LCU%20No%20Fool%20Like%20One)

# codex/ref

Gets a structure of all codex entries used by EDMC-Canonn

## example
[Live Codex Reference Data](https://us-central1-canonn-api-236217.cloudfunctions.net/query/codex/ref)

# nearest/codex 

This function will show you the nearest codex entry to your current position. 

## parameters

* x=&y=&z= (provide x,y,z coordinates to avoid an edsm lookup)
* system (if x,y,z is not known you can supply the system name and it will look up edsm)
* name ( The english name of the thing you want to find)

## examples

[Nearest Entry to Sol using coordinates](https://us-central1-canonn-api-236217.cloudfunctions.net/query/nearest/codex?x=0&y=0&z=0)
[Nearest Entry to Merope using system name ](https://us-central1-canonn-api-236217.cloudfunctions.net/query/nearest/codex?system=Merope)
[Nearest Bark Mounds to Merope ](https://us-central1-canonn-api-236217.cloudfunctions.net/query/nearest/codex?system=Merope&name=Bark)




# getSystemPoi
Accepts a system name a commander name and returns all the POI information for that system captured in the Canonn database. There is an optional odyssey flag that controls how data from Odyssey and Horizons is used. 

The data is captured from the following journal events

* CodexEntry
* SAASignalFound
* FSSSignalDiscovered

In addition it uses POI data recorded by the specified commander using the "*canonn capture*" command

[https://us-central1-canonn-api-236217.cloudfunctions.net/getSystemPoi?system=Merope&cmdr=Syleo&odyssey=Y](https://us-central1-canonn-api-236217.cloudfunctions.net/query/getSystemPoi?system=Merope&cmdr=Syleo&odyssey=Y "Get system POIs for Merope")


```



