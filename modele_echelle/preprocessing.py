"""
Module de préparation des données pour les régressions
"""

import pandas as pd
import plotnine
import numpy as np


def table_reg_essence_prix(df: pd.DataFrame, zone: str) -> pd.DataFrame:
    """Résumé par zone : population, prix moyen des carburants, nombre d'événements.

    Args:
        df (pd.DataFrame): table d'évènements par ville, avec la population
        zone (str): colonne de la zone géographique

    Returns:
        pd.DataFrame: une ligne par zone
    """
    df_unique = df.drop_duplicates("COM")

    evenements = df.groupby(zone)["has_event"].sum().rename("evenements")

    events = df_unique.groupby(zone).agg(
        pop_totale=("PMUN", "sum"),
        prix_gazole=("gazole", "mean"),
        prix_e10=("e10", "mean"),
    )
    events["prix_moyen"] = events[["prix_gazole", "prix_e10"]].mean(axis=1) * 100 #on ne fait pas de moyenne manuelle parce qu'il manque le prix de l'e10 en Corse

    return (
        events.join(evenements)
        .drop(columns=["prix_gazole", "prix_e10"])
        .reset_index()
    ) 
    
