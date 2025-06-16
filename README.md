# UGC

Map of cinemas that accept the card "UGC Illimité" in France.


## Description

A Python script that scrapes the [page that gathers all the cinemas that accept the card "UGC Illimité"](https://www.ugc.fr/cinemas-acceptant-ui.html) and retrieve geographical data about them, using OpenStreetMap.

> [!NOTE]
> The page "Cinemas accpetant UI" used to generate the map have been synced on 18/05/2025.



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

-



## Usage

After having downloaded the page `cinemas-acceptant-ui.html` (and saved it under this name), run the following code

```bash
python3 ugc.py
```

For some cinemas, something could have gone wrong (issue in the requests, cinema not found, etc...), in some cases the cinema will be included in the database, but with `checked = False`, as the program was not able to check if everythin was correct.
The cinema not checked appear in light blue on the map.

If the code is run again with the file `cinemas.json` present in the directory, it won't re-searche for them again.
