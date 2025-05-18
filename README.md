# UGC

Map of cinemas that accept the card "UGC Illimité" in France.


## Description

This project is composed of two parts:

1. A Python script that scrapes the [page that gathers all the cinemas that accept the card "UGC Illimité"](https://www.ugc.fr/cinemas-acceptant-ui.html) and retrieve geographical data about them, using OpenStreetMap.



## Data set

To avoid making many requests to OpenStreetMap, the data are saved in a JSON file.
The data stored are:
- a hash, which is a key to identify the cinema (from its name and address present in the original webpage)
- the name of the cinema,
- its address,
- its website,
- its coordinates (latitude and longitude),
- the `osm_id` of the node in OpenStreetMap.


## Spotted an error ?

Si vous avez repéré une erreur dans l'emplacement d'un cinéma, n'hésitez pas à me le signaler ;)

Le programme automatique comporte quelques failles (par exemple si plusieurs cinémas portent le même nom, ça peut pointer vers le mauvais), dans la carte, les cinémas qui apparaissent en bleu foncé ont été manuellement vérifiés, et ceux en bleu clair sont ceux qui n'ont pas été vérifiés.


## Notes for some cinemas


### Plusieurs entrées même cinéma

- Certains cinémas ont plusieurs entrées dans OpenStreetMap, car ils ont plusieurs entrées. C'est le cas pour `MK2 NATION` et `MK2 BIBLIOTHEQUE`.


### Plusieurs cinémas, même nom

- Il y a 2 cinémans `ESPACE SAINT MICHEL` en France selon OSM (un à Paris, et un à Aurignac), le premier dans la liste (celui de Paris) est le bon.
- Le `Cin'Hoche` (un à Sartrouville, et un à Bobigny), le premier dans la liste (celui de Sartrouville) est le bon.
- Il y a plein de cinémas `CINEMA LE STUDIO`, et par défaut OSM ne trouve pas le bon. Voici l'entrée faite manuellement :

```json
{
  "hash": "5ce20d8ee79920a1c9fe393c022b3324",
  "name": "CINEMA LE STUDIO",
  "address": "2 rue Edouard Poisson 93300 AUBERVILLIERS",
  "website": "https://lestudio-aubervilliers.fr",
  "lat": "48.9107503",
  "lon": "2.3839544",
  "osm_id": 5426835938
}
```

- Le `CINEMA JACQUES PREVERT`, on veut celuis d'Aulnay-sous-Bois, mais ce n'est pas le premier dans la liste. Voici l'entrée faite manuellement :

```json
{
  "hash": "739b6b894d44049fb74e3e7039fb3062",
  "name": "CINEMA JACQUES PREVERT",
  "address": "134 rue Anatole France 93600 AULNAY SOUS BOIS",
  "website": "http://www.tcprevert.fr/",
  "lat": "48.9401482",
  "lon": "2.4966187",
  "osm_id": 555733637
}
```

- `CINÉMA VOX`, le premier de la liste (Strasbourg) est le bon
- `L'ÉCRAN`, le premier de la liste (Saint-Denis) est le bon
- `Les Écrans`, le premier de la liste (Toucoing) est le bon

- `LE LIDO`, il faut le faire à la main :

```json
{
  "hash": "db6a6464bfb621173ff5590d901d46ac",
  "name": "LE LIDO",
  "address": "Place Jacques Tati \u2013 70 avenue de la R\u00e9publique 94100 SAINT-MAUR-DES-FOSS\u00c9S",
  "website": "https://www.cinemas-theatresaintmaur.com/",
  "lat": "48.798593",
  "lon": "2.485662",
  "osm_id": 137484040
}
```

- Piège: Le Lido de Limoges, le premier de la liste est le bon.


### Non trouvé par OSM

- `LE SAINT-ANDRÉ DES ARTS` n'est pas trouvé par la requête OSM. Voici l'entrée faite à la main

```json
{
  "hash": "2fbf5d5f3eac2858e7b85c791031ab3b",
  "name": "LE SAINT-ANDRÉ DES ARTS",
  "address": "30 Rue Saint-André des Arts, 75006 Paris",
  "website": "https://cinemasaintandre.com/",
  "lat": 48.8533737,
  "lon": 2.3421249,
  "osm_id": 1427978194
}
```

- Le `CINÉMA LOUIS JOUVET` n'est pas trouvé par la requête OSM. Voici l'entrée faite à la main

```json
{
  "hash": "1435e78580dc5ec0ae198b9bcd33a6fa",
  "name": "CIN\u00c9MA LOUIS JOUVET",
  "address": "3 place Maurice Berteaux 78400 CHATOU",
  "website": "https://www.cinechatou.fr/",
  "lat": "4.8868384",
  "lon": "2.1562778",
  "osm_id": 7831646897
},
```

- `LE COSMOS` non trouvé:
```json
{
  "hash": "e0491e7bf81e8e83e5e7aa884ff2cafe",
  "name": "LE COSMOS",
  "address": "3, rue des Francs-Bourgeois 67000 STRASBOURG",
  "website": "https://cinema-cosmos.eu/",
  "lat": "48.5826499",
  "lon": "7.7459938",
  "osm_id": 163991622,
  "checked": true
}
```


- OSM ne trouve pas le `MAX LINDER`, premier essai : remplacer par `Max Linder Panorama` dans le fichier HTML.
- OSM ne trouve pas le Palace de Cambray, premier essai : remplacer par `Cinéma Le Palace` dans le fichier HTML.