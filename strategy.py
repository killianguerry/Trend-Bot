"""
Génération du signal de tendance.
"""

import pandas as pd
from config import StrategyConfig


def sma_signal(df: pd.DataFrame, cfg: StrategyConfig) -> pd.Series:
    """
    Signal binaire (1 = long, 0 = flat) basé sur Close > SMA(window).

    Anti-lookahead : le signal calculé avec la clôture du jour t n'est
    exécutable qu'à l'ouverture du jour t+1 (voir backtest.py, qui décale
    le signal d'un jour avant de l'appliquer).

    band_pct : bande morte optionnelle pour réduire le nombre de faux
    signaux quand le prix oscille juste autour de la SMA.
    """
    sma = df["Close"].rolling(window=cfg.sma_window, min_periods=cfg.sma_window).mean()

    upper = sma * (1 + cfg.band_pct)
    lower = sma * (1 - cfg.band_pct)

    raw_signal = pd.Series(index=df.index, dtype=float)
    raw_signal[:] = float("nan")
    raw_signal[df["Close"] > upper] = 1.0
    raw_signal[df["Close"] < lower] = 0.0
    # Dans la bande morte : on garde le dernier état (pas de changement)
    signal = raw_signal.ffill().fillna(0.0)

    if cfg.confirm_days > 0:
        # Le signal ne change que si le nouvel état est confirmé N jours de suite
        confirmed = signal.copy()
        raw_state = (df["Close"] > sma).astype(float)
        stable_count = raw_state.groupby((raw_state != raw_state.shift()).cumsum()).cumcount() + 1
        confirmed = raw_state.where(stable_count >= cfg.confirm_days).ffill().fillna(0.0)
        signal = confirmed

    signal.name = "signal"
    return signal
