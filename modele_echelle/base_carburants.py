import csv
import xml.etree.ElementTree as ET
import importlib.util
import os

# pour pouvoir utiliser AR_S3 en tant que module alors qu'on est dans un autre dossier
spec = importlib.util.spec_from_file_location(
    "AR_S3", "bdd/AR_S3.py"
)
ar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ar)

#ar.envoyer_vers_s3("PrixCarburants_annuel_2026.xml", "base_carburants_2026.xml")

#ar.recuperer_depuis_s3("base_carburants_2026.xml", "bdd/base_carburants_2026.xml")

# FICHIER = "bdd/base_carburants_2026.xml"
# JOUR = "2026-10-17"
# FIN_JOUR = JOUR + "T23:59:59"  # les dates ISO se comparent comme du texte

# with open("bdd/prix_2026-10-17.csv", "w", newline="", encoding="utf-8") as out:
#     w = csv.writer(out)
#     w.writerow(["id", "cp", "ville", "carburant", "prix", "maj", "maj_le_jour"])

#     for _, pdv in ET.iterparse(FICHIER, events=("end",)):
#         if pdv.tag != "pdv":
#             continue

#         # dernière mise à jour <= 17/10 23:59:59, par carburant
#         dernier = {}
#         for p in pdv.findall("prix"):
#             maj = p.get("maj")
#             if maj and maj <= FIN_JOUR:
#                 nom = p.get("nom")
#                 if nom not in dernier or maj >= dernier[nom][0]:
#                     dernier[nom] = (maj, p.get("valeur"))

#         ville = (pdv.findtext("ville") or "").strip()
#         for nom, (maj, val) in dernier.items():
#             w.writerow(
#                 [
#                     pdv.get("id"),
#                     pdv.get("cp"),
#                     ville,
#                     nom,
#                     float(val),
#                     maj,
#                     maj.startswith(JOUR),
#                 ]
#             )

#         pdv.clear()  # libère la mémoire

# os.remove("bdd/base_carburants_2026.xml")

def jointure_prix_toutes_communes(df_communes,df_prix):
    