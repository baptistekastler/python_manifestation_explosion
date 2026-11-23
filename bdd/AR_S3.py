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

# pour enregistrer un fichier dans le s3
# fs.put("/home/onyxia/work/python_manifestation_explosion/bdd/just17.csv", f"{DOSSIER}/just17.csv")

# ceci permet de récupérer un fichier qui se trouve dans le s3
# fs.get(
#    f"{DOSSIER}/just17.csv",
#    "/home/onyxia/work/python_manifestation_explosion/bdd/just17.csv",
# )
# ¨Pour ouvrir un fichier qui est dans le s3
# with fs.open(f"{DOSSIER}/actions.csv", mode="rb") as f:
#    actions_17_octobre = pd.read_csv(f)


# pour enregistrer un fichier dans le s3
# with fs.open(f"{DOSSIER}/action_17_octobre_geolocalise.parquet", "wb") as f:
#    action_17_octobre_localise.to_parquet(f, index=False)