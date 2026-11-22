# Dans ce script je vais merge les deux bases de données
# de manifs et merge avec 
# le document fiscalité locale que j'ai
# je commence par lire les deux fichiers de manifs

import os
import s3fs
import pandas as pd

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

with fs.open(f"{DOSSIER}/actions.csv", mode="rb") as f:
    actions_17_octobre = pd.read_csv(f)

with fs.open(f"{DOSSIER}/lieux.csv", mode="rb") as f:
    lieux_actions = pd.read_csv(f)

# 2. Nom de la colonne ID permettant la liaison
# Remplacez 'id_lieu' par le nom exact de la colonne d'identifiant commune
colonne_id = 'id' 

# 3. Fusion (Merge) en jointure externe ('outer') pour ne perdre aucune donnée
action_17_octobre_localise = pd.merge(
    actions_17_octobre, 
    lieux_actions, 
    on=colonne_id, 
    how='outer',
    suffixes=('_action', '_lieu')  # Ajoute un suffixe en cas de colonnes avec le même nom dans les 2 fichiers
)

# 4. Vérification du résultat
print(f"Nombre d'actions initiales : {len(actions_17_octobre)}")
print(f"Nombre de lieux initiaux : {len(lieux_actions)}")
print(f"Nombre de lignes après fusion : {len(action_17_octobre_localise)}")

# Aperçu des premières lignes
print(action_17_octobre_localise.head())
# Attention le résultat du terminal montre qu'il y a moins d'actions que de lieux ce qui est logique
# Il ya  cependant 486 actions qui n'ont pas de lieu 
# Cela nous laisse 1906 lignes exploitables
# Nombre d'actions initiales : 2392
# Nombre de lieux initiaux : 20008
# Nombre de lignes après fusion : 20486


# transformation de la base de données pour qu'elle ait le code insee des endroits
# comme ça on pourra facilement la relier à d'autres bases de données

import pandas as pd
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

# Nettoyage et conversion des coordonnées pour éviter l'erreur 'NaN/infinite'
action_17_octobre_localise['lat'] = pd.to_numeric(action_17_octobre_localise['lat'], errors='coerce')
action_17_octobre_localise['lon'] = pd.to_numeric(action_17_octobre_localise['lon'], errors='coerce')

# Initialisation du géocodeur Nominatim
geolocator = Nominatim(user_agent="mon_application_insee")
# Permet de respecter les règles d'utilisation de l'API (1 seconde entre chaque requête)
reverse = RateLimiter(geolocator.reverse, min_delay_seconds=1)

# Fonction pour extraire le code INSEE d'une coordonnée (lat, lon)
def obtnir_code_insee(lat, lon):
    if pd.isna(lat) or pd.isna(lon):
        return None
    try:
        location = reverse((lat, lon), exactly_one=True)
        if location and 'address' in location.raw:
            address = location.raw['address']
            # Nominatim stocke souvent le code INSEE sous 'ref:INSEE' ou à défaut utilise le code postal
            return address.get('ref:INSEE') or address.get('postcode')
    except Exception:
        pass
    return None

# Optimisation : traitement uniquement des coordonnées uniques
coords_uniques = action_17_octobre_localise[['lat', 'lon']].dropna().drop_duplicates()

dict_insee = {}
for _, row in coords_uniques.iterrows():
    dict_insee[(row['lat'], row['lon'])] = obtnir_code_insee(row['lat'], row['lon'])

# Application des codes INSEE dans le DataFrame initial
action_17_octobre_localise['code_insee'] = action_17_octobre_localise.apply(
    lambda r: dict_insee.get((r['lat'], r['lon'])), axis=1
 )

print(action_17_octobre_localise.head())

# enregistrer la base de données en parquet et dans le S3 
with fs.open(f"{DOSSIER}/action_17_octobre_geolocalise.parquet", "wb") as f:
    action_17_octobre_localise.to_parquet(f, index=False)
action_17_octobre_localise.to_parquet("data/manifs_17.parquet", index=False)