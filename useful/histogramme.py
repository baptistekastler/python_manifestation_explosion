import pandas as pd
import matplotlib.pyplot as plt

def plot_genre_par_type_commune(
    df: pd.DataFrame,
    col_genre: str = "title",
    col_pop: str = "PMUN",
    bins: list = [0, 2000, 10000, 50000, 100000, float("inf")],
    labels: list = ["Rurale (< 2 000)", "Petite (2k - 10k)", "Moyenne (10k - 50k)", "Grande (50k - 100k)", "Très grande (> 100 000)"],
    normalize: str = "index",
    figsize: tuple = (12, 6),
    titre: str = "Répartition des types de communes par type de manifestation (%)",
):
    """Trace un diagramme en barres des types de manifestations selon la taille de la commune."""
    data = df.copy()
    data[col_pop] = pd.to_numeric(data[col_pop], errors="coerce")

    data["type_commune"] = pd.cut(data[col_pop], bins=bins, labels=labels)

    table_pct = pd.crosstab(data[col_genre], data["type_commune"], normalize=normalize) * 100

    ax = table_pct.plot(kind="bar", figsize=figsize, width=0.8)
    ax.set_title(titre)
    ax.set_xlabel("Type de manifestation")
    ax.set_ylabel("Pourcentage (%)")
    plt.xticks(rotation=25, ha="right")
    plt.legend(title="Type de commune", bbox_to_anchor=(1.02, 1), loc="upper left")
    plt.tight_layout()
    return ax