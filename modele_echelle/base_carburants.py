import csv
import xml.etree.ElementTree as ET
import importlib.util
import os
import pandas as pd
import geopandas as gpd

# pour pouvoir utiliser AR_S3 en tant que module alors qu'on est dans un autre dossier
spec = importlib.util.spec_from_file_location(
    "AR_S3", "bdd/AR_S3.py"
)
ar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ar)

#ar.envoyer_vers_s3("PrixCarburants_annuel_2026.xml", "base_carburants_2026.xml")

# ar.recuperer_depuis_s3("base_carburants_2026.xml", "bdd/base_carburants_2026.xml")

FICHIER = "bdd/base_carburants_2026.xml"
JOUR = "2026-10-17"
FIN_JOUR = JOUR + "T23:59:59"   # les dates ISO se comparent comme du texte


def convertir(coord):
    """Convertit '4620138' en 46.20138. Renvoie None si absent ou nul."""
    if not coord:
        return None
    try:
        v = int(coord)
    except ValueError:
        return None
    return v / 100000 if v != 0 else None


# with open("bdd/prix_2026-10-17.csv", "w", newline="", encoding="utf-8") as out:
#     w = csv.writer(out)
#     w.writerow(["id", "cp", "ville", "lat", "lon",
#                 "carburant", "prix", "maj", "maj_le_jour"])

#     for _, pdv in ET.iterparse(FICHIER, events=("end",)):
#         if pdv.tag != "pdv":
#             continue

#         # dernière mise à jour <= 17/10 23:59:59, par carburant
#         dernier = {}
#         for p in pdv.findall("prix"):
#             maj = p.get("maj")
#             if maj and maj <= FIN_JOUR:
#                 nom = p.get("nom")
#                 if nom not in dernier or maj >= dernier[nom][0]:
#                     dernier[nom] = (maj, p.get("valeur"))

#         ville = (pdv.findtext("ville") or "").strip()
#         lat = convertir(pdv.get("latitude"))
#         lon = convertir(pdv.get("longitude"))

#         for nom, (maj, val) in dernier.items():
#             w.writerow([
#                 pdv.get("id"), pdv.get("cp"), ville, lat, lon,
#                 nom, float(val), maj, maj.startswith(JOUR),
#             ])

#         pdv.clear()   # libère la mémoire

# os.remove("bdd/base_carburants_2026.xml")



def merge_carburants_communes(
    all_communes_events: pd.DataFrame,
    prix_17_10: pd.DataFrame,
    chemin_communes: str = ( 
        "https://etalab-datasets.geo.data.gouv.fr/contours-administratifs/"
        "2024/geojson/communes-1000m.geojson"
     ),    
     col_code_contours: str = "code",
    ) -> pd.DataFrame:
    """Remplace les prix des carburants par la moyenne des stations de la commune.

    Args:
        all_communes_events: table d'événements par commune (avec `code_insee`).
        prix_17_10: prix par station (colonnes id, lat, lon, carburant, prix).
        chemin_communes: fichier de contours des communes.
        col_code_contours: nom de la colonne du code INSEE dans les contours.

    Returns:
        pd.DataFrame: all_communes_events avec une colonne de prix par carburant
        (gazole, e10, sp95, sp98, e85, gplc) et nb_stations.
    """
    # une ligne par station, une colonne par carburant (tous les carburants)
    prix = prix_17_10.dropna(subset=["lat", "lon"])
    stations = (
        prix.pivot_table(index=["id", "lat", "lon"], columns="carburant",
                         values="prix", aggfunc="mean")
        .reset_index()
    )
    stations.columns = [str(c).lower() for c in stations.columns]
    carburants = [c for c in stations.columns if c not in ("id", "lat", "lon")]

    pts = gpd.GeoDataFrame(
        stations,
        geometry=gpd.points_from_xy(stations["lon"], stations["lat"]),
        crs="EPSG:4326",
    )

    # jointure spatiale station -> commune
    communes = gpd.read_file(chemin_communes)[[col_code_contours, "geometry"]]
    communes = communes.to_crs("EPSG:4326")
    pts = gpd.sjoin(pts, communes, how="left", predicate="within")

    # prix moyen par commune, pour chaque carburant
    agg = {c: (c, "mean") for c in carburants}
    agg["nb_stations"] = ("id", "nunique")
    prix_commune = (
        pts.dropna(subset=[col_code_contours])
        .groupby(col_code_contours)
        .agg(**agg)
        .reset_index()
        .rename(columns={col_code_contours: "code_insee"})
    )

    # fusion : on écarte les anciens prix scrapés
    anciens = [c for c in all_communes_events.columns if c.lower() in carburants]
    events = all_communes_events.drop(columns=anciens).copy()
    events["code_insee"] = events["code_insee"].astype(str).str.zfill(5)

    return events.merge(prix_commune, on="code_insee", how="left")