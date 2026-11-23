# Fonctions pour faire des cartes choroplèthes du nombre d'actions par département,
# DROM et COM placés autour de la France métropolitaine.
import io
import time

import numpy as np
import pandas as pd
import geopandas as gpd
import requests
import folium
from branca.colormap import LinearColormap
from matplotlib.colors import LinearSegmentedColormap

from useful_db import ajouter_code_insee


URL_DEPARTEMENTS = (
    "https://etalab-datasets.geo.data.gouv.fr/contours-administratifs/"
    "{year}/geojson/departements-1000m.geojson"
)

# Métropole : 01 à 95 sans 20, plus 2A et 2B
CODES_METRO = [f"{i:02d}" for i in range(1, 96) if i != 20] + ["2A", "2B"]

# Outre-mer : code -> (nom, CRS local, facteur d'échelle, (x, y) du centre en Lambert 93)
# Métropole : x ≈ 100 000 à 1 300 000, y ≈ 6 040 000 à 7 100 000.
# DROM : colonne à gauche de la métropole (x = -120 000)
# COM  : rangée sous la métropole (y = 5 800 000)
OUTRE_MER = {
    # --- DROM (colonne de gauche) ---
    "971": ("Guadeloupe",               32620, 1.0,  (-120_000, 7_000_000)),
    "972": ("Martinique",               32620, 1.0,  (-120_000, 6_850_000)),
    "973": ("Guyane",                   2972,  0.35, (-120_000, 6_660_000)),
    "974": ("La Réunion",               2975,  1.0,  (-120_000, 6_480_000)),
    "976": ("Mayotte",                  4471,  1.0,  (-120_000, 6_340_000)),
    # --- COM (rangée du bas) ---
    "975": ("Saint-Pierre-et-Miquelon", 4467,  1.0,  (200_000,   5_800_000)),
    "977": ("Saint-Barthélemy",         32620, 1.0,  (330_000,   5_800_000)),
    "978": ("Saint-Martin",             32620, 1.0,  (430_000,   5_800_000)),
    "986": ("Wallis-et-Futuna",         32701, 1.0,  (560_000,   5_800_000)),
    "987": ("Polynésie française",      3296,  0.12, (760_000,   5_800_000)),
    "988": ("Nouvelle-Calédonie",       3163,  0.5,  (1_000_000, 5_800_000)),
    "989": ("Clipperton",               32612, 1.0,  (1_120_000, 5_800_000)),
}


# fonctions qui permettent de télécharger les contours
def _telecharger_departements(year: int, essais: int = 3) -> gpd.GeoDataFrame:
    """Télécharge le GeoJSON Etalab en entier avant de le lire (avec nouvelles tentatives)."""
    url = URL_DEPARTEMENTS.format(year=year)
    derniere_erreur = None
    for i in range(essais):
        try:
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            return gpd.read_file(io.BytesIO(r.content))
        except Exception as e:
            derniere_erreur = e
            print(f"Essai {i + 1}/{essais} échoué : {type(e).__name__}")
            time.sleep(2)
    raise RuntimeError(f"Téléchargement impossible : {derniere_erreur}")


def charger_departements(year: int = 2023, rapprocher_outre_mer: bool = True) -> gpd.GeoDataFrame:
    """Contours des départements en Lambert 93 (EPSG:2154), source Etalab.

    Args:
        year (int): millésime des contours.
        rapprocher_outre_mer (bool): si True, DROM et COM sont projetés dans leur CRS
            local, éventuellement réduits, puis placés autour de la métropole
            selon le dictionnaire OUTRE_MER. Si False, seule la métropole est renvoyée.

    Returns:
        gpd.GeoDataFrame: colonnes INSEE_DEP, LIBELLE_DEPARTEMENT, geometry
    """
    dep = _telecharger_departements(year)
    dep = dep.rename(columns={"code": "INSEE_DEP", "nom": "LIBELLE_DEPARTEMENT"})
    dep = dep[["INSEE_DEP", "LIBELLE_DEPARTEMENT", "geometry"]].copy()
    dep["geometry"] = dep.geometry.make_valid()

    metro = dep.loc[dep["INSEE_DEP"].isin(CODES_METRO)].to_crs(2154)
    if not rapprocher_outre_mer:
        return metro.reset_index(drop=True)

    morceaux = [metro]
    for code, (_, crs_local, echelle, (x, y)) in OUTRE_MER.items():
        d = dep.loc[dep["INSEE_DEP"] == code].to_crs(crs_local)
        if d.empty:  # territoire absent du fichier : on l'ignore
            continue

        # centre de l'emprise dans le CRS local (en mètres)
        minx, miny, maxx, maxy = d.total_bounds
        cx, cy = (minx + maxx) / 2, (miny + maxy) / 2

        # réduction autour du centre, puis déplacement vers la position voulue
        geom = d.geometry.scale(xfact=echelle, yfact=echelle, origin=(cx, cy))
        geom = geom.translate(xoff=x - cx, yoff=y - cy)

        d = d.copy()
        d["geometry"] = geom
        # les coordonnées sont désormais celles du cadre Lambert 93 voulu
        d = d.set_crs(2154, allow_override=True)
        morceaux.append(d)

    return gpd.GeoDataFrame(pd.concat(morceaux, ignore_index=True), crs=2154)


