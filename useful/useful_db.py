import numpy as np
import pandas as pd
import geopandas as gpd
import folium
from folium.plugins import MarkerCluster
from cartiflette import carti_download
import ipywidgets

import sys
sys.path.append("/home/onyxia/work/python_manifestation_explosion")

from bdd.AR_S3 import get_fs, envoyer_vers_s3, recuperer_depuis_s3

URL_COMMUNES = (
    "https://etalab-datasets.geo.data.gouv.fr/contours-administratifs/"
    "{year}/geojson/communes-1000m.geojson"
)


def ajouter_code_insee(
    df: pd.DataFrame,
    lon_col: str = "lon",
    lat_col: str = "lat",
    year: int = 2024,
    code_col: str = "code_insee",
) -> pd.DataFrame:
    """Ajoute les codes Insee aux évènements à partir de leurs coordonnées GPS et d'un fichier geojson disponible dans sur etalab

    Args:
        df (pd.DataFrame): _description_
        lon_col (str, optional): _description_. Defaults to "lon".
        lat_col (str, optional): _description_. Defaults to "lat".
        year (int, optional): _description_. Defaults to 2024.
        code_col (str, optional): _description_. Defaults to "code_insee".

    Returns:
        pd.DataFrame: un df avec une colonne en plus
    """
    df = df.copy()

    lon = pd.to_numeric(df[lon_col], errors="coerce")
    lat = pd.to_numeric(df[lat_col], errors="coerce")
    valides = lon.notna() & lat.notna()

    communes = gpd.read_file(URL_COMMUNES.format(year=year))[["code", "geometry"]]
    communes = communes.to_crs(4326)

    points = gpd.GeoDataFrame(
        df.loc[valides, []],
        geometry=gpd.points_from_xy(lon[valides], lat[valides]),
        crs=4326,
    )

    joint = gpd.sjoin(points, communes, how="left", predicate="within")
    joint = joint[~joint.index.duplicated(keep="first")]

    df[code_col] = pd.NA
    df.loc[joint.index, code_col] = joint["code"]
    return df


def merge_communes(df, all_communes)-> pd.DataFrame:
    """_summary_

    Args:
        df (pd.DataFrame): Un df avec tous les évènements
        all_communes (pd.DataFrame): un df avec toutes les communes 

    Returns:
        pd.DataFrame: _description_
    """
    communes = all_communes.copy()
    evenements = df.copy()

    communes["CODGEO"] = communes["CODGEO"].astype(str).str.strip().str.zfill(5)

    # Gestion propre des éventuels NaN ou floats (ex: 1001.0 -> '01001') dans code_insee
    evenements["code_insee"] = (
        evenements["code_insee"]
        .astype("string")
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.zfill(5)
    )

    #jointure à gauche, avec les données au format long (une ligne / evenement)
    merged = communes.merge(
        evenements,
        left_on="CODGEO",
        right_on="code_insee",
        how="left",
    )

    merged["has_event"] = merged["id"].notna()

    return merged




def desc_bool(df)->pd.DataFrame:
    """génère une table qui donne la proportion de communes où il y a eu un évènement

    Args:
        df (pd.DataFrame): une table avec toutes les communes, où seules les communes où il n'y a pas eu d'évènement ont des NA dans la colonne 'title'

    Returns:
        pd.DataFrame: la table descriptive
    """
    df_clean = df.drop_duplicates(subset=["CODGEO"])
    effectifs = df_clean["has_event"].value_counts(dropna=False)
    stats = pd.DataFrame(
        {
            "Effectif": effectifs,
            "Proportion (%)": (effectifs / len(df_clean) * 100).round(2),
        }
    )
    stats.index = stats.index.map({True: "Avec événement", False: "Sans événement"})
    return stats


def desc_types_events(df)->pd.DataFrame:
    """génère une table qui donne les porportions d'évènements.

    Args:
        df (pd.DataFrame): table au format long

    Returns:
        pd.DataFrame: la table descriptive
    """
    effectifs = df["title"].value_counts(dropna=False)

    nb_communes = len(df.drop_duplicates(subset=["CODGEO"]))

    stats = pd.DataFrame(
        {
            "Effectif": effectifs,
            "Proportion (%)": (effectifs / nb_communes * 100).round(1),
        }
    )

    stats.index = stats.index.str.replace("_", " ").str.capitalize()
    stats.index.name = "Par types d'évènements"

    stats = stats[stats.index != "NaN"]
    return stats


# création d'une fonction qui assigne une couleur de folium à chaque type d'évènement


couleurs_actions = {
    "rond_point": "red",
    "barrage_filtrant": "darkred",
    "operation_escargot": "purple",
    "blocage": "blue",
    "manifestation": "orange",
    "rassemblement": "beige",
    "assemblee": "green",
    "prise_de_parole": "lightgreen",
    "pancartes": "lightblue",
    "tractage": "cadetblue",
    "piquet_de_greve": "darkpurple",
    "autre": "gray",
}


def couleur_evenement(val: str) -> str:
    """Associe une couleur à un évènement

    Args:
        val (str): un type d'évènement

    Returns:
        str: une couleur
    """
    if not isinstance(val, str):
        return "lightgray"
    return couleurs_actions.get(val.strip().lower(), "lightgray")


# fonctions pour faire des cartes


def carte_events(scraped):
    df = scraped.copy()
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df = df.dropna(subset=["lat", "lon"])

    # centre de la carte
    center = df[["lat", "lon"]].mean().values.tolist()
    sw = df[["lat", "lon"]].min().values.tolist()
    ne = df[["lat", "lon"]].max().values.tolist()

    m = folium.Map(location=center, tiles="OpenStreetMap")
    marker_cluster = MarkerCluster().add_to(m)

    # Ajout des marqueurs dans le MarkerCluster
    for row in df.itertuples():
        lieu = row.commune if pd.notna(row.commune) else row.ville
        titre = str(row.title).capitalize()
        popup_html = (
            f"<b>{titre}</b><br>"
            f"Lieu : {lieu}<br>"
            f"Date : {row.date} ({row.heure})<br>"
            f"Adresse : {row.adresse}"
        )

        folium.Marker(
            location=[row.lat, row.lon],
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=f"{titre} — {lieu}",
            icon=folium.Icon(
                color=couleur_evenement(row.title),
                icon="info-sign",
                prefix="glyphicon",
            ),
        ).add_to(marker_cluster)

    # 4. Ajustement automatique du zoom aux bornes des points
    m.fit_bounds([sw, ne])

    return m
