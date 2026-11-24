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

URLS_CONTOURS = {
    "departement": "https://etalab-datasets.geo.data.gouv.fr/contours-administratifs/{year}/geojson/departements-1000m.geojson",
    "commune": "https://etalab-datasets.geo.data.gouv.fr/contours-administratifs/{year}/geojson/communes-1000m.geojson",
}

CODES_METRO = [f"{i:02d}" for i in range(1, 96) if i != 20] + ["2A", "2B"]

OUTRE_MER = {
    "971": ("Guadeloupe",               32620, 1.0,  (-120_000, 7_000_000)),
    "972": ("Martinique",               32620, 1.0,  (-120_000, 6_850_000)),
    "973": ("Guyane",                   2972,  0.35, (-120_000, 6_660_000)),
    "974": ("La Réunion",               2975,  1.0,  (-120_000, 6_480_000)),
    "976": ("Mayotte",                  4471,  1.0,  (-120_000, 6_340_000)),
    "975": ("Saint-Pierre-et-Miquelon", 4467,  1.0,  (200_000,   5_800_000)),
    "977": ("Saint-Barthélemy",         32620, 1.0,  (330_000,   5_800_000)),
    "978": ("Saint-Martin",             32620, 1.0,  (430_000,   5_800_000)),
    "986": ("Wallis-et-Futuna",         32701, 1.0,  (560_000,   5_800_000)),
    "987": ("Polynésie française",      3296,  0.12, (760_000,   5_800_000)),
    "988": ("Nouvelle-Calédonie",       3163,  0.5,  (1_000_000, 5_800_000)),
    "989": ("Clipperton",               32612, 1.0,  (1_120_000, 5_800_000)),
}

def _extraire_code_dep(serie_code: pd.Series) -> pd.Series:
    """Extrait le code département (2 ou 3 caractères) depuis un code département ou commune."""
    code = serie_code.astype("string").str.strip()
    dep = code.str[:2]
    est_outre_mer = (code.str.startswith("97") | code.str.startswith("98")).fillna(False)
    dep.loc[est_outre_mer] = code[est_outre_mer].str[:3]
    return dep

def _telecharger_contours(niveau: str, year: int, essais: int = 3) -> gpd.GeoDataFrame:
    """Télécharge le GeoJSON Etalab pour le niveau demandé ('departement' ou 'commune')."""
    if niveau not in URLS_CONTOURS:
        raise ValueError("Le niveau doit être 'departement' ou 'commune'.")
    url = URLS_CONTOURS[niveau].format(year=year)
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

def charger_contours(
    niveau: str = "departement", year: int = 2023, rapprocher_outre_mer: bool = True
) -> gpd.GeoDataFrame:
    """Contours des départements ou communes en Lambert 93 (EPSG:2154), source Etalab."""
    gdf = _telecharger_contours(niveau, year)
    gdf = gdf.rename(columns={"code": "CODE_GEO", "nom": "LIBELLE"})
    gdf = gdf[["CODE_GEO", "LIBELLE", "geometry"]].copy()
    gdf["geometry"] = gdf.geometry.make_valid()
    gdf["_DEP"] = _extraire_code_dep(gdf["CODE_GEO"])

    metro = gdf.loc[gdf["_DEP"].isin(CODES_METRO)].to_crs(2154).drop(columns=["_DEP"])
    if not rapprocher_outre_mer:
        return metro.reset_index(drop=True)

    morceaux = [metro]
    for code, (_, crs_local, echelle, (x, y)) in OUTRE_MER.items():
        d = gdf.loc[gdf["_DEP"] == code].to_crs(crs_local).drop(columns=["_DEP"])
        if d.empty:
            continue

        minx, miny, maxx, maxy = d.total_bounds
        cx, cy = (minx + maxx) / 2, (miny + maxy) / 2

        geom = d.geometry.scale(xfact=echelle, yfact=echelle, origin=(cx, cy))
        geom = geom.translate(xoff=x - cx, yoff=y - cy)

        d = d.copy()
        d["geometry"] = geom
        d = d.set_crs(2154, allow_override=True)
        morceaux.append(d)

    return gpd.GeoDataFrame(pd.concat(morceaux, ignore_index=True), crs=2154)

