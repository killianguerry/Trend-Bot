"""
Chargement des données de marché.

IMPORTANT : ce module utilise yfinance, qui nécessite un accès internet.
Il est fait pour tourner sur ta machine / Streamlit Cloud, pas dans un
environnement sandboxé sans réseau.

Stratégie de cache : on télécharge toujours l'historique COMPLET disponible
(depuis FULL_HISTORY_START) et on le stocke tel quel. Les appels avec un
`start` plus tardif filtrent simplement ce cache en mémoire. Ça évite le bug
classique du "cache partiel" où une première requête sur une période récente
pollue le cache pour toutes les requêtes suivantes sur une période plus
ancienne.
"""

import os
import pandas as pd
import yfinance as yf

CACHE_DIR = "data_cache"
FULL_HISTORY_START = "1993-01-01"  # bien avant l'inception de QQQ (1999), donc couvre tout


def _cache_path(ticker: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f"{ticker}.parquet")


def load_price_data(ticker: str, start: str, end: str = None, force_refresh: bool = False) -> pd.DataFrame:
    """
    Retourne un DataFrame journalier avec colonnes :
    Open, High, Low, Close, Volume, Dividends
    indexé par date (naive, sans timezone).

    Close est le prix NON ajusté des dividendes (on gère les dividendes
    nous-mêmes dans le simulateur de portefeuille, pour pouvoir appliquer
    les frais de courtage réels sur les vrais prix cotés).
    """
    path = _cache_path(ticker)
    need_download = force_refresh or not os.path.exists(path)

    df = None
    if not need_download:
        cached = pd.read_parquet(path)
        cached.index = pd.to_datetime(cached.index)

        cache_covers_start = cached.index.min() <= pd.Timestamp(start)
        # Si le cache a plus d'un jour et qu'on demande des données récentes
        # (end=None -> "jusqu'à aujourd'hui"), on le considère éventuellement
        # périmé mais on ne force pas le refresh à chaque appel : yfinance
        # sera de toute façon requêté au prochain redémarrage de l'app/cache
        # Streamlit. Pour forcer un refresh explicite, utiliser force_refresh=True.
        if cache_covers_start:
            df = cached

    if df is None:
        df = _download(ticker, FULL_HISTORY_START, None)

    df = df.loc[df.index >= pd.Timestamp(start)]
    if end:
        df = df.loc[df.index <= pd.Timestamp(end)]

    return df


def _download(ticker: str, start: str, end: str) -> pd.DataFrame:
    raw = yf.download(
        ticker,
        start=start,
        end=end,
        auto_adjust=False,   # on garde Close brut, on gère les div. nous-mêmes
        actions=True,        # récupère les dividendes/splits
        progress=False,
    )

    if raw.empty:
        raise ValueError(
            f"Aucune donnée reçue pour {ticker}. Vérifie ta connexion internet "
            f"ou le ticker."
        )

    # yfinance peut retourner des colonnes multi-index selon la version
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    df = raw[["Open", "High", "Low", "Close", "Volume"]].copy()
    df["Dividends"] = raw.get("Dividends", 0.0)
    df.index.name = "Date"
    df.index = pd.to_datetime(df.index).tz_localize(None)

    path = _cache_path(ticker)
    df.to_parquet(path)
    return df


if __name__ == "__main__":
    data = load_price_data("QQQ", "2000-01-01")
    print(data.tail())
    print(f"\n{len(data)} lignes chargées, de {data.index.min().date()} à {data.index.max().date()}")
    print(f"Total dividendes distribués sur la période : {data['Dividends'].sum():.2f} $ / action")
