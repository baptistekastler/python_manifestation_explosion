"""
ACTIONS DU 17 OCTOBRE : CROISEMENT AVEC LES ÉQUIPEMENTS ET LE VOTE, RÉGRESSIONS DE POISSON

Données :
    - bdd/just17_avec_insee.csv         actions du 17 octobre, rattachées à une commune (dans le dépôt)
    - S3 : spktaqlr/diffusion/bpe.csv   Base permanente des équipements (Insee)
    - S3 : spktaqlr/diffusion/vote.csv  législatives 2024, 1er tour, résultats par commune

Lancement : python explications/analyse_poisson.py
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd
import s3fs
import statsmodels.api as sm
import statsmodels.formula.api as smf

ICI = Path(__file__).resolve().parent                 # le dossier explications/
FICHIER_ACTIONS = ICI.parent / "bdd" / "just17_avec_insee.csv"
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



# 1. ACTIONS : nombre d'actions par commune

actions = pd.read_csv(FICHIER_ACTIONS, dtype={"code_insee": str, "id": str})
actions = actions.dropna(subset=["code_insee"])        # actions sans commune : impossibles à placer
actions = actions.drop_duplicates(subset="id")         # une même action ne compte qu'une fois
actions["code_insee"] = code_insee(actions["code_insee"])
nb_actions = actions.groupby("code_insee").size().rename("nb_actions").reset_index()
print(f"Actions : {len(actions):,} réparties dans {len(nb_actions):,} communes")



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

# On part des communes du fichier de vote (toutes les communes de France), pour garder
# aussi celles qui n'ont eu ni action ni équipement.
df = (vote
      .merge(nb_actions, on="code_insee", how="left")
      .merge(equipements, on="code_insee", how="left"))
for c in ["nb_actions", "nb_equipements", "nb_education", "nb_sante"]:
    df[c] = df[c].fillna(0).astype(int)
df = df[(df["Inscrits"] > 0) & (df["Exprimés"] > 0)].copy()

print(f"\nTable : {len(df):,} communes | {(df['nb_actions'] > 0).sum():,} avec au moins une action | "
      f"{df['nb_actions'].sum():,} actions sur {len(actions):,}")
# Actions perdues = actions dont la commune n'est pas dans le fichier de vote
perdues = nb_actions[~nb_actions["code_insee"].isin(df["code_insee"])]
if len(perdues):
    print(f"  Attention : {perdues['nb_actions'].sum()} actions dans des communes absentes du vote : "
          f"{perdues['code_insee'].head(10).tolist()}")

# --- Variables pour les régressions ---
# Taille de la commune : on utilise le nombre d'inscrits (pas besoin d'un fichier de population).
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



# 5. RÉGRESSIONS DE POISSON sur le nombre d'actions

# Pourquoi Poisson : nb_actions est un comptage (0, 1, 2...), avec beaucoup de 0.
# Le modèle estime E[nb_actions] = exp(...), donc des effets en POURCENTAGE :
#     effet_% = (exp(coefficient) - 1) x 100
#
# offset = log(inscrits) : on modélise un nombre d'actions PAR INSCRIT. Sans ça, les grandes
# communes auraient « plus d'actions » simplement parce qu'elles sont grandes.
#
# Les parts des blocs somment à 100 % : on ne peut pas toutes les mettre. La DROITE est omise
# (catégorie de référence) : chaque coefficient de bloc se lit « +10 points pour ce bloc, pris à la droite ».
#
# Erreurs-types groupées par département (les communes d'un même département se ressemblent).

VOTE = "pct_extreme_gauche_10 + pct_gauche_10 + pct_extreme_droite_10 + pct_divers_10"
MODELES = {
    "(1) vote seul": f"nb_actions ~ {VOTE}",
    "(2) + participation et équipements": f"nb_actions ~ {VOTE} + participation_10 + equipement_z",
    "(3) + effets fixes département": f"nb_actions ~ {VOTE} + participation_10 + equipement_z + C(dep)",
}
VARIABLES = ["pct_extreme_gauche_10", "pct_gauche_10", "pct_extreme_droite_10", "pct_divers_10",
             "participation_10", "equipement_z"]

effets, pvalues = {}, {}
for nom, formule in MODELES.items():
    modele = smf.glm(formule, data=df, family=sm.families.Poisson(), offset=df["log_inscrits"])
    res = modele.fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(df["dep"])[0]})
    garder = [v for v in VARIABLES if v in res.params.index]
    effets[nom] = (np.exp(res.params[garder]) - 1) * 100
    pvalues[nom] = res.pvalues[garder]

effets = pd.DataFrame(effets).reindex(VARIABLES)      # lignes dans l'ordre de VARIABLES
pvalues = pd.DataFrame(pvalues).reindex(VARIABLES)

print("\n" + "=" * 90)
print("Variation du nombre d'actions par inscrit (en %)")
print("  vote et participation : pour +10 points | équipement : pour +1 écart-type")
print("  bloc de référence : droite")
print("=" * 90)
print(effets.round(1).to_string())
print("\np-values (< 0,05 : effet significatif au seuil de 5 %)")
print(pvalues.round(3).to_string())

effets.to_csv(ICI / "sorties" / "poisson_effets.csv")
pvalues.to_csv(ICI / "sorties" / "poisson_pvalues.csv")

# ajouter filosofi
