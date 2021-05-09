# postEvent

This function is used primarily by [JournalLimpet](https://journal-limpet "Journal Limpet") and [EDMC-Canonn](https://canonn.fyi/plugin "Canonn EDMC Plugin") to submit events to the Canonn Database. 

It is designed to accept batches of events so that they can be bulk inserted. 

# Usage

The events it supports is documented through the [postEventWhitelist API](../postEventWhitelist/README.md "View the API documentation") which also includes some limited filtering capabilities. 

Applications should at least once per day download the [postEventWhitelist](https://us-central1-canonn-api-236217.cloudfunctions.net/postEventWhitelist "Download the current whitelist") to see what events can be sent. 

Frequently occurring events like FSSSignalDiscovered should be batched up before sending in batches of no more than 40 events so as not to cause the function to exceed response times and block 

## Data format

The data format has some flexibility about how you send records but we will only document the recommended schema here.

```python
{
  "type": "array",
  "items": [
    {
      "type": "object",
      "properties": {
        "gameState": {
          "type": "object",
          "properties": {
            "systemName": {"type": "string"},
            "systemAddress": {"type": "integer"},
            "systemCoordinates": {
              "type": "array",
              "items": [
                {"type": "number"},
                {"type": "number"},
                {"type": "number"}              
              ]
            },
            "clientVersion": {"type": "string"},
            "isBeta": {"type": "boolean"},
            "latitude": {"type": "number"},
            "longitude": {"type": "integer"},
            "bodyName": {"type": "string"},
            "bodyId": {"type": "string"}
          },
          "required": [
            "systemName",
            "systemAddress",
            "systemCoordinates",
            "clientVersion",
            "isBeta"
          ]
        },
        "rawEvents": {
          "type": "array",
          "items": [  # an array of raw events from in game 
            {
              "type": "object",
              "properties": {
                "timestamp": {"type": "string"},
                "event": {"type": "string"},
              },
              "required": [
                "timestamp",
                "event"
              ]
            }
          ]
        },
        "cmdrName": {
          "type": "string"
        }
      },
      "required": [
        "gameState",
        "rawEvents",
        "cmdrName"
      ]
    }
  ]
}
```

Note that the gamestate needs to have the correct details to go with the raw events. Eg. The system, body, lat/lon must be the same for all the events in the rawEvents array, otherwise you need to supply a new postEvent record with its own Gamestate. 

```json
[
    {
        "gameState": {
            "systemName": "Lysoovsky BH-L d8-26",
            "systemAddress": 902538824779,
            "systemCoordinates": [
                -6214.53125,
                461.37500,
                7361.75000
            ],
            "clientVersion": "Postman",
            "isBeta": false,
            "latitude": 12.12345,
            "longitude": 0,
            "bodyName": "Lysoovsky BH-L d8-26 5 b",
            "bodyId": "19",
        },
        "rawEvents": [
            { "timestamp":"2021-04-25T16:03:07Z", "event":"ScanOrganic", "ScanType":"Analyse", "Genus":"$Codex_Ent_Stratum_Genus_Name;", "Genus_Localised":"Stratum", "Species":"$Codex_Ent_Stratum_02_Name;", "Species_Localised":"Stratum Paleas", "SystemAddress":5306398479066, "Body":19 }
        ],
        "cmdrName": "TEST"
    }
]
```