# Cette fonction permet de compter le nombre d'actions par département 
def compter_actions_par_departement(
    df: pd.DataFrame,
    lon_col: str = "lon",
    lat_col: str = "lat",
    year: int = 2023,
) -> pd.DataFrame:
    """Compte le nombre d'évènements (tous types confondus) par département.

    Si la colonne 'code_insee' existe déjà dans df, elle est réutilisée
    (évite de retélécharger le fichier des communes).

    Returns:
        pd.DataFrame: colonnes 'INSEE_DEP' et 'nb_actions'
    """
    if "code_insee" not in df.columns:
        df = ajouter_code_insee(df, lon_col=lon_col, lat_col=lat_col, year=year)
    else:
        df = df.copy()

    code = df["code_insee"].astype("string").str.zfill(5)
    # métropole : 2 premiers caractères (dont "2A"/"2B"), outre-mer (97x, 98x) : 3
    df["INSEE_DEP"] = code.str[:2]
    est_outre_mer = (code.str.startswith("97") | code.str.startswith("98")).fillna(False)
    df.loc[est_outre_mer, "INSEE_DEP"] = code[est_outre_mer].str[:3]

    return (
        df.dropna(subset=["INSEE_DEP"])
        .groupby("INSEE_DEP")
        .size()
        .rename("nb_actions")
        .reset_index()
    )


def preparer_table_departements(
    scraped: pd.DataFrame,
    departements: gpd.GeoDataFrame | None = None,
    lon_col: str = "lon",
    lat_col: str = "lat",
    year_communes: int = 2023,
) -> gpd.GeoDataFrame:
    """Contours (Lambert 93, outre-mer rapproché) + colonne 'nb_actions' (0 si aucune action)."""
    if departements is None:
        departements = charger_departements()

    counts = compter_actions_par_departement(
        scraped, lon_col=lon_col, lat_col=lat_col, year=year_communes
    )
    carte = departements.merge(counts, on="INSEE_DEP", how="left")
    carte["nb_actions"] = carte["nb_actions"].fillna(0).astype(int)
    carte = carte[["LIBELLE_DEPARTEMENT", "INSEE_DEP", "nb_actions", "geometry"]]
    return gpd.GeoDataFrame(carte, geometry="geometry", crs=departements.crs)


# fonctions qui permettent de fabriquer les cartes 
def carte_choroplethe_statique(
    scraped: pd.DataFrame,
    departements: gpd.GeoDataFrame | None = None,
    echelle: str = "lineaire",
    couleurs: tuple = ("white", "red"),
    etiquettes: bool = True,
    figsize: tuple = (9, 9),
    **kwargs,
):
    """Carte matplotlib (Lambert 93), DROM à gauche et COM en dessous de la métropole.

    Args:
        echelle (str): "lineaire" ou "log" (couleur selon log(1 + n)).
        etiquettes (bool): affiche le nom de chaque territoire d'outre-mer.
    """
    carte = preparer_table_departements(scraped, departements, **kwargs)

    if echelle == "log":
        carte["valeur"] = np.log1p(carte["nb_actions"])
        legende = "Nombre d'actions (échelle log : log(1+n))"
    else:
        carte["valeur"] = carte["nb_actions"]
        legende = "Nombre d'actions"

    cmap = LinearSegmentedColormap.from_list("degrade", list(couleurs))
    ax = carte.plot(
        column="valeur",
        cmap=cmap,
        edgecolor="black",
        linewidth=0.4,
        legend=True,
        legend_kwds={"label": legende, "shrink": 0.6},
        figsize=figsize,
    )

    if etiquettes:
        for code, (nom, *_ ) in OUTRE_MER.items():
            d = carte.loc[carte["INSEE_DEP"] == code]
            if d.empty:
                continue
            minx, miny, maxx, maxy = d.total_bounds
            ax.text((minx + maxx) / 2, miny - 15_000, nom,
                    fontsize=5, ha="center", va="top")

    ax.set_axis_off()
    return ax


def carte_choroplethe_departements(
    scraped: pd.DataFrame,
    departements: gpd.GeoDataFrame | None = None,
    echelle: str = "lineaire",
    vmax: float | None = None,
    couleurs: tuple = ("white", "red"),
    **kwargs,
) -> folium.Map:
    """Carte réactive : départements colorés du blanc au rouge selon le nombre d'actions.

    L'outre-mer étant déplacé, il n'y a pas de fond de carte (tiles=None).

    Args:
        scraped (pd.DataFrame): évènements, avec colonnes lon/lat (ou code_insee)
        departements (gpd.GeoDataFrame, optional): contours (voir charger_departements).
        echelle (str): "lineaire" ou "log"
        vmax (float, optional): valeur correspondant au rouge max (par défaut le maximum observé)
        couleurs (tuple): couleur de départ et d'arrivée
        **kwargs: passés à preparer_table_departements (lon_col, lat_col, year_communes)
    """
    carte = preparer_table_departements(scraped, departements, **kwargs).to_crs(4326)

    transfo = np.log1p if echelle == "log" else (lambda x: x)
    vmax = carte["nb_actions"].max() if vmax is None else vmax
    legende = "Nombre d'actions" + (" (échelle log : log(1+n))" if echelle == "log" else "")

    cmap = LinearColormap(
        list(couleurs), vmin=0, vmax=max(float(transfo(vmax)), 1e-9), caption=legende
    )

    minx, miny, maxx, maxy = carte.total_bounds
    m = folium.Map(location=[(miny + maxy) / 2, (minx + maxx) / 2], zoom_start=5, tiles=None)

    folium.GeoJson(
        carte,
        style_function=lambda f: {
            "fillColor": cmap(float(transfo(min(f["properties"]["nb_actions"], vmax)))),
            "color": "black",
            "weight": 1,
            "fillOpacity": 0.9,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["LIBELLE_DEPARTEMENT", "INSEE_DEP", "nb_actions"],
            aliases=["Département :", "Numéro :", "Nombre d'actions :"],
        ),
    ).add_to(m)

    m.fit_bounds([[miny, minx], [maxy, maxx]])
    cmap.add_to(m)
    return m