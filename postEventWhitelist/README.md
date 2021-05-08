# postEventWhitelist

This function returns a whitelist of data for applications wanting to use the postEvent API to send data to the Canonn databases. 
The contents as an array of key values pairs in the definitions. 

```json
[
  {
    "description": "All Codex Events",
    "definition": {
      "event": "CodexEntry"
    }
  },
  {
    "description": "Signals Found Scanning Bodies",
    "definition": {
      "event": "SAASignalsFound"
    }
  },
  {
    "description": "Hutton Orbital Docking Events",
    "definition": {
      "event": "Docked",
      "StationName": "Hutton Orbital"
    }
  },
  {
    "description": "Commander event for codex reports",
    "definition": {
      "event": "Commander"
    }
  },
  {
    "description": "Cloud NSP",
    "definition": {
      "event": "FSSSignalDiscovered",
      "SignalName": "$Fixed_Event_Life_Cloud;"
    }
  },
  {
    "description": "Ring NSP",
    "definition": {
      "event": "FSSSignalDiscovered",
      "SignalName": "$Fixed_Event_Life_Ring;"
    }
  },
  {
    "description": "Belt NSP",
    "definition": {
      "event": "FSSSignalDiscovered",
      "SignalName": "$Fixed_Event_Life_Belt;"
    }
  },
  {
    "description": "Stations",
    "definition": {
      "event": "FSSSignalDiscovered",
      "IsStation": true
    }
  },
  {
    "description": "Surface Biology Scans",
    "definition": {
      "event": "ScanOrganic"
    }
  }
]
```

To check if an event should be sent to postEvent you need to cycle through each of the definitions and check that all of the key value pairs in the definition match.

Eg If event == "Docked" and "StationName" == "Hutton Orbital" then you can include the event to be sent to postEvent.


# Usage

The whitelist contents can be downloaded from the Canonn api [https://us-central1-canonn-api-236217.cloudfunctions.net/postEventWhitelist](https://us-central1-canonn-api-236217.cloudfunctions.net/postEventWhitelist)
Because the data is updated very infrequently it should only be checked once per session, not on every event, or once per day would be sufficient. 
