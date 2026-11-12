import argparse
import hashlib
import html
import json
import os
import re
import tempfile
import time
import unicodedata
from difflib import SequenceMatcher
from urllib.parse import urlparse

import folium
import requests
from bs4 import BeautifulSoup
from folium.plugins import MarkerCluster
from geopy.distance import distance

USER_AGENT = "UI-map/1.0 (https://github.com/thomas-saigre/ugc)"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URLS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)
WEBSITE_TAGS = ("website", "contact:website", "brand:website", "url")

# Threshold
RADIUS_PRECISE = 300        # m, around an adress precisely geocoded
RADIUS_CITY = 3000          # m, around a point « commune »
NAME_MATCH = 0.5            # minimal name match do be considered trustworthy
MAX_NAME_SEARCH_DIST = 1.0  # km, tolerated distance between researhc by name and adress


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #

class Http:
    """Session HTTP avec User-Agent identifiable, limitation de débit par hôte
    (1 requête/s, conformément à la politique d'usage de Nominatim) et
    nouvelles tentatives sur les erreurs temporaires."""

    def __init__(self, min_interval=1.0):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.min_interval = min_interval
        self._last = {}

    def _wait(self, host):
        elapsed = time.monotonic() - self._last.get(host, 0.0)
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last[host] = time.monotonic()

    def request(self, method, url, retries=3, **kwargs):
        host = urlparse(url).netloc
        for attempt in range(retries):
            self._wait(host)
            try:
                r = self.session.request(method, url, timeout=60, **kwargs)
                if r.status_code == 200:
                    return r.json()
                if r.status_code not in (429, 502, 503, 504):
                    print(f"    Erreur HTTP {r.status_code} sur {url}")
                    return None
                print(f"    HTTP {r.status_code} sur {host}, nouvelle tentative…")
            except (requests.RequestException, ValueError) as e:
                print(f"    Erreur sur {url} : {e}")
            time.sleep(5 * (attempt + 1))
        return None


# --------------------------------------------------------------------------- #
# Adresses et noms
# --------------------------------------------------------------------------- #

POSTCODE_RE = re.compile(r"(\d{5})\s+([^\d]+?)(?:\s+CEDEX(?:\s*\d+)?)?\s*$", re.IGNORECASE)
LEVEL_RE = re.compile(r"\b(?:niveau|level|floor|[ée]tage)\b\s*[-–]?\s*\d*", re.IGNORECASE)


def parse_address(address):
    """Sépare une adresse UGC en (rue, code postal, ville).

    >>> parse_address("10, rue Carnot (place de la Gare) 78160 MARLY-LE-ROI")
    ('10, rue Carnot (place de la Gare)', '78160', 'MARLY-LE-ROI')
    """
    m = POSTCODE_RE.search(address)
    if not m:
        return address.strip(), None, None
    street = address[:m.start()].strip(" ,-–")
    return street, m.group(1), m.group(2).strip()


def clean_street(street):
    """Retire les informations parasites pour le géocodage : niveaux,
    parenthèses, « Palais des Congrès », tirets orphelins.

    >>> clean_street("Forum des Halles - Niveau -3")
    'Forum des Halles'
    """
    s = LEVEL_RE.sub(" ", street)
    s = re.sub(r"\(.*?\)", " ", s)
    s = s.replace("Palais des Congrès", " ")
    s = re.sub(r"\s*[-–,]\s*(?=[-–,]|$)", "", s)  # tirets/virgules orphelins
    s = re.sub(r"^\s*[-–,]\s*", "", s)
    return " ".join(s.split())


def same_department(postcode_a, postcode_b):
    if not postcode_a or not postcode_b:
        return False
    return postcode_a.strip()[:2] == postcode_b.strip()[:2]


_STOPWORDS = {"le", "la", "les", "l", "cinema", "cinemas", "cine", "ugc", "de", "du", "des", "d"}


