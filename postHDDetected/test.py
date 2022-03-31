import requests
import json


data1 = {"cmdr": 'TEST1', "system": 'TEST', "timestamp": '2022-03-30T21:49:31Z', "x": 40000, "y": 0,
         "z": 0, "destination": 'TEST', "dx": 0, "dy": 0, "dz": 0, "client": 'TEST', "odyssey": 'N'}
data2 = {"cmdr": 'TEST2', "system": 'TEST', "timestamp": '2022-03-30T21:49:31Z', "x": 40000, "y": 0,
         "z": 0, "destination": 'TEST', "dx": 0, "dy": 0, "dz": 0, "client": 'TEST', "odyssey": 'Y'}
data3 = {"cmdr": 'TEST3', "system": 'TEST', "timestamp": '2022-03-30T21:49:31Z', "x": 40000,
         "y": 0, "z": 0, "destination": 'TEST', "dx": 0, "dy": 0, "dz": 0, "client": 'TEST'}


def post(data):
    url = "https://europe-west1-canonn-api-236217.cloudfunctions.net/postHDDetected2"

    r = requests.post(url, data=json.dumps(data, ensure_ascii=False).encode('utf8'),
                      headers={"content-type": "application/json"})
    if not r.status_code == requests.codes.ok:
        headers = r.headers
        contentType = str(headers['content-type'])
        if 'json' in contentType:
            print(json.dumps(r.content))
        else:
            print(r.content)
        print(r.status_code)
    else:
        print("success")


post(data3)
post(data1)
post(data2)
