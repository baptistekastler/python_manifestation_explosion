import geopandas as gpd
import pandas as pd


# I. GEOJSON POUR AMÉLIORER LA BDD

# 1. Charger le CSV des actions du 17 octobre
df = pd.read_csv("bdd/just17.csv", sep=";", on_bad_lines="warn")

# Vérifier / convertir les coordonnées (adapte 'lat' et 'lon' si les colonnes ont un autre nom)
df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
df_valide = df.dropna(subset=["lat", "lon"]).copy()

# 2. Créer la géométrie à partir de (lon, lat)
gdf_actions = gpd.GeoDataFrame(
    df_valide,
    geometry=gpd.points_from_xy(df_valide["lon"], df_valide["lat"]),
    crs="EPSG:4326",
)

# 3. Croiser avec le fond de carte des communes
gdf_communes = gpd.read_file("bdd/communes-100m.geojson").to_crs("EPSG:4326")

gdf_joint = gpd.sjoin(
    gdf_actions,
    gdf_communes[["code", "nom", "geometry"]],
    how="left",
    predicate="within",
)

# 4. Récupérer un DataFrame propre avec le code INSEE
df_just17_communes = pd.DataFrame(
    gdf_joint.drop(columns=["geometry", "index_right"])
).rename(columns={"code": "code_insee", "nom": "nom_commune"})

# 5. Enregistrer le résultat en CSV
df_just17_communes.to_csv("bdd/just17_avec_insee.csv", index=False)


# II. LÉGISLATIVES2024 

# 1. Charger les actions géolocalisées
df_actions = pd.read_csv("bdd/just17_avec_insee.csv", dtype={"code_insee": str})
df_actions["code_insee"] = df_actions["code_insee"].astype(str).str.strip().str.zfill(5)

nb_actions_commune = (
    df_actions.dropna(subset=["code_insee"])
    .groupby("code_insee", as_index=False)
    .size()
    .rename(columns={"size": "nb_actions"})
)

# 2. Lire uniquement l'en-tête de législatives-2024.csv pour cibler les colonnes utiles
chemin_leg = "bdd/legislatives-2024.csv"
cols_all = pd.read_csv(chemin_leg, sep=";", nrows=0).columns.tolist()

cols_base = [
    "Code département",
    "Libellé département",
    "Code commune",
    "Libellé commune",
    "Inscrits",
    "Votants",
    "Exprimés",
]
cols_nuances = [c for c in cols_all if c.startswith("Nuance candidat ")]
cols_voix = [c for c in cols_all if c.startswith("Voix ")]

cols_utiles = [c for c in (cols_base + cols_nuances + cols_voix) if c in cols_all]

df_leg = pd.read_csv(
    chemin_leg,
    sep=";",
    usecols=cols_utiles,
    dtype={"Code département": str, "Code commune": str},
    low_memory=False,
)

# 3. Reconstruire code_insee proprement
dep = df_leg["Code département"].astype(str).str.strip()
com = df_leg["Code commune"].astype(str).str.strip()
df_leg["code_insee"] = [
    (d.zfill(3) + c.zfill(2)) if len(d) >= 3 else (d.zfill(2) + c.zfill(3))
    for d, c in zip(dep, com)
]

# 4. Sommer les voix par nuance politique pour chaque ligne (commune)
# On récupère les numéros de panneaux existants (1, 2, 3, ...)
voix_par_nuance = {}
for c_nuance in cols_nuances:
    idx = c_nuance.replace("Nuance candidat ", "")
    c_voix = f"Voix {idx}"
    if c_voix not in df_leg.columns:
        continue
    nuances_series = df_leg[c_nuance].dropna().unique()
    for n in nuances_series:
        masque = df_leg[c_nuance] == n
        voix_num = pd.to_numeric(df_leg.loc[masque, c_voix], errors="coerce").fillna(0)
        if n not in voix_par_nuance:
            voix_par_nuance[n] = pd.Series(0.0, index=df_leg.index)
        voix_par_nuance[n].loc[masque] += voix_num

df_voix_nuances = pd.DataFrame(voix_par_nuance, index=df_leg.index).add_prefix("voix_")

# Convertir Exprimés en numérique et calculer les % par nuance
exprimes = pd.to_numeric(df_leg["Exprimés"], errors="coerce")
df_pct_nuances = df_voix_nuances.div(exprimes.replace(0, pd.NA), axis=0) * 100
df_pct_nuances.columns = [c.replace("voix_", "pct_") for c in df_pct_nuances.columns]

# 5. Assembler avec les infos de base et nb_actions
df_table = pd.concat(
    [
        df_leg[["code_insee", "Libellé commune", "Inscrits", "Votants", "Exprimés"]],
        df_pct_nuances,
    ],
    axis=1,
)

# S'il y a plusieurs lignes par code_insee (ex. 2 tours ou communes découpées), agréger :
# Ici on garde la moyenne des % par commune (ou adapte selon ton besoin)
cols_pct = list(df_pct_nuances.columns)
df_communes_vote = df_table.groupby("code_insee", as_index=False)[cols_pct].mean()

df_final = pd.merge(df_communes_vote, nb_actions_commune, on="code_insee", how="left")
df_final["nb_actions"] = df_final["nb_actions"].fillna(0)

# 6. Calculer les corrélations avec nb_actions
corrs = df_final[cols_pct + ["nb_actions"]].corr(method="spearman")["nb_actions"].sort_values(ascending=False)
print(corrs)