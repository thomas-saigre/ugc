import requests
import time
import json
import hashlib
from bs4 import BeautifulSoup
import folium
from folium.plugins import MarkerCluster
from geopy.geocoders import Nominatim
import re
import sys


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

def clean_address(address):
    """Cleans the address by removing level information and extra whitespace.
    Example:
        clean_address("Forum des Halles - Niveau -3 75001 PARIS") = "Forum des Halles - 75001 PARIS"

    Args:
        address (str): The address string to be cleaned.

    Returns:
        str: cleaned address
    """
    # Remove level information using regular expressions
    # This pattern matches common ways to denote levels or floors, including standalone hyphens
    cleaned_address = re.sub(r'(\s*[-–]\s*\d+|\bNiveau\b|\bLevel\b|\bFloor\b|\bEtage\b)', '', address, flags=re.IGNORECASE)
    cleaned_address = cleaned_address.replace('Palais des Congrès', '')
    # Remove any extra whitespace
    cleaned_address = ' '.join(cleaned_address.split())
    return cleaned_address

def get_coordinates(address):
    time.sleep(1)
    geolocator = Nominatim(user_agent="geoapi")
    cleaned_address = clean_address(address)

    try:
        location = geolocator.geocode(cleaned_address)

        if location:
            return (location.latitude, location.longitude)
        else:
            return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

def check_coordinates(test_coordinates, real_coordinates, threshold=0.01):
    if abs(float(test_coordinates[0]) - real_coordinates[0]) < threshold and abs(float(test_coordinates[1]) - real_coordinates[1]) < threshold:
        return True
    else:
        print(f"Coordinates for do not match: OSM ({test_coordinates[0]}, {test_coordinates[1]}), Geocoder ({real_coordinates[0]}, {real_coordinates[1]})")
        return False

