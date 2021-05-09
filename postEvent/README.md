# postEvent

This function is used primarily by [JournalLimpet](https://journal-limpet "Journal Limpet") and [EDMC-Canonn](https://canonn.fyi/plugin "Canonn EDMC Plugin") to submit events to the Canonn Database. 

It is designed to accept batches of events so that they can be bulk inserted. 

# Usage

The events it supports is documented through the [postEventWhitelist API](../postEventWhitelist/README.md "View the API documentation") which also includes some limited filtering capabilities. 

Applications should at least once per day download the [postEventWhitelist](https://us-central1-canonn-api-236217.cloudfunctions.net/postEventWhitelist "Download the current whitelist") to see what events can be sent. 

Frequently occurring events like FSSSignalDiscovered should be batched up before sending in batches of no more than 40 events so as not to cause the function to exceed response times and block 

## Data format

The data format has some flexibility about how you send records but we will only document the recommended format here.

The input data to the function is an array of postEvent Records each postEvent records should contain events for a specific 
gamestate eg system,body and lat/lon

events sharing these characteristics can be grouped together in a raw events record.

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
            "longitude": 0
            "body"
            "bodyId"
        },
        "rawEvents": [
            { "timestamp":"2021-04-25T16:03:07Z", "event":"ScanOrganic", "ScanType":"Analyse", "Genus":"$Codex_Ent_Stratum_Genus_Name;", "Genus_Localised":"Stratum", "Species":"$Codex_Ent_Stratum_02_Name;", "Species_Localised":"Stratum Paleas", "SystemAddress":5306398479066, "Body":19 }
        ],
        "cmdrName": "TEST"
    }
]
```




