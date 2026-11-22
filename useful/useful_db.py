import numpy as np
import pandas as pd
import geopandas as gpd
import folium
from folium.plugins import MarkerCluster


def liste_colonnes(df):
    """Permet simplement d'afficher une liste des colonnes d'un df

    Args:
        df (pd.DataFrame): un df

    Returns:
        list : des str avec les noms des colonnes
    """
    for col in df.columns.to_list():
        print(f"  -{col!s}")

def merger_communes_event_bool(all_communes, scraped) -> pd.DataFrame:
    """Fusionne les tables pour avoir des stats sur les communes au niveau de la France

    Args:
        all_communes (pd.DataFrame): fichier appartenance geo communes de l'Insee
        scraped (pd.DataFrame): évènements recensés sur 17octobregiletsjaunes.net

    Returns:
        pd.DataFrame: table fusionnée avec les données de toutes les communes, pour faire des statistiques descriptives sur toute la France.
    """
    communes = all_communes.copy()
    evenements = scraped.copy()

    evenements = evenements.unique("ville")

    






def merger_communes_event_types(all_communes, scraped, type) -> pd.DataFrame:
    """Permet de faire des stats sur les types d'évènements

    Args:
        all_communes (_type_): _description_
        scraped (_type_): _description_

    Returns:
        pd.DataFrame: _description_
    """
    communes = all_communes.copy()
    evenements = scraped.copy()

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

    #centre de la carte
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

