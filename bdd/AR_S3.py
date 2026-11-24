import os
import s3fs
from dotenv import load_dotenv

# Charge les variables du fichier .env dans os.environ (si le fichier existe)
load_dotenv(override=True)
DEFAULT_DOSSIER = "spktaqlr/diffusion"


def get_fs() -> s3fs.S3FileSystem:
    """Initialise et retourne la connexion au stockage S3 du SSP Cloud."""
    s3fs.S3FileSystem.clear_instance_cache()
    endpoint = os.environ.get("AWS_S3_ENDPOINT", "minio.lab.sspcloud.fr")
    return s3fs.S3FileSystem(
        client_kwargs={"endpoint_url": f"https://{endpoint}"}
    )


def envoyer_vers_s3(
    chemin_local: str,
    nom_distant: str | None = None,
    dossier_s3: str = DEFAULT_DOSSIER,
) -> str:
    """Envoie un fichier ou dossier local (Onyxia) vers le S3."""
    fs = get_fs()
    if nom_distant is None:
        nom_distant = os.path.basename(chemin_local)
    chemin_cible = f"{dossier_s3}/{nom_distant}"
    fs.put(chemin_local, chemin_cible, recursive=os.path.isdir(chemin_local))
    return chemin_cible


def recuperer_depuis_s3(
    nom_distant: str,
    chemin_local: str,
    dossier_s3: str = DEFAULT_DOSSIER,
) -> str:
    """Télécharge un fichier depuis le S3 vers l'espace de travail local (Onyxia)."""
    fs = get_fs()
    chemin_source = f"{dossier_s3}/{nom_distant}"
    fs.get(chemin_source, chemin_local)
    return chemin_local