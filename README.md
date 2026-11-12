# UGC

Map of cinemas that accept the card "UGC Illimité" in France.

Version 2 (with some vibe coding...)

## Description

A Python script that scrapes the [page that gathers all the cinemas that accept the card "UGC Illimité"](https://www.ugc.fr/cinemas-acceptant-ui.html) and retrieve geographical data about them, using OpenStreetMap.

> [!NOTE]
> The page "Cinemas accpetant UI" used to generate the map have been synced on 29/10/2026.



## Data set

To avoid making many requests to OpenStreetMap, the data are saved in a JSON file.
The data stored are:
- a hash, which is a key to identify the cinema (from its name and address present in the original webpage)
- the name of the cinema,
- its address,
- its website,
- its coordinates (latitude and longitude),
- the `osm_id` of the entry in OpenStreetMap.


## Spotted an error ?

<!-- LTeX: language=fr -->

Si vous avez repéré une erreur dans l'emplacement d'un cinéma ou sur les données, n'hésitez pas à [me le signaler](https://github.com/thomas-saigre/ugc/issues) ;)

Le programme automatique comporte quelques failles (par exemple si plusieurs cinémas portent le même nom, ça peut pointer vers le mauvais), dans la carte, les cinémas qui apparaissent en bleu foncé ont été manuellement vérifiés, et ceux en bleu clair sont ceux qui n'ont pas été vérifiés.

<!-- LTeX: language=en-US -->

## Notes for some cinemas

The code is not perfect : some cinemas are not correctly found, or not found at all.
This is a small proportion of them (around 20), so the author choose to manually fix the corresponding entries.



## Usage

After having downloaded the page `cinemas-acceptant-ui.html` (and saved it under this name), run the following code

```bash
python3 ugc.py            # writes map.html
```

Options:

| Option | Description |
|--------|-------------|
| `--source FILE` | UGC page to read (default: `cinemas-acceptant-ui.html`) |
| `--cache FILE` | data collected so far (default: `cinemas.json`) |
| `--overrides FILE` | manual corrections (default: `overrides.json`) |
| `--refresh` | locate every cinema again and re-download the OSM data |
| `--retry-unchecked` | locate again only the cinemas marked as unchecked |

For each cinema, the script geocodes its address with Nominatim, then looks for the matching OpenStreetMap cinema nearby.

Results are saved in `cinemas.json` after each cinema.
On the next run, cinemas already located are skipped, so only new ones in the UGC list are searched.

When the script cannot confirm a result (address not found, no matching OSM cinema, name too different…), the cinema is kept with `checked = false` and shown in **orange** on the map. Cinemas that could not be located at all are not placed on the map; they are listed in the box at the bottom left. At the end of each run, the script prints every cinema to check, with its hash and the reason.

### Manual corrections (`overrides.json`)

To fix a cinema by hand, add an entry to `overrides.json`, using the hash printed by the script as the key:

```json
{
    "419c11e1f7aa4545d59fa544cecc15e4": {
       "lat": 48.8655,
       "lon": 2.3236,
       "website": "https://jeudepaume.org/",
       "osm_type": "way",
       "osm_id": 54188994
    }
}
```

All fields are optional (`lat`, `lon`, `website`, `checked`, `note`): only what you provide is replaced. Overrides are applied last and take priority over the automatic results; a cinema with an override is marked as checked and is no longer searched.

### See the map

To open the map, use a server :

```bash
python3 -m http.server 8000
```
