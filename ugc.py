import requests
import time
import json
from bs4 import BeautifulSoup


def request_OSM_data(url, headers={'User-Agent': 'UI-map/1.0 (https://github.com/thomas-saigre/ugc)'}):
    time.sleep(1)
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to retrieve data from {url}, error {response.status_code}")
        print(response.text)
        return None

class Cinema:

    def __init__(self, tag):
        self.name = tag.find(class_='color--white text-uppercase').text.strip()
        self.address = tag.find(class_='color--blue-grey').text.strip()

    def get_infos_from_OSM(self):
        data_nominatim = request_OSM_data(f"https://nominatim.openstreetmap.org/search?q={self.name}&format=json")
        if data_nominatim:
            if len(data_nominatim) > 1:
                print(f"Multiple results found for {self.name}, please check results !")
            osm_id = data_nominatim[0]['osm_id']
            osm_type = data_nominatim[0]['osm_type']

            data_osm = request_OSM_data(f"https://api.openstreetmap.org/api/0.6/{osm_type}/{osm_id}.json")

            self.website = data_osm['elements'][0]['tags'].get('website', None)
            self.lat = data_nominatim[0]['lat']
            self.lon = data_nominatim[0]['lon']



def get_cinemas(file):
    with open(file, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')

    cinemas = soup.find_all(class_='item--cinema-content text-center')
    return cinemas



c = get_cinemas('cinemas-acceptant-ui.html')

all_cinemas = [Cinema(cine) for cine in c]


les_halles = all_cinemas[0]

