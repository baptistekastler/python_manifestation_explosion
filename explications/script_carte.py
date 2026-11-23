import os
import s3fs
import pandas as pd
import geopandas as gpd
import folium
import mapclassify
from folium.plugins import FastMarkerCluster

# Attention ici il faut installer des packages avec pip install -U et le nom du package dans le terminal 
# Cela permet jusqu'au 27 novembre d'avoir accès au s3 des données 
# Je le changerai ensuite
os.environ["AWS_ACCESS_KEY_ID"] = "4OFV1U0N8PIHG73XGCB0"
os.environ["AWS_SECRET_ACCESS_KEY"] = "EmyhmET6KDRSGKSEtBRQmZcaRv7kSEAdg+ujxX4N"
os.environ["AWS_SESSION_TOKEN"] = "eyJhbGciOiJIUzUxMiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3NLZXkiOiI0T0ZWMVUwTjhQSUhHNzNYR0NCMCIsImF1ZCI6Im1pbmlvLWRhdGFub2RlIiwiYXV0aF90aW1lIjoxNzk1MTg1OTY2LCJhenAiOiJvbnl4aWEiLCJlbWFpbCI6ImJhcHRpc3RlLmthc3RsZXJAZW5zYWUuZnIiLCJlbWFpbF92ZXJpZmllZCI6dHJ1ZSwiZXhwIjoxNzk1NzkwNzY5LCJmYW1pbHlfbmFtZSI6Ikthc3RsZXIiLCJnaXZlbl9uYW1lIjoiQmFwdGlzdGUiLCJncm91cHMiOlsiVVNFUl9PTllYSUEiXSwiaWF0IjoxNzk1MTg1OTY5LCJpc3MiOiJodHRwczovL2F1dGgubGFiLnNzcGNsb3VkLmZyL2F1dGgvcmVhbG1zL3NzcGNsb3VkIiwianRpIjoib25ydHJ0OjZjZTJhMzA0LWQzNTAtMDRkZS1hZDE5LTJhMGYwZmY4ZWYxOSIsImxvY2FsZSI6ImZyIiwibmFtZSI6IkJhcHRpc3RlIEthc3RsZXIiLCJvbnl4aWEtdXNlcm5hbWUiOiJzcGt0YXFsciIsInBvbGljeSI6InN0c29ubHksc3Rzb25seTIiLCJwcmVmZXJyZWRfdXNlcm5hbWUiOiJzcGt0YXFsciIsInNjb3BlIjoib3BlbmlkIHByb2ZpbGUgZW1haWwgcmVzb3VyY2U6bWluaW8iLCJzaWQiOiJ0OXRIS3poR3FIYWJyMFNBQlpoamY2b1oiLCJzdWIiOiIxNGQxNDUxZS00Mzg1LTQyZmYtYmE2OS1lMTIzY2M4N2EwMTIiLCJ0eXAiOiJCZWFyZXIifQ.UjnhwtnHKN2MIVMyB2FbNiuxpnZrgHkkvojocElkXTHS8SZGj_8FXhhF5irvQOcq57nnH0FfWz6LZpclIjUO3Q"

# Connexion au stockage S3 du SSP Cloud qui se trouve 
# dans data storage sur l'nterface
def get_fs():
    s3fs.S3FileSystem.clear_instance_cache()
    return s3fs.S3FileSystem(
        client_kwargs={"endpoint_url": f"https://{os.environ['AWS_S3_ENDPOINT']}"}
    )
fs = get_fs()

DOSSIER = "spktaqlr/diffusion" # définition du chemin d'accès


# ouverture du fichier obtenu avec le fichier script merge
with fs.open(f"{DOSSIER}/action_17_octobre_geolocalise.parquet", "rb") as f:
    df = pd.read_parquet(f)

print(df[["lat", "lon", "ville", "dep"]].head())
# ici on nettoie les données pour être sûr que cela fonctionne bien 

df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
valides = df["lat"].between(-90, 90) & df["lon"].between(-180, 180)
print(f"{valides.sum()} lignes avec coordonnées valides sur {len(df)}")

# cela permet de contrôler le fait que les départements sont bien écris avec deux chiffres et non 1 
df["dep"] = (
    df["dep"].astype("string").str.strip().str.upper()
    .str.replace(r"\.0$", "", regex=True)
    .str.zfill(2)
)

geo = df[valides].copy()

# ceci permet de créer une carte de points et c'est claude qui le fait. Je ne sais pas trop ce qu'il s'y passe
carte_points = folium.Map(location=[46.6, 2.5], zoom_start=6, tiles="OpenStreetMap")
FastMarkerCluster(geo[["lat", "lon"]].values.tolist()).add_to(carte_points)

html_points = carte_points.get_root().render()
with fs.open(f"{DOSSIER}/carte_points.html", "w", encoding="utf-8") as f:
    f.write(html_points)
print(f"Carte de points enregistrée : {DOSSIER}/carte_points.html")

# pour pouvoir avoir des couleurs on compte le nombre d'actions/ de points par départements
par_dep = geo.groupby("dep").size().rename("nb_points").reset_index()
print(par_dep.sort_values("nb_points", ascending=False).head(10))

# ici on utilise l'extension cartiflette conseillé par claude pour pouvoir faire la carte
try:
    from cartiflette import carti_download

    deps = carti_download(
        values="France",
        crs=4326,
        borders="DEPARTEMENT",
        vectorfile_format="geojson",
        filter_by="FRANCE_ENTIERE",
        source="EXPRESS-COG-CARTO-TERRITOIRE",
        year=2024,
    )
    print(deps.columns.tolist())

    col_dep = next(c for c in deps.columns if c.upper() in ("INSEE_DEP", "CODE", "DEP"))
    deps = deps.rename(columns={col_dep: "dep"})
    deps["dep"] = deps["dep"].astype(str).str.zfill(2)

    carte = deps.merge(par_dep, on="dep", how="left").fillna({"nb_points": 0})
    m = carte.explore(
        column="nb_points", cmap="OrRd", legend=True, tiles="cartodbpositron",
        scheme="quantiles", k=5,

    )

    html_deps = m.get_root().render()
    with fs.open(f"{DOSSIER}/carte_departements.html", "w", encoding="utf-8") as f:
        f.write(html_deps)
        print(f"Carte par département enregistrée : {DOSSIER}/carte_departements.html")

except Exception as e:
    print("Carte par département non générée :", e)
    print("La carte de points reste utilisable.")