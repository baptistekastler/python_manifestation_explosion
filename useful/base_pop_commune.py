# Ce code permet de merge les deux bases de données de population des communes et des lieux des manifestations 
# pour ensuite l'utiliser pour pondérer les cartes 
import pandas as pd
from useful_db import ajouter_code_insee

all_communes_events = pd.read_csv("/home/onyxia/work/python_manifestation_explosion/bdd/all_communes_events.csv", sep=";")

from bdd.AR_S3 import recuperer_depuis_s3, envoyer_vers_s3

recuperer_depuis_s3("donnees_communes.csv","/home/onyxia/work/python_manifestation_explosion/bdd/pop_commune.csv")
pop_commune = pd.read_csv("/home/onyxia/work/python_manifestation_explosion/bdd/pop_commune.csv", sep=";")

print(pop_commune.head())

pop_commune.info()

# nous avions un pb dans le merge car Paris Lyon Marseille étaient en arrondissement dans une base 
# et non dans l'autre, on a donc aggrégé à l'échelon communal avec ce qui suit
ARRONDISSEMENTS = {
    "75056": [f"751{i:02d}" for i in range(1, 21)],
    "69123": [f"6938{i}" for i in range(1, 10)],
    "13055": [f"132{i:02d}" for i in range(1, 17)],
}
VERS_COMMUNE = {arr: com for com, arrs in ARRONDISSEMENTS.items() for arr in arrs}

pop_commune["COM"] = pop_commune["COM"].astype("string").str.strip().str.zfill(5)
pop_commune["COM"] = pop_commune["COM"].replace(VERS_COMMUNE)

cols_somme = ["PMUN"] 
autres = [c for c in pop_commune.columns if c not in cols_somme + ["COM"]]

agg = {c: "sum" for c in cols_somme}
agg.update({c: "first" for c in autres})
pop_commune = pop_commune.groupby("COM", as_index=False).agg(agg)

pop_commune = pop_commune.drop(columns=["REG", "DEP"])

all_communes_events["CODGEO"] = all_communes_events["CODGEO"].astype("string")

# gardons à l'esprit qu'environ 250 mobilissation sne se sont pas vus apposé un code_insee

commune_events_pop = all_communes_events.merge(pop_commune, 
    left_on="CODGEO",
    right_on="COM", 
    how="left",
)

print(len(commune_events_pop), len(all_communes_events))
print(pop_commune["COM"].duplicated().sum())

commune_events_pop.to_csv(
    "/home/onyxia/work/python_manifestation_explosion/bdd/commune_events_pop.csv",
    sep=";",
    index=False,
)
envoyer_vers_s3("/home/onyxia/work/python_manifestation_explosion/bdd/commune_events_pop.csv")