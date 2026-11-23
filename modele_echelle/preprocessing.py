"""
Module de préparation des données pour les régressions
"""

import pandas as pd
import plotnine
import numpy as np


def table_reg_essence_prix(df: pd.DataFrame, zone: str) -> pd.DataFrame:
    """_summary_

    Args:
        df (pd.DataFrame): une table d'évènements par ville
        zone (str): une zone géographique

    Returns:
        pd.DataFrame: _description_
    """
    events = df.groupby(zone).agg(
        nb_events=("has_event", "sum"),
        prix_gazole=("gazole", "mean"),
        prix_e10=("e10", "mean"),
    )

    # centrer et réduire les variables, car les prix de l'essence sont très resserrés :

    for col in ("prix_gazole", "prix_e10"):
        events[col] = (events[col] - events[col].mean()) / events[col].std()
    
    return events
