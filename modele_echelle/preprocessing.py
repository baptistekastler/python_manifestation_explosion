"""
Module de préparation des données pour les régressions
"""

import pandas as pd
import plotnine
import numpy as np
import bdd.AR_S3 as s3

def pop_ville(villes=all_communes_events, pop)->pd.DataFrame:
    """Joint une table avec toute les villes et evenèments et celle avec les populations des villes

    Args:
        villes (pd.DataFrame): all_communes_events
        pop (pd.DataFrame): les populations données par l'Insee

    Returns:
        pd.DataFrame: le df avec toutes les infos
    """
    pop = pop.drop(columns = ["REG", "Région", "DEP","CODARR", "CODCAN", "Commune", "PCAP", "PTOT"])
    new = pd.merge(
        left=villes,
        right=pop,
        left_on="CODGEO",
        right_on="COM",
        how="inner"
    )

    return new

def table_reg_essence_prix(df: pd.DataFrame, zone: str) -> pd.DataFrame:
    """_summary_

    Args:
        df (pd.DataFrame): une table d'évènements par ville, avec la population
        zone (str): une zone géographique

    Returns:
        pd.DataFrame: _description_
    """
    events = df.groupby(zone).agg(
        nb_events=("has_event", "sum"),
        prix_gazole=("gazole", "mean"),
        prix_e10=("e10", "mean"),
    )
    events["prix moyen"] = (events["prix_gazole"] + events["prix_e10"]) / 2 * 100
    return events.drop(columns=["prix_gazole", "prix_e10"])
