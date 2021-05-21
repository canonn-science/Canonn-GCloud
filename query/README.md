# Query

The query function uses flask routing at enable multiple queries to be served from a single cloud function. This will enacle database connections to be limited and should ensure that the less frequently used queries benefit from the function staying in memory when being used by more frequent queries.

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
