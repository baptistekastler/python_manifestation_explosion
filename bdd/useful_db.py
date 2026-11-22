import numpy as np
import pandas as pd

# table d'appartenance des communes à des zones géographiques
all_communes = pd.read_excel(
    "/home/onyxia/python_manifestation_explosion/bdd/table-appartenance-geo-communes-2026.xlsx",
    header=5,
    dtype=str,
    engine="calamine",
)

scraped = pd.read_csv("/home/onyxia/python_manifestation_explosion/bdd/just17_avec_insee.csv")

def merger_communes(all_communes, scraped) -> pd.DataFrame :
    """_summary_

    Args:
        all_communes (_type_): _description_
        scraped (_type_): _description_

    Returns:
        pd.DataFrame: table fusionnée avec un 
    """

