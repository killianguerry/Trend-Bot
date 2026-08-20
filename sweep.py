"""
Balayage systématique de paramètres, sur plusieurs périodes.

Objectif : éviter de choisir un réglage "à l'œil" sur un seul résultat
(surajustement). On teste une grille de (sma_window, leverage) sur deux
fenêtres temporelles différentes et on ne retient que les combinaisons
qui restent bonnes sur les deux — pas juste sur une.

Usage :
    python sweep.py
"""

import itertools
import pandas as pd

from config import BacktestConfig, StrategyConfig, IBCosts
from data_loader import load_price_data
from backtest import run_backtest
from metrics import compute_metrics

TICKER = "QQQ"

# Grille testée — élargis/réduis si besoin
SMA_WINDOWS = [100, 150, 200, 250, 300, 350]
LEVERAGES = [1.15, 1.25, 1.35, 1.5]

# Deux périodes : la période complète (avec bulle 2000) et une période
# "hors bulle" pour vérifier que le réglage n'est pas juste un coup de
# chance sur l'épisode 2000-2002.
PERIODS = {
    "2000_to_now": "2000-01-01",
    "2003_to_now": "2003-01-01",
}


def run_one(df_by_start, sma_window, leverage, start_key):
    df = df_by_start[start_key]
    strat_cfg = StrategyConfig(
        ticker=TICKER,
        sma_window=sma_window,
        target_leverage=leverage,
        start_date=PERIODS[start_key],
    )
    cfg = BacktestConfig(strategy=strat_cfg, costs=IBCosts())

    if len(df) < sma_window + 10:
        return None

    result = run_backtest(df, cfg)
    strat_m = compute_metrics(result.equity_curve, "Stratégie")
    bh_m = compute_metrics(result.benchmark_curve, "Buy & Hold")

    return {
        "period": start_key,
        "sma_window": sma_window,
        "leverage": leverage,
        "CAGR": strat_m["CAGR"],
        "CAGR_BH": bh_m["CAGR"],
        "CAGR_edge": strat_m["CAGR"] - bh_m["CAGR"],
        "MaxDD": strat_m["Max Drawdown"],
        "MaxDD_BH": bh_m["Max Drawdown"],
        "Sharpe": strat_m["Sharpe (rf=4%)"],
        "Sharpe_BH": bh_m["Sharpe (rf=4%)"],
        "Sharpe_edge": strat_m["Sharpe (rf=4%)"] - bh_m["Sharpe (rf=4%)"],
        "Calmar": strat_m["Calmar"],
        "Calmar_BH": bh_m["Calmar"],
        "n_trades": result.n_trades,
    }


def main():
    print(f"Chargement des données {TICKER} (une seule fois, la plus longue période)...")
    df_full = load_price_data(TICKER, start="2000-01-01")

    df_by_start = {
        "2000_to_now": df_full,
        "2003_to_now": df_full.loc[df_full.index >= "2003-01-01"],
    }

    rows = []
    combos = list(itertools.product(SMA_WINDOWS, LEVERAGES, PERIODS.keys()))
    print(f"Test de {len(combos)} combinaisons...")

    for sma_window, leverage, period_key in combos:
        r = run_one(df_by_start, sma_window, leverage, period_key)
        if r is not None:
            rows.append(r)

    results = pd.DataFrame(rows)
    results.to_csv("sweep_results.csv", index=False)
    print(f"\nRésultats complets sauvegardés dans sweep_results.csv ({len(results)} lignes)\n")

    # --- Vue pivot : Sharpe edge (stratégie - buy&hold) par combo x période ---
    pivot_sharpe = results.pivot_table(
        index=["sma_window", "leverage"], columns="period", values="Sharpe_edge"
    )
    pivot_cagr = results.pivot_table(
        index=["sma_window", "leverage"], columns="period", values="CAGR_edge"
    )

    # Robustesse : combinaisons qui battent le buy&hold en Sharpe SUR LES DEUX PÉRIODES
    robust = pivot_sharpe.dropna()
    robust = robust[(robust["2000_to_now"] > 0) & (robust["2003_to_now"] > 0)]

    print("=" * 70)
    print("Écart de Sharpe (stratégie - buy&hold), par combinaison et période")
    print("=" * 70)
    print(pivot_sharpe.round(3))

    print("\n" + "=" * 70)
    print("Écart de CAGR en points (stratégie - buy&hold), par combinaison et période")
    print("=" * 70)
    print((pivot_cagr * 100).round(2))

    print("\n" + "=" * 70)
    if len(robust) > 0:
        print(f"Combinaisons robustes (Sharpe > buy&hold SUR LES 2 PÉRIODES) : {len(robust)}")
        print("=" * 70)
        print(robust.round(3))
    else:
        print("Aucune combinaison ne bat le buy&hold en Sharpe sur les 2 périodes à la fois.")
        print("=> Le signal SMA seul n'apporte probablement pas d'edge en rendement ajusté")
        print("   au risque en dehors des crashs extrêmes type 2000-2002. Il faudra soit")
        print("   changer de signal, soit accepter l'objectif 'réduction de drawdown' plutôt")
        print("   que 'battre le marché'.")
    print("=" * 70)


if __name__ == "__main__":
    main()