class Cinema:

    def __init__(self, tag):
        self.name = tag.find(class_='color--white text-uppercase').text.strip()
        self.address = ' '.join(tag.find(class_='color--blue-grey').text.strip().split())
        self.set_hash()
        self.website = None
        self.lat = None
        self.lon = None
        self.are_data_gathered = False
        self.osm_id = None
        self.checked = False

    def get_infos_from_OSM(self):
        url = f"https://nominatim.openstreetmap.org/search?q={self.name}&format=json"
        data_nominatim = request_OSM_data(url)

        coordinates = get_coordinates(self.address)
        if coordinates is None:
            warning_msg = f"Failed to retrieve coordinates for {self.name} at {clean_address(self.address)}"
            print(warning_msg)

        if data_nominatim:
            data_nominatim = [item for item in data_nominatim if item.get('type') == 'cinema']

            if len(data_nominatim) == 0:
                print(f"No cinema found for {self.name}. Please check manually. Hash is {self.hash}")
                return

            for item in data_nominatim:
                to_check = False
                osm_id = item.get('osm_id')
                osm_type = item.get('osm_type')

                url = f"https://api.openstreetmap.org/api/0.6/{osm_type}/{osm_id}.json"
                data_osm = request_OSM_data(url)

                self.website = data_osm['elements'][0]['tags'].get('website', None)
                if not self.website:
                    self.website = data_osm['elements'][0]['tags'].get('contact:website', None)
                    if not self.website:
                        self.website = data_osm['elements'][0]['tags'].get('brand:website', None)
                        if not self.website:
                            print(f"Failed to retrieve website for {self.name} on {url}. Hash is {self.hash}")
                lat = data_nominatim[0]['lat']
                lon = data_nominatim[0]['lon']

                if coordinates is None:
                    print(f"Coordinates for {self.name} at {clean_address(self.address)} could not be retrieved. Using OSM coordinates, {len(data_nominatim)} were found")
                    to_check = Trueto_check = True
                    if len(data_nominatim) == 1:
                        print(f"\tUsing the only result found: {data_nominatim[0]['display_name']}")
                    else:
                        print(f"\tUsing the first result found: {data_nominatim[0]['display_name']}. Please check manually if this is the correct one.")


                    coordinates = (float(lat), float(lon))

                if check_coordinates((lat, lon), coordinates):
                    self.lat = lat
                    self.lon = lon
                    self.osm_id = osm_id
                    self.checked = not to_check
                    break

                if item == data_nominatim[-1]:
                    print(f"Reached the last OSM result for {self.name} and no matching coordinates were found. Please check manually. Hash is {self.hash}")
            self.are_data_gathered = True

        else:
            self.checked = False
            self.lat = None
            self.lon = None
            self.osm_id = None
            self.website = None
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
                        'hash': cinema.hash,
                        'name': cinema.name,
                        'address': cinema.address,
                        'website': cinema.website,
                        'lat': cinema.lat,
                        'lon': cinema.lon,
                        'osm_id': cinema.osm_id,
                        'checked': cinema.checked,
                })
        with open(file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def import_data(self, file):
        with open(file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for cinema in self.cinemas:
            for entry in data:
                if cinema.hash == entry['hash']:
                    cinema.website = entry['website']
                    cinema.lat = entry['lat']
                    cinema.lon = entry['lon']
                    cinema.osm_id = entry['osm_id']
                    cinema.are_data_gathered = True
                    cinema.checked = entry['checked']


        with open(file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def __len__(self):
        return len(self.cinemas)

    def get_infos_for_all_cinemas(self, export_file=None, export_at_each_step=False, load_file=False):
        """Get infos for all cinemas

        Args:
            export_file (str, optional): Path to the file where previous data are stored. For an empty file, create a file with only [] in it. Defaults to None.
            export_at_each_step (bool, optional): Update export_file at each step. Defaults to False.
        """
        data = []
        if load_file:
            self.import_data(export_file)
            with open(export_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        for cinema in self.cinemas:
            # print(f"Getting data for {cinema.name}")
            hash_list = [entry['hash'] for entry in data]
            if cinema.hash in hash_list:
                # print(f"       Data already gathered for {cinema.name}")
                continue
            else:
                cinema.get_infos_from_OSM()
                if cinema.are_data_gathered:
                    data.append({
                            'hash': cinema.hash,
                            'name': cinema.name,
                            'address': cinema.address,
                            'website': cinema.website,
                            'lat': cinema.lat,
                            'lon': cinema.lon,
                            'checked': cinema.checked,
                    })
                    if export_at_each_step and export_file:
                        self.export_data(export_file)


class Map:

    def __init__(self, ui: UI):
        self.ui = ui

    def get_buttons_str(self, cities=["Strasbourg", "Paris"], latitudes=[48.5734, 48.8566], longitudes=[7.7521, 2.3522], zooms=[15, 13]):
        buttons = '<div style="position: fixed; top: 10px; left: 50px; z-index: 1000;">\n'
        for city, lat, lon, zoom in zip(cities, latitudes, longitudes, zooms):
            buttons += f"  <button onclick='jumpToCity({lat}, {lon}, {zoom})'>{city}</button>\n"
        buttons += '</div>\n'
        return buttons

    def draw_map(self, name="map.html"):

        m = folium.Map(location=[46.603354, 1.888334], zoom_start=6)
        marker_cluster = MarkerCluster().add_to(m)

        for cinema in self.ui.cinemas:
            if cinema.are_data_gathered:
                popup = f"<a href='{cinema.website}'>{cinema.name}</a><br>{cinema.address}"
                # dans la mer si on n'a pas de coordonnée
                if cinema.lat is None: cinema.lat = 46.91931896308067
                if cinema.lon is None: cinema.lon = -2.7073753368667157
                folium.Marker(
                    [cinema.lat, cinema.lon],
                    popup=popup,
                    # icon=folium.Icon(color='green') if cinema.checked else folium.Icon(color='red'),
                    icon=folium.Icon(color='darkblue', icon="film") if cinema.checked else folium.Icon(color='blue', icon="film"),
                ).add_to(marker_cluster)

        folium.LayerControl().add_to(m)



        # Add buttons for zooming to specific cities with absolute positioning using JavaScript
        buttons_html = """
<div style="position: fixed; top: 10px; left: 50px; z-index: 1000;">
    <button onclick="jumpToCity(48.5797, 7.7521, 16)">Strasbourg</button>
    <button onclick="jumpToCity(48.8566, 2.3522, 12)">Paris</button>
</div>
<script>
    function jumpToCity(lat, lng, zoom) {
        var map = Object.values(window).find(obj => obj instanceof L.Map);
        if (map) {
            map.setView([lat, lng], zoom);
        }
    }
</script>
"""
        m.get_root().html.add_child(folium.Element(buttons_html))

        today = time.strftime("%Y-%m-%d")

        # Add a text at the bottom left of the page
        text_html = f"""
        <div style="position: fixed; bottom: 10px; left: 10px; z-index: 1000; background-color: white; padding: 5px; border-radius: 5px; box-shadow: 0px 0px 5px rgba(0,0,0,0.5);">
            Source : <a href="https://www.ugc.fr/cinemas-acceptant-ui.html">ugc.fr</a><br>
            Date : {today}
        </div>
        """
        m.get_root().html.add_child(folium.Element(text_html))

        m.save(name)


if __name__ == "__main__":

    if len(sys.argv) > 1:
        map_filename = sys.argv[1]
    else:
        map_filename = "map.html"

    c = UI('cinemas-acceptant-ui.html')
    data = c.get_infos_for_all_cinemas('cinemas.json', export_at_each_step=True, load_file=True)

    map = Map(c)
    map.draw_map(map_filename)