def _construire_fond_departements(carte_communes: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Dissout les polygones communaux par département pour obtenir leurs bordures exactes."""
    fond = carte_communes[["CODE_GEO", "geometry"]].copy()
    fond["INSEE_DEP"] = _extraire_code_dep(fond["CODE_GEO"])
    # buffer(0) nettoie d'éventuelles micro-fissures topologiques entre communes
    fond["geometry"] = fond.geometry.buffer(0)
    return fond.dissolve(by="INSEE_DEP", as_index=False)[["INSEE_DEP", "geometry"]]

def compter_actions(
    df: pd.DataFrame,
    niveau: str = "departement",
    lon_col: str = "lon",
    lat_col: str = "lat",
    year: int = 2023,
) -> pd.DataFrame:
    """Compte le nombre d'évènements par département ou par commune."""
    if "code_insee" not in df.columns:
        df = ajouter_code_insee(df, lon_col=lon_col, lat_col=lat_col, year=year)
    else:
        df = df.copy()

    code_commune = df["code_insee"].astype("string").str.zfill(5)
    
    if niveau == "departement":
        df["CODE_GEO"] = _extraire_code_dep(code_commune)
    elif niveau == "commune":
        df["CODE_GEO"] = code_commune
    else:
        raise ValueError("Le niveau doit être 'departement' ou 'commune'.")

    return (
        df.dropna(subset=["CODE_GEO"])
        .groupby("CODE_GEO")
        .size()
        .rename("nb_actions")
        .reset_index()
    )

def preparer_table(
    scraped: pd.DataFrame,
    niveau: str = "departement",
    contours: gpd.GeoDataFrame | None = None,
    lon_col: str = "lon",
    lat_col: str = "lat",
    year_communes: int = 2023,
) -> gpd.GeoDataFrame:
    """Contours (Lambert 93) + colonne 'nb_actions' (0 si aucune action)."""
    if contours is None:
        contours = charger_contours(niveau=niveau, year=year_communes)

    counts = compter_actions(
        scraped, niveau=niveau, lon_col=lon_col, lat_col=lat_col, year=year_communes
    )
    carte = contours.merge(counts, on="CODE_GEO", how="left")
    carte["nb_actions"] = carte["nb_actions"].fillna(0).astype(int)
    carte = carte[["LIBELLE", "CODE_GEO", "nb_actions", "geometry"]]
    return gpd.GeoDataFrame(carte, geometry="geometry", crs=contours.crs)


# Fonctions qui permettent de dessiner les cartes 

def carte_choroplethe_statique(
    scraped: pd.DataFrame,
    niveau: str = "departement",
    contours: gpd.GeoDataFrame | None = None,
    echelle: str = "lineaire",
    couleurs: tuple = ("white", "red"),
    etiquettes: bool = True,
    uniquement_actifs: bool = False,
    figsize: tuple = (9, 9),
    **kwargs,
):
    """Carte matplotlib (Lambert 93) à l'échelle départementale ou communale.
    
    Args:
        uniquement_actifs (bool): si True, n'affiche les polygones que pour nb_actions > 0,
            tout en conservant les bordures des départements en arrière-plan.
    """
    carte = preparer_table(scraped, niveau=niveau, contours=contours, **kwargs)
    
    # On prépare le fond départemental avant un éventuel filtrage des communes à 0
    fond_dep = _construire_fond_departements(carte) if niveau == "commune" else None

    if echelle == "log":
        carte["valeur"] = np.log1p(carte["nb_actions"])
        legende = "Nombre d'actions (échelle log : log(1+n))"
    else:
        carte["valeur"] = carte["nb_actions"]
        legende = "Nombre d'actions"

    vmin = 0
    vmax = max(float(carte["valeur"].max()), 1e-9)

    if uniquement_actifs:
        carte_affichee = carte.loc[carte["nb_actions"] > 0].copy()
    else:
        carte_affichee = carte

    epaisseur_bordure = 0.05 if niveau == "commune" else 0.4
    couleur_bordure = "grey" if niveau == "commune" else "black"

    cmap = LinearSegmentedColormap.from_list("degrade", list(couleurs))
    ax = carte_affichee.plot(
        column="valeur",
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        edgecolor=couleur_bordure,
        linewidth=epaisseur_bordure,
        legend=True,
        legend_kwds={"label": legende, "shrink": 0.6},
        figsize=figsize,
    )

    # Superposition des bordures départementales au niveau communal
    if fond_dep is not None:
        fond_dep.boundary.plot(ax=ax, color="black", linewidth=0.4)

    if etiquettes:
        deps = _extraire_code_dep(carte["CODE_GEO"])
        for code, (nom, *_) in OUTRE_MER.items():
            d = carte.loc[deps == code]
            if d.empty:
                continue
            minx, miny, maxx, maxy = d.total_bounds
            ax.text(
                (minx + maxx) / 2,
                miny - 15_000,
                nom,
                fontsize=5,
                ha="center",
                va="top",
            )

    ax.set_axis_off()
    return ax


def carte_choroplethe_interactive(
    scraped: pd.DataFrame,
    niveau: str = "departement",
    contours: gpd.GeoDataFrame | None = None,
    echelle: str = "lineaire",
    vmax: float | None = None,
    couleurs: tuple = ("white", "red"),
    uniquement_actifs: bool = False,
    **kwargs,
) -> folium.Map:
    """Carte réactive Folium à l'échelle départementale ou communale.
    
    Args:
        uniquement_actifs (bool): si True, n'affiche que les polygones ayant nb_actions > 0
            (allège fortement la carte Folium au niveau communal) avec les contours départementaux.
    """
    carte_l93 = preparer_table(scraped, niveau=niveau, contours=contours, **kwargs)
    
    # Cadrage et fond départemental calculés sur l'ensemble du territoire
    fond_dep = (
        _construire_fond_departements(carte_l93).to_crs(4326)
        if niveau == "commune"
        else None
    )
    carte = carte_l93.to_crs(4326)
    minx, miny, maxx, maxy = carte.total_bounds

    transfo = np.log1p if echelle == "log" else (lambda x: x)
    vmax = carte["nb_actions"].max() if vmax is None else vmax
    legende = "Nombre d'actions" + (" (échelle log : log(1+n))" if echelle == "log" else "")

    cmap = LinearColormap(
        list(couleurs), vmin=0, vmax=max(float(transfo(vmax)), 1e-9), caption=legende
    )

    if uniquement_actifs:
        carte_affichee = carte.loc[carte["nb_actions"] > 0].copy()
    else:
        carte_affichee = carte

    m = folium.Map(location=[(miny + maxy) / 2, (minx + maxx) / 2], zoom_start=5, tiles=None)

    # Couche de fond : bordures des départements (non interactive pour laisser le survol aux communes)
    if fond_dep is not None:
        folium.GeoJson(
            fond_dep,
            style_function=lambda _: {
                "fillColor": "white",
                "color": "black",
                "weight": 1.0,
                "fillOpacity": 0.1,
            },
            interactive=False,
        ).add_to(m)

    # Couche principale : communes ou départements
    label_entite = "Commune :" if niveau == "commune" else "Département :"
    label_code = "Code INSEE :" if niveau == "commune" else "Numéro :"
    epaisseur = 0.2 if niveau == "commune" else 1.0

    folium.GeoJson(
        carte_affichee,
        style_function=lambda f: {
            "fillColor": cmap(float(transfo(min(f["properties"]["nb_actions"], vmax)))),
            "color": "black",
            "weight": epaisseur,
            "fillOpacity": 0.9,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["LIBELLE", "CODE_GEO", "nb_actions"],
            aliases=[label_entite, label_code, "Nombre d'actions :"],
        ),
    ).add_to(m)

    m.fit_bounds([[miny, minx], [maxy, maxx]])
    cmap.add_to(m)
    return m


# ces fonctions permettent de faire la carte pondérée par la population

def preparer_table_ponderee(
    just17_pop: pd.DataFrame,
    col_pop: str = "PMUN",
    pour: int = 10_000,
    pop_min: int = 0,
    contours: gpd.GeoDataFrame | None = None,
    year_communes: int = 2023,
) -> gpd.GeoDataFrame:
    """Contours communaux + nb_actions + population + taux pour `pour` habitants.

    just17_pop : une ligne par évènement, avec 'code_insee' et la population
    de la commune (issue du merge avec pop_commune).
    """
    # nb_actions par commune (compter_actions réutilise la colonne code_insee)
    carte = preparer_table(
        just17_pop, niveau="commune", contours=contours, year_communes=year_communes
    )

    # population : une valeur par commune, prise dans just17_pop
    pop = just17_pop[["code_insee", col_pop]].copy()
    pop["CODE_GEO"] = (
        pop["code_insee"].astype("string").str.strip()
        .str.replace(r"\.0$", "", regex=True).str.zfill(5)
    )
    pop["population"] = pd.to_numeric(pop[col_pop], errors="coerce")
    pop = pop.dropna(subset=["CODE_GEO"]).groupby("CODE_GEO", as_index=False)["population"].first()

    carte = carte.merge(pop, on="CODE_GEO", how="left", validate="one_to_one")

    # taux : 0 si aucune action, NaN si population inconnue ou sous le seuil
    taux = carte["nb_actions"] / carte["population"] * pour
    taux = taux.where(carte["population"] > pop_min)
    carte["taux"] = np.where(carte["nb_actions"] == 0, 0.0, taux)
    return carte

def carte_statique_ponderee(
    just17_pop: pd.DataFrame,
    col_pop: str = "PMUN",
    pour: int = 10_000,
    pop_min: int = 0,
    quantile_max: float | None = 0.99,
    couleurs: tuple = ("white", "red"),
    etiquettes: bool = True,
    figsize: tuple = (9, 9),
    contours: gpd.GeoDataFrame | None = None,
    year_communes: int = 2023,
):
    """Carte matplotlib communale : actions pour `pour` habitants, depuis just17_pop."""
    carte = preparer_table_ponderee(
        just17_pop, col_pop="PMUN", pour=pour, pop_min=pop_min,
        contours=contours, year_communes=year_communes,
    )
    fond_dep = _construire_fond_departements(carte)

    legende = f"Actions pour {pour:,} habitants".replace(",", " ")

    vmax = (
        float(carte["taux"].quantile(quantile_max))
        if quantile_max is not None else float(carte["taux"].max())
    )
    vmax = max(vmax, 1e-9)

    cmap = LinearSegmentedColormap.from_list("degrade", list(couleurs))
    ax = carte.plot(
        column="taux",
        cmap=cmap,
        vmin=0,
        vmax=vmax,
        edgecolor="grey",
        linewidth=0.05,
        legend=True,
        legend_kwds={"label": legende, "shrink": 0.6,
                     "extend": "max" if quantile_max else "neither"},
        missing_kwds={"color": "lightgrey"},
        figsize=figsize,
    )
    fond_dep.boundary.plot(ax=ax, color="black", linewidth=0.4)

    if etiquettes:
        deps = _extraire_code_dep(carte["CODE_GEO"])
        for code, (nom, *_) in OUTRE_MER.items():
            d = carte.loc[deps == code]
            if d.empty:
                continue
            minx, miny, maxx, maxy = d.total_bounds
            ax.text((minx + maxx) / 2, miny - 15_000, nom, fontsize=5, ha="center", va="top")

    ax.set_axis_off()
    return ax