def normalize_name(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return " ".join(w for w in re.findall(r"[a-z0-9]+", s) if w not in _STOPWORDS)


def name_similarity(a, b):
    a, b = normalize_name(a), normalize_name(b)
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def get_website(tags):
    for key in WEBSITE_TAGS:
        value = tags.get(key)
        if value:
            value = value.split(";")[0].strip()
            return value if value.startswith(("http://", "https://")) else "https://" + value
    return None


# --------------------------------------------------------------------------- #
# Geocoder / OpenStreetMap
# --------------------------------------------------------------------------- #

class Geocoder:

    def __init__(self, http):
        self.http = http

    def _nominatim(self, **params):
        params = {"format": "jsonv2", "addressdetails": 1, "limit": 10, **params}
        return self.http.request("GET", NOMINATIM_URL, params=params) or []

    def geocode(self, address):
        """Renvoie (lat, lon, précision) avec précision 'address' ou 'city', ou None.
        Un résultat dont le département ne correspond pas au code postal est rejeté."""
        street, postcode, city = parse_address(address)
        street = clean_street(street)

        def valid(results):
            for r in results:
                if postcode is None or same_department(r.get("address", {}).get("postcode"), postcode):
                    return float(r["lat"]), float(r["lon"])
            return None

        if street:
            query = f"{street}, {postcode} {city}" if postcode else street
            found = valid(self._nominatim(q=query))
            if found:
                return (*found, "address")

        if postcode:
            found = valid(self._nominatim(postalcode=postcode, city=city, country="France"))
            if not found:
                found = valid(self._nominatim(postalcode=postcode, country="France"))
            if found:
                return (*found, "city")
        return None

    def cinemas_around(self, lat, lon, radius):
        query = (f'[out:json][timeout:25];'
                 f'nwr["amenity"="cinema"](around:{radius},{lat},{lon});'
                 f'out center tags;')
        data = {}
        for url in OVERPASS_URLS:
            data = self.http.request("POST", url, data={"data": query})
            if data is not None:
                break
        data = data or {}
        candidates = []
        for el in data.get("elements", []):
            point = el.get("center", el)
            if "lat" not in point:
                continue
            candidates.append({
                "osm_type": el["type"], "osm_id": el["id"],
                "lat": float(point["lat"]), "lon": float(point["lon"]),
                "tags": el.get("tags", {}),
            })
        return candidates

    def search_cinema_by_name(self, name, postcode, city):
        queries = [
            " ".join(x for x in (name, postcode, city) if x),
            f"{name} {city}" if city else None,
            name,
        ]
        tried = set()
        for query in queries:
            if not query or query in tried:
                continue
            tried.add(query)
            candidates = []
            for r in self._nominatim(q=query, extratags=1, limit=20):
                if r.get("type") != "cinema":
                    continue
                if postcode and not same_department(r.get("address", {}).get("postcode"), postcode):
                    continue
                tags = dict(r.get("extratags") or {})
                tags.setdefault("name", r.get("name", ""))
                candidates.append({
                    "osm_type": r["osm_type"], "osm_id": r["osm_id"],
                    "lat": float(r["lat"]), "lon": float(r["lon"]), "tags": tags,
                })
            if candidates:
                return candidates
        return []




class Cinema:

    def __init__(self, name, address):
        self.name = name
        self.address = address
        self.hash = hashlib.md5(f"{name}{address}".encode()).hexdigest()
        self.website = None
        self.lat = None
        self.lon = None
        self.osm_id = None
        self.osm_type = None
        self.checked = False
        self.note = None  # short explanation when checked = False

    @classmethod
    def from_tag(cls, tag):
        name_tag = tag.find(class_="color--white text-uppercase")
        address_tag = tag.find(class_="color--blue-grey")
        if name_tag is None or address_tag is None:
            return None
        return cls(name_tag.get_text(strip=True), " ".join(address_tag.get_text().split()))

    # -- persistance ------------------------------------------------------- #

    def to_dict(self):
        return {
            "hash": self.hash, "name": self.name, "address": self.address,
            "website": self.website, "lat": self.lat, "lon": self.lon,
            "osm_id": self.osm_id, "osm_type": self.osm_type,
            "checked": self.checked, "note": self.note,
        }

    def load(self, entry):
        self.website = entry.get("website")
        self.lat = float(entry["lat"]) if entry.get("lat") is not None else None
        self.lon = float(entry["lon"]) if entry.get("lon") is not None else None
        self.osm_id = entry.get("osm_id")
        self.osm_type = entry.get("osm_type")
        self.checked = bool(entry.get("checked"))
        self.note = entry.get("note")

    def apply_override(self, override):
        for key in ("lat", "lon", "website", "osm_id", "osm_type"):
            if key in override:
                setattr(self, key, override[key])
        self.checked = override.get("checked", True)
        self.note = override.get("note", "manually corrected")

    # -- localisation ------------------------------------------------------ #

    def _use(self, candidate, checked, note=None):
        self.lat, self.lon = candidate["lat"], candidate["lon"]
        self.osm_id, self.osm_type = candidate["osm_id"], candidate["osm_type"]
        self.website = get_website(candidate["tags"])
        self.checked = checked
        self.note = note

    def _rank(self, candidates, origin):
        """Rank the place candidates by similarity of name, then distance."""
        scored = []
        for c in candidates:
            sim = name_similarity(self.name, c["tags"].get("name", ""))
            dist = distance(origin, (c["lat"], c["lon"])).km if origin else 0.0
            scored.append((sim, dist, c))
        scored.sort(key=lambda t: (-t[0], t[1]))
        return scored

    def locate(self, geo):
        self.website = self.lat = self.lon = self.osm_id = self.osm_type = None
        self.checked, self.note = False, None
        _, postcode, city = parse_address(self.address)

        geocoded = geo.geocode(self.address)
        origin = geocoded[:2] if geocoded else None
        precise = geocoded is not None and geocoded[2] == "address"

        # 1. Cinemas OSM around address
        if geocoded:
            radius = RADIUS_PRECISE if precise else RADIUS_CITY
            ranked = self._rank(geo.cinemas_around(*origin, radius), origin)
            if ranked:
                sim, dist, best = ranked[0]
                if sim >= NAME_MATCH:
                    self._use(best, checked=True)
                    return
                if precise:
                    # Pas de nom ressemblant : on prend le plus proche de l'adresse
                    nearest = min(ranked, key=lambda t: t[1])
                    self._use(nearest[2], checked=False,
                              note=f"nom OSM différent : {nearest[2]['tags'].get('name', '?')}")
                    return
                if len(ranked) == 1:
                    self._use(best, checked=False,
                              note=f"seul cinéma de la commune : {best['tags'].get('name', '?')}")
                    return

        # 2. Recherche par nom dans le département
        ranked = self._rank(geo.search_cinema_by_name(self.name, postcode, city), origin)
        if ranked:
            sim, dist, best = ranked[0]
            if origin is None:
                self._use(best, checked=False, note="adresse non géocodée, trouvé par le nom")
                return
            if precise and dist <= MAX_NAME_SEARCH_DIST:
                self._use(best, checked=sim >= NAME_MATCH)
                return
            if not precise and dist <= RADIUS_CITY / 1000 * 3:
                self._use(best, checked=False, note="trouvé par le nom, adresse approximative")
                return

        # 3. Repli : point géocodé, sans objet OSM
        if geocoded:
            self.lat, self.lon = origin
            self.note = ("aucun cinéma OSM trouvé, position de l'adresse" if precise
                         else "aucun cinéma OSM trouvé, position de la commune")
        else:
            self.note = "introuvable"


# --------------------------------------------------------------------------- #
# Liste UGC + cache
# --------------------------------------------------------------------------- #

def read_json(path, default):
    if not path or not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        content = f.read().strip()
    return json.loads(content) if content else default


def write_json_atomic(path, data):
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


class UI:

    def __init__(self, source_file):
        with open(source_file, encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")
        tags = soup.find_all(class_="item--cinema-content text-center")
        self.cinemas = [c for c in (Cinema.from_tag(t) for t in tags) if c is not None]
        if len(self.cinemas) < len(tags):
            print(f"{len(tags) - len(self.cinemas)} block(s) ignored (name or address missing)")

    def __len__(self):
        return len(self.cinemas)

    def __getitem__(self, index):
        return self.cinemas[index]

    def update(self, cache_file, overrides_file=None, refresh=False, retry_unchecked=False):
        """Complète les données manquantes et enregistre le cache après chaque cinéma.

        Sont (re)cherchés : les cinémas absents du cache, ceux sans coordonnées,
        tous si refresh=True, et les non vérifiés si retry_unchecked=True."""
        cache = {e["hash"]: e for e in read_json(cache_file, [])}
        overrides = read_json(overrides_file, {})
        geo = None

        for i, cinema in enumerate(self.cinemas, 1):
            entry = cache.get(cinema.hash)
            todo = (refresh or entry is None or entry.get("lat") is None
                    or (retry_unchecked and not entry.get("checked")))
            if cinema.hash in overrides:
                todo = False
            if not todo:
                if entry:
                    cinema.load(entry)
            else:
                geo = geo or Geocoder(Http())
                print(f"[{i}/{len(self)}] {cinema.name}")
                cinema.locate(geo)
                cache[cinema.hash] = cinema.to_dict()
                write_json_atomic(cache_file, [cache[c.hash] for c in self.cinemas if c.hash in cache])

            if cinema.hash in overrides:
                cinema.apply_override(overrides[cinema.hash])

        # Écriture finale (retire aussi les cinémas qui ne sont plus dans la liste UGC)
        write_json_atomic(cache_file, [c.to_dict() for c in self.cinemas])

    def report(self):
        to_check = [c for c in self.cinemas if not c.checked]
        no_site = [c for c in self.cinemas if c.lat is not None and not c.website]
        if to_check:
            print(f"\n{len(to_check)} cinema(s) tp check (add an entry in overrides.json) :")
            for c in to_check:
                print(f"  {c.hash}  {c.name} — {c.address}\n      → {c.note}")
        if no_site:
            print(f"\n{len(no_site)} cinema(s) without website in OSM :")
            for c in no_site:
                ref = f"https://www.openstreetmap.org/{c.osm_type}/{c.osm_id}" if c.osm_id else c.hash
                print(f"  {c.name} ({ref})")


# --------------------------------------------------------------------------- #
# Carte
# --------------------------------------------------------------------------- #

CITIES = [
    ("Strasbourg", 48.5797, 7.7521, 15),
    ("Paris", 48.8566, 2.3522, 12),
    ("Lille", 50.6292, 3.0573, 14),
    ("Lyon", 45.7640, 4.8357, 14),
    ("Bordeaux", 44.8378, -0.5792, 14),
]

CONTROLS_TEMPLATE = """
<style>
.city-button {
  background-color: #fff; color: #333; padding: 8px 16px; margin: 4px;
  border: 1px solid #bbb; border-radius: 6px; box-shadow: 0 2px 6px rgba(0,0,0,0.08);
  cursor: pointer; font-size: 15px; transition: background 0.2s, color 0.2s, box-shadow 0.2s;
}
.city-button:hover { background-color: #007bff; color: #fff; box-shadow: 0 4px 12px rgba(0,123,255,0.15); }
#search-input { padding: 8px; border-radius: 6px; border: 1px solid #bbb; font-size: 15px; width: 220px; }
.info-box {
  position: fixed; bottom: 10px; left: 10px; z-index: 1000; background: white; padding: 5px 8px;
  border-radius: 5px; box-shadow: 0 0 5px rgba(0,0,0,0.5); max-width: 360px; max-height: 40vh; overflow: auto;
}
</style>
<div style="position: fixed; top: 10px; left: 50px; z-index: 1000;">
__BUTTONS__
  <input id="search-input" type="text" placeholder="Rechercher un lieu…">
  <button class="city-button" onclick="searchLocation()">Go</button>
</div>
<script>
function jumpToCity(lat, lng, zoom) { __MAP__.setView([lat, lng], zoom); }
function searchLocation() {
  var query = document.getElementById('search-input').value;
  if (!query) return;
  fetch('https://nominatim.openstreetmap.org/search?format=json&limit=1&q=' + encodeURIComponent(query))
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data && data.length > 0) {
        __MAP__.setView([parseFloat(data[0].lat), parseFloat(data[0].lon)], 15);
      } else { alert('Lieu introuvable.'); }
    })
    .catch(function () { alert('Erreur pendant la recherche.'); });
}
document.addEventListener('DOMContentLoaded', function () {
  var input = document.getElementById('search-input');
  if (input) input.addEventListener('keydown', function (e) { if (e.key === 'Enter') searchLocation(); });
});
</script>
"""


def draw_map(cinemas, filename="map.html"):
    m = folium.Map(location=[46.603354, 1.888334], zoom_start=6)
    cluster = MarkerCluster(name="UGC Illimité").add_to(m)

    missing = []
    for c in cinemas:
        if c.lat is None or c.lon is None:
            missing.append(c)
            continue
        name = html.escape(c.name)
        if c.website:
            title = f'<a href="{html.escape(c.website, quote=True)}" target="_blank" rel="noopener">{name}</a>'
        else:
            title = f"<b>{name}</b>"
        popup = f"{title}<br>{html.escape(c.address)}"
        folium.Marker(
            [c.lat, c.lon],
            popup=folium.Popup(popup, max_width=300),
            tooltip=c.name,
            icon=folium.Icon(color="darkblue" if c.checked else "orange", icon="film"),
        ).add_to(cluster)

    folium.LayerControl().add_to(m)

    buttons = "\n".join(
        f'  <button class="city-button" onclick="jumpToCity({lat}, {lon}, {zoom})">{html.escape(city)}</button>'
        for city, lat, lon, zoom in CITIES
    )
    controls = CONTROLS_TEMPLATE.replace("__BUTTONS__", buttons).replace("__MAP__", m.get_name())
    m.get_root().html.add_child(folium.Element(controls))

    missing_html = ""
    if missing:
        items = "".join(f"<li>{html.escape(c.name)} — {html.escape(c.address)}</li>" for c in missing)
        missing_html = (f"<details><summary>{len(missing)} cinéma(s) non localisé(s)</summary>"
                        f"<ul style='margin:4px 0; padding-left:18px'>{items}</ul></details>")
    info = f"""
    <div class="info-box">
      Source : <a href="https://www.ugc.fr/cinemas-acceptant-ui.html">ugc.fr</a><br>
      Date : {time.strftime("%Y-%m-%d")}<br>
      <span style="color:#d97c2b">●</span> position à vérifier
      {missing_html}
    </div>
    """
    m.get_root().html.add_child(folium.Element(info))

    m.save(filename)
    print(f"\nMap exported to {filename} ({len(cinemas) - len(missing)} cinemas in it, "
          f"{len(missing)} not localized)")




if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the map of all cinemas accepting the card UGC Illimité")
    parser.add_argument("output", nargs="?", default="map.html", help="Output file (the map)")
    parser.add_argument("--source", default="cinemas-acceptant-ui.html", help="Saved HTML page from UGC website [cinemas-acceptant-ui.html]")
    parser.add_argument("--cache", default="cinemas.json", help="cache of collected data [cinemas.json]")
    parser.add_argument("--overrides", default="overrides.json", help="manual corrections [overrides.json]")
    parser.add_argument("--refresh", action="store_true", help="relocate everything")
    parser.add_argument("--retry-unchecked", action="store_true", help="relocate non verified cinemas")
    args = parser.parse_args()

    ui = UI(args.source)
    ui.update(args.cache, args.overrides, refresh=args.refresh, retry_unchecked=args.retry_unchecked)
    ui.report()
    draw_map(ui.cinemas, args.output)
