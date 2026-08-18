"""
Chargement des données de marché.

IMPORTANT : ce module utilise yfinance, qui nécessite un accès internet.
Il est fait pour tourner sur ta machine / Streamlit Cloud, pas dans un
environnement sandboxé sans réseau.
"""

import os
import pandas as pd
import yfinance as yf

CACHE_DIR = "data_cache"


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

    if not force_refresh and os.path.exists(path):
        cached = pd.read_parquet(path)
        cached.index = pd.to_datetime(cached.index)
        last_cached_date = cached.index.max()
        # Si le cache couvre déjà la période demandée, on le réutilise
        if end is None or pd.Timestamp(end) <= last_cached_date:
            df = cached
        else:
            df = _download(ticker, start, end)
    else:
        df = _download(ticker, start, end)

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
