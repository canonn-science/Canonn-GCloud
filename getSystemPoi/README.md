# getSystemPoi

This is a cloud function that accepts a system name and a commander name and returns all the POI information for that system captured in the Canonn database.

The data is captured from the following journal events

* CodexEntry
* SAASignalFound
* FSSSignalDiscovered

In addition it uses POI data recorded by the specified commander using the "*canonn capture*" command

[https://us-central1-canonn-api-236217.cloudfunctions.net/getSystemPoi?system=Merope&cmdr=Syleo](https://us-central1-canonn-api-236217.cloudfunctions.net/getSystemPoi?system=Merope&cmdr=Syleo "Get system POIs for Merope")

# Usage.

If you wish to access this function from the above [url](https://us-central1-canonn-api-236217.cloudfunctions.net/getSystemPoi?system=Merope&cmdr=Syleo) in your own software we require that you make a formal request to Canonn and that if appropriate you also include code in your application to capture the data from your users so that we can improve our knowledge of the galaxy.

In order to save on bandwidth please use the following headers in the get request so that the gzip transport is used. 

```python
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:20.0) Gecko/20100101 Firefox/20.0",
    "Accept-Encoding": "gzip, deflate",
}
```



