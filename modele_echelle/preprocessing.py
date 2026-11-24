"""
Module de préparation des données pour les régressions
"""

import pandas as pd
import plotnine
import numpy as np

def table_reg_essence_prix(df: pd.DataFrame, zone: str) -> pd.DataFrame:
    """Résumé par zone : population totale, prix moyen pondéré par la population, événements.

    Args:
        df (pd.DataFrame): table d'événements par commune avec population et prix.
        zone (str): nom de la colonne du découpage géographique ('DEP', 'REG', etc.).

    Returns:
        pd.DataFrame: table agrégée avec une ligne par zone.
    """
    df = df.copy()
    df[zone] = df[zone].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)

    evenements = (
        df.groupby(zone)["has_event"]
        .sum()
        .astype(int)
        .rename("evenements")
    )

    df_unique = df.drop_duplicates(subset=["COM"]).copy()
    df_unique["prix_carbu"] = df_unique[["gazole", "e10"]].mean(axis=1)

    pop_totale = df_unique.groupby(zone)["PMUN"].sum().rename("pop_totale")

    valides = df_unique.dropna(subset=["prix_carbu", "PMUN"]).copy()
    valides["pop_x_prix"] = valides["PMUN"] * valides["prix_carbu"]

    agg_prix = valides.groupby(zone).agg(
        somme_produit=("pop_x_prix", "sum"),
        pop_renseignee=("PMUN", "sum"),
    )
    prix_moyen = (
        (agg_prix["somme_produit"] / agg_prix["pop_renseignee"]) * 100
    ).rename("prix_moyen")

    return (
        pd.concat([pop_totale, prix_moyen, evenements], axis=1)
        .reset_index()
        .rename(columns={"index": zone})
    )
