General idea if we implement routing caculations:



This is just a rough test on whether it works, I am not sure about the tech stack we using yet.
For now, I think it works well if given block and the street. 

Make a .env file.(this should contain your onemap api token)
Run python app.py

(The links are generated with Chatgpt, but probably codable to auto run later on I think, I am using flask rn so it generates a json file)
curl.exe "http://127.0.0.1:5000/search?location=Blk%20406%20Pandan%20Gardens" in powershell, to get the latitude and longitude

Output:

{
  "query": "Blk 406 Pandan Gardens",
  "results": [
    {
      "address": "406 PANDAN GARDENS SINGAPORE 600406",
      "lat": 1.318821472571007,
      "lon": 103.7492263721293,
      "name": "406 PANDAN GARDENS SINGAPORE 600406",
      "postal_code": "600406"
    }
  ]
}

curl.exe "http://127.0.0.1:5000/transport?lat=1.309254654600818&lon=103.7676627297488" will generate a json file that looks like this.

output:

{
  "api_status": {
    "bus_search": true,
    "mrt_search": true
  },
  "errors": {
    "bus": null,
    "mrt": null
  },
  "nearest_bus_stop": {
    "id": 20149,
    "lat": 1.31795969,
    "lon": 103.74897266,
    "name": "BLK 408",
    "road": "WEST COAST RD",
    "straight_line_distance_m": 28.25357808012029,
    "walking_distance_m": 132.0,
    "walking_time_minutes": 1.5833333333333333
  },
  "nearest_mrt": {
    "id": "EW24 / NS1",
    "lat": 1.33307484838,
    "lon": 103.742265441,
    "name": "JURONG EAST MRT STATION",
    "road": "JURONG EAST STREET 12",
    "straight_line_distance_m": 774.3072225892394,
    "walking_distance_m": 2395.0,
    "walking_time_minutes": 28.783333333333335
  },
  "transport_score": 10,
  "user_location": {
    "lat": 1.318821472571007,
    "lon": 103.7492263721293
  }
}
