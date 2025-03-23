import requests
import time
import json
import hashlib
from bs4 import BeautifulSoup


def request_OSM_data(url, headers={'User-Agent': 'UI-map/1.0 (https://github.com/thomas-saigre/ugc)'}):
    # print(f"Requesting data from {url}")
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
        self.address = ' '.join(tag.find(class_='color--blue-grey').text.strip().split())
        self.set_hash()
        self.website = None
        self.lat = None
        self.lon = None
        self.are_data_gathered = False

    def get_infos_from_OSM(self):
        data_nominatim = request_OSM_data(f"https://nominatim.openstreetmap.org/search?q={self.name}&format=json")
        if data_nominatim:
            if len(data_nominatim) > 1:
                print(f"Multiple results found for {self.name}, please check results !")
            osm_id = data_nominatim[0]['osm_id']
            osm_type = data_nominatim[0]['osm_type']

            data_osm = request_OSM_data(f"https://api.openstreetmap.org/api/0.6/{osm_type}/{osm_id}.json")

            try:
                self.website = data_osm['elements'][0]['tags'].get('website', None)
                self.lat = data_nominatim[0]['lat']
                self.lon = data_nominatim[0]['lon']
            except:
                print(f"Failed to retrieve data for {self.name}")
                return None
            self.are_data_gathered = True

    def set_hash(self):
        hash_input = f"{self.name}{self.address}".encode()
        self.hash = hashlib.md5(hash_input).hexdigest()


class UI:

    def __init__(self, file):
        self.get_cinemas(file)


    def __getitem__(self, index):
        return self.cinemas[index]

    def get_cinemas(self, file):
        with open(file, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'html.parser')

        cinemas = soup.find_all(class_='item--cinema-content text-center')
        self.cinemas = [Cinema(cinema) for cinema in cinemas]

    def export_data(self, file):
        data = []
        for cinema in self.cinemas:
            if cinema.are_data_gathered:
                data.append({
                    cinema.hash: {
                        'name': cinema.name,
                        'address': cinema.address,
                        'website': cinema.website,
                        'lat': cinema.lat,
                        'lon': cinema.lon
                    }
                })

        with open(file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def __len__(self):
        return len(self.cinemas)

    def get_infos_for_all_cinemas(self, export_file=None, export_at_each_step=False):
        data = []
        if export_file:
            with open(export_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        for cinema in self.cinemas:
            if any(cinema.hash in entry for entry in data):
                continue
            else:
                cinema.get_infos_from_OSM()
                if cinema.are_data_gathered:
                    data.append({
                        cinema.hash: {
                            'name': cinema.name,
                            'address': cinema.address,
                            'website': cinema.website,
                            'lat': cinema.lat,
                            'lon': cinema.lon
                        }
                    })
                    if export_at_each_step and export_file:
                        with open(export_file, 'w', encoding='utf-8') as f:
                            json.dump(data, f, indent=2)







c = UI('cinemas-acceptant-ui.html')
c.get_infos_for_all_cinemas('cinemas.json', export_at_each_step=True)
