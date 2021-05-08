# edmcWhitelist

This function returns a whitelist of data for edmc plugins to download and insert into the raw_events table on the Canonn database. 
It is there to enable us to quickly capture new events without needing a client update.

The contents as an array of key values pairs 

```json
[
  {
    "definition": {
      "event": "Docked",
      "StationName": "Hutton Orbital"
    }
  },
  {
    "definition": {
      "'event": "SellExplorationData"
    }
  }
]
```

When an event comes in to the plugin then for each definition, the keys are checked against the key values in the event and if all are identical the event can be recorded by the plugin.

Eg If event == "Docked" and "StationName" == "Hutton Orbital" then write the event to the raw events table. 

# Usage

The whitelist contents can be downloaded from the Canonn api [https://us-central1-canonn-api-236217.cloudfunctions.net/edmcWhitelist](https://us-central1-canonn-api-236217.cloudfunctions.net/edmcWhitelist)
Because the data is downloaded very infrequently it should only be checked once per session, not on every event. 
