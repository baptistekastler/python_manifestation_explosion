# j'importe la base de données des taxes locales
# j'ai préléablement mis dans le dossier diffusion qui se trouve dans data storage de ssp cloud 

import os
import s3fs
import pandas as pd

# Connexion au stockage S3 (MinIO) du SSP Cloud qui se trouve dasn data storage sur l'nterface
fs = s3fs.S3FileSystem(
    client_kwargs={"endpoint_url": f"https://{os.environ['AWS_S3_ENDPOINT']}"}
)

# definition de certaines variables et des chemins d'accès
DOSSIER = "spktaqlr/diffusion"
COL_SIREN = "sirepci"
COL_ANNEE = "exercice"

print(fs.ls(DOSSIER))  # verification de l'existence des fichier

# lecture des fichiers sur les votes de fiscalité locale
FICHIERS_FISCALITE = {
    2023: f"{DOSSIER}/fiscalite_locale_des_particuliers_2023.parquet",
    2024: f"{DOSSIER}/fiscalite_locale_des_particuliers_2024.parquet",
    2025: f"{DOSSIER}/fiscalite_locale_des_particuliers_2025.parquet",
}

# pour ouvrir et lire les fichiers de fiscalité locale

def lire_parquet(chemin, colonnes=None):
    """Lit un parquet sur S3, avec un message clair si le fichier est absent."""
    if not fs.exists(chemin):
        raise FileNotFoundError(f"Fichier introuvable : {chemin}")
    with fs.open(chemin) as f:
        return pd.read_parquet(f, columns=colonnes)

# pour préparer le merge de chaque commune sur base de leur numéro

def normaliser_siren(serie):
    """SIREN en texte de 9 chiffres (évite .0 et zéros perdus)."""
    return (
        serie.astype("string")
        .str.replace(r"\.0$", "", regex=True)
        .str.strip()
        .str.zfill(9)
    )


# Lecture des trois années 
fiscalite_par_annee = {
    annee: lire_parquet(chemin) for annee, chemin in FICHIERS_FISCALITE.items()
}

# Contrôles avant empilement
for annee, df in fiscalite_par_annee.items():
    print(annee, df.shape)

    manquantes = [c for c in (COL_SIREN, COL_ANNEE) if c not in df.columns]
    if manquantes:
        raise KeyError(
            f"Colonnes {manquantes} absentes dans le fichier {annee}. "
            f"Colonnes disponibles : {df.columns.tolist()}"
        )

# L'année contenue dans le fichier doit correspondre à celle du nom de fichier
    annees_presentes = sorted(pd.to_numeric(df[COL_ANNEE], errors="coerce").dropna().unique())
    if annees_presentes != [annee]:
        print(f"Attention : le fichier {annee} contient EXERCICE = {annees_presentes}")

colonnes_ref = set(fiscalite_par_annee[2023].columns)
for annee, df in fiscalite_par_annee.items():
    ecart = colonnes_ref ^ set(df.columns)
    if ecart:
        print(f"Attention : colonnes différentes en {annee} par rapport à 2023 : {sorted(ecart)}")

# Empilement des trois années ---
fiscalite_locale = pd.concat(fiscalite_par_annee.values(), ignore_index=True)

# Clés propres
fiscalite_locale["siren"] = normaliser_siren(fiscalite_locale[COL_SIREN])
fiscalite_locale["annee"] = pd.to_numeric(fiscalite_locale[COL_ANNEE], errors="coerce").astype("Int64")

invalides = ~fiscalite_locale["siren"].str.fullmatch(r"\d{9}", na=False)
print(f"Lignes avec SIREN invalide ou manquant : {invalides.sum()}")

# Résumé
print(fiscalite_locale.shape)
print(fiscalite_locale.groupby("annee").size())
print(fiscalite_locale.groupby(["siren", "annee"]).size().value_counts().head())

# Sauvegarde sur le stockage s3 de SSPcloud
with fs.open(f"{DOSSIER}/fiscalite_locale_2023_2025.parquet", "wb") as f:
     fiscalite_locale.to_parquet(f, index=False)

# Évolution de la population de Grasse exemple pour voir si ça marche bien 
COL_COMMUNE = "libcom"
COL_POP = "mpoid" 

# on extrait Grasse c'est là d'où je viens
grasse = fiscalite_locale[
    fiscalite_locale[COL_COMMUNE].astype("string").str.strip().str.upper().eq("GRASSE")
]

# on récupère la population  par année
pop = (
    grasse.assign(**{COL_POP: pd.to_numeric(grasse[COL_POP], errors="coerce")})
    .groupby("annee")[COL_POP]
    .first()          # une valeur par année
    .sort_index()
    .to_frame("population")
)

# ajouter les colonnes de variation pour le fun
pop["variation"] = pop["population"].diff()
pop["variation_%"] = (pop["population"].pct_change() * 100).round(2)

# pov : je ne comprends pas trop pourquoi y'a aussi 2021 et 2022
print(pop)