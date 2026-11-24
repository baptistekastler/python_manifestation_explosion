
"""
ACTIONS DU 17 OCTOBRE : CROISEMENT AVEC LES ÉQUIPEMENTS ET LE VOTE, RÉGRESSIONS DE POISSON

Données (toutes sur le S3, dossier spktaqlr/diffusion) :
    - commune_events_pop.csv  une ligne par commune : codgeo (code INSEE), has_event (true/false)
    - bpe.csv                 Base permanente des équipements (Insee)
    - vote.csv                législatives 2024, 1er tour, résultats par commune

Lancement : python explications/poisson.py
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd
import s3fs
import statsmodels.api as sm
import statsmodels.formula.api as smf

ICI = Path(__file__).resolve().parent                 # le dossier explications/
DOSSIER_S3 = "spktaqlr/diffusion"

# Connexion au S3 d'Onyxia
fs = s3fs.S3FileSystem(client_kwargs={"endpoint_url": "https://" + os.environ["AWS_S3_ENDPOINT"]})


def code_insee(serie):
    """Code commune à 5 caractères (1001 -> 01001). Paris, Lyon et Marseille sont parfois
    découpés en arrondissements (75101...) : on les regroupe en une seule commune."""
    codes = serie.astype(str).str.strip().str.upper().str.zfill(5)
    codes = codes.where(~codes.str.match(r"^751\d\d$"), "75056")   # Paris
    codes = codes.where(~codes.str.match(r"^6938\d$"), "69123")    # Lyon
    codes = codes.where(~codes.str.match(r"^132\d\d$"), "13055")   # Marseille
    return codes


# 1. ÉVÉNEMENTS : une ligne par commune, avec 1 s'il y a eu un événement, 0 sinon

# sep=None : pandas devine tout seul si le fichier est séparé par des virgules ou des points-virgules.
with fs.open(f"{DOSSIER_S3}/commune_events_pop.csv") as f:
    evenements = pd.read_csv(f, sep=None, engine="python", dtype={"CODGEO": str})
evenements["code_insee"] = code_insee(evenements["CODGEO"])

# has_event peut être lu comme du texte ("true"/"false") ou comme un booléen (True/False) :
# on convertit dans tous les cas en 1 / 0.
evenements["a_eu_action"] = evenements["has_event"].astype(str).str.strip().str.lower().isin(["true", "1"]).astype(int)

# Si Paris, Lyon ou Marseille apparaissent par arrondissement, on les regroupe :
# la commune a eu un événement si au moins un de ses arrondissements en a eu un.
evenements = evenements.groupby("code_insee", as_index=False)["a_eu_action"].max()
print(f"Événements : {len(evenements):,} communes, dont {evenements['a_eu_action'].sum():,} avec un événement")


# 2. BPE : nombre d'équipements par commune

# Le fichier est très lourd : on ne lit que le code commune (DEPCOM) et le domaine (DOM).
# DOM = "C" pour l'enseignement, "D" pour la santé et l'action sociale.
with fs.open(f"{DOSSIER_S3}/bpe.csv") as f:
    bpe = pd.read_csv(f, sep=";", usecols=["DEPCOM", "DOM"], dtype=str)
bpe["code_insee"] = code_insee(bpe["DEPCOM"])
bpe["est_education"] = bpe["DOM"] == "C"
bpe["est_sante"] = bpe["DOM"] == "D"
equipements = bpe.groupby("code_insee").agg(
    nb_equipements=("DOM", "size"),
    nb_education=("est_education", "sum"),
    nb_sante=("est_sante", "sum"),
).reset_index()
print(f"BPE : {len(bpe):,} équipements dans {len(equipements):,} communes")


# 3. VOTE : part de chaque bloc et participation, par commune

with fs.open(f"{DOSSIER_S3}/vote.csv") as f:
    vote_brut = pd.read_csv(f, sep=";", dtype=str, low_memory=False)
vote_brut["code_insee"] = code_insee(vote_brut["Code commune"])

# Colonnes "Nuance candidat 1", "Voix 1", "Nuance candidat 2", "Voix 2"... :
# on les empile pour avoir une ligne par candidat et par commune.
morceaux = []
for colonne in vote_brut.columns:
    if colonne.startswith("Nuance candidat "):
        numero = colonne.replace("Nuance candidat ", "")
        morceaux.append(pd.DataFrame({
            "code_insee": vote_brut["code_insee"],
            "nuance": vote_brut[colonne],
            "voix": pd.to_numeric(vote_brut[f"Voix {numero}"], errors="coerce"),
        }))
candidats = pd.concat(morceaux).dropna(subset=["nuance"])

# Nuances regroupées en blocs. On raisonne par bloc car l'offre varie selon la circonscription
# (l'extrême droite est représentée tantôt par un candidat RN, tantôt UXD).
BLOCS = {
    "EXG": "extreme_gauche",
    "COM": "gauche", "FI": "gauche", "SOC": "gauche", "VEC": "gauche", "RDG": "gauche",
    "DVG": "gauche", "UG": "gauche", "ECO": "gauche",
    "REN": "droite", "MDM": "droite", "HOR": "droite", "ENS": "droite", "DVC": "droite",
    "UDI": "droite", "LR": "droite", "DVD": "droite",
    "DSV": "extreme_droite", "RN": "extreme_droite", "REC": "extreme_droite",
    "UXD": "extreme_droite", "EXD": "extreme_droite",
    "REG": "divers", "DIV": "divers",
}
candidats["bloc"] = candidats["nuance"].map(BLOCS).fillna("divers")
voix_blocs = candidats.pivot_table(index="code_insee", columns="bloc", values="voix",
                                   aggfunc="sum", fill_value=0)

# Une grande ville couvre plusieurs circonscriptions (plusieurs lignes) : on ADDITIONNE.
for c in ["Inscrits", "Votants", "Exprimés"]:
    vote_brut[c] = pd.to_numeric(vote_brut[c], errors="coerce")
vote = vote_brut.groupby("code_insee")[["Inscrits", "Votants", "Exprimés"]].sum().join(voix_blocs)
for bloc in ["extreme_gauche", "gauche", "droite", "extreme_droite", "divers"]:
    vote[f"pct_{bloc}"] = vote[bloc] / vote["Exprimés"] * 100
vote["participation"] = vote["Votants"] / vote["Inscrits"] * 100
vote = vote.reset_index()
print(f"Vote : {len(vote):,} communes")


# 4. LA TABLE : une ligne par commune

# On part du fichier des événements (une ligne par commune, avec ou sans événement)
# et on y accroche le vote et les équipements.
df = (evenements
      .merge(vote, on="code_insee", how="inner")          # communes sans résultat de vote : écartées
      .merge(equipements, on="code_insee", how="left"))
for c in ["nb_equipements", "nb_education", "nb_sante"]:
    df[c] = df[c].fillna(0).astype(int)                   # absente de la BPE = 0 équipement
df = df[(df["Inscrits"] > 0) & (df["Exprimés"] > 0)].copy()

print(f"\nTable : {len(df):,} communes | {df['a_eu_action'].sum():,} avec un événement "
      f"({df['a_eu_action'].mean():.1%})")
# Contrôle : communes avec événement perdues à la fusion (absentes du fichier de vote)
perdues = evenements[(evenements["a_eu_action"] == 1) & ~evenements["code_insee"].isin(df["code_insee"])]
if len(perdues):
    print(f"  Attention : {len(perdues)} communes avec événement absentes du vote : "
          f"{perdues['code_insee'].head(10).tolist()}")

# --- Variables pour les régressions ---
# Taille de la commune : nombre d'inscrits (en log).
df["log_inscrits"] = np.log(df["Inscrits"])

# Vote divisé par 10 : un coefficient se lit « pour +10 points ».
for v in ["pct_extreme_gauche", "pct_gauche", "pct_extreme_droite", "pct_divers", "participation"]:
    df[f"{v}_10"] = df[v] / 10

# Équipements pour 1 000 inscrits. Dans les toutes petites communes ce ratio explose
# (une école pour 80 inscrits) : on prend le log, puis on standardise.
# Le coefficient se lit « pour un écart-type d'équipement en plus ».
dens = np.log1p(df["nb_equipements"] / df["Inscrits"] * 1000)
df["equipement_z"] = (dens - dens.mean()) / dens.std()

# Département : pour les effets fixes et pour grouper les erreurs-types.
df["dep"] = np.where(df["code_insee"].str.startswith("97"), df["code_insee"].str[:3], df["code_insee"].str[:2])

ICI.joinpath("sorties").mkdir(exist_ok=True)
df.to_csv(ICI / "sorties" / "table_communes.csv", index=False)


# 5. RÉGRESSIONS DE POISSON sur le fait d'avoir eu un événement (0/1)

# Pourquoi Poisson sur une variable 0/1 ? C'est une méthode classique (« Poisson modifié ») :
# avec des erreurs-types robustes, elle donne directement des RAPPORTS DE PROBABILITÉS.
#     effet_% = (exp(coefficient) - 1) x 100
# se lit : « la probabilité d'avoir eu un événement est X % plus élevée ».
# (C'est plus parlant qu'un logit, dont les coefficients sont des rapports de cotes.)
#
# Taille : on met log(inscrits) comme variable de contrôle. On n'utilise plus d'offset :
# une probabilité ne peut pas être proportionnelle à la taille (elle ne dépasse jamais 1).
#
# Les parts des blocs somment à 100 % : on ne peut pas toutes les mettre. La DROITE est omise
# (catégorie de référence) : chaque coefficient de bloc se lit « +10 points pour ce bloc, pris à la droite ».
#
# Erreurs-types groupées par département (les communes d'un même département se ressemblent).

VOTE = "pct_extreme_gauche_10 + pct_gauche_10 + pct_extreme_droite_10 + pct_divers_10"
MODELES = {
    "(1) vote + taille": f"a_eu_action ~ {VOTE} + log_inscrits",
    "(2) + participation et équipements": f"a_eu_action ~ {VOTE} + log_inscrits + participation_10 + equipement_z",
    "(3) + effets fixes département": f"a_eu_action ~ {VOTE} + log_inscrits + participation_10 + equipement_z + C(dep)",
}
VARIABLES = ["pct_extreme_gauche_10", "pct_gauche_10", "pct_extreme_droite_10", "pct_divers_10",
             "participation_10", "equipement_z", "log_inscrits"]

# Avec les effets fixes, un département sans AUCUN événement ne peut pas être estimé
# (son coefficient partirait à moins l'infini) : on retire ces départements pour le modèle (3).
dep_avec_evenement = df.groupby("dep")["a_eu_action"].transform("max") == 1

effets, pvalues = {}, {}
for nom, formule in MODELES.items():
    donnees = df[dep_avec_evenement] if "C(dep)" in formule else df
    modele = smf.glm(formule, data=donnees, family=sm.families.Poisson())
    res = modele.fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(donnees["dep"])[0]})
    garder = [v for v in VARIABLES if v in res.params.index]
    effets[nom] = (np.exp(res.params[garder]) - 1) * 100
    pvalues[nom] = res.pvalues[garder]

effets = pd.DataFrame(effets).reindex(VARIABLES)      # lignes dans l'ordre de VARIABLES
pvalues = pd.DataFrame(pvalues).reindex(VARIABLES)

print("\n" + "=" * 90)
print("Variation de la probabilité d'avoir eu un événement (en %)")
print("  vote et participation : pour +10 points | équipement : pour +1 écart-type")
print("  log_inscrits : pour une commune 2,7 fois plus grande | bloc de référence : droite")
print("=" * 90)
print(effets.round(1).to_string())
print("\np-values (< 0,05 : effet significatif au seuil de 5 %)")
print(pvalues.round(3).to_string())
print(f"\nModèle (3) : {(~dep_avec_evenement).sum():,} communes retirées "
      f"(départements sans aucun événement)")

effets.to_csv(ICI / "sorties" / "poisson_effets.csv")
pvalues.to_csv(ICI / "sorties" / "poisson_pvalues.csv")

# ajouter filosofi
