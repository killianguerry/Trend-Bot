"""
Point d'entrée : lance le backtest complet et affiche le rapport.

Usage :
    python main.py
"""

import matplotlib.pyplot as plt

from config import BacktestConfig
from data_loader import load_price_data
from backtest import run_backtest
from metrics import compute_metrics, print_report


def main():
    cfg = BacktestConfig()

    print(f"Chargement des données {cfg.strategy.ticker}...")
    df = load_price_data(
        cfg.strategy.ticker,
        start=cfg.strategy.start_date,
        end=cfg.strategy.end_date,
    )
    print(f"{len(df)} jours de données chargés "
          f"({df.index.min().date()} -> {df.index.max().date()})\n")

    result = run_backtest(df, cfg)

    strat_metrics = compute_metrics(result.equity_curve, "Stratégie")
    bh_metrics = compute_metrics(result.benchmark_curve, "Buy & Hold")

    print_report(strat_metrics, bh_metrics, extra={
        "n_trades": result.n_trades,
        "total_commissions": result.total_commissions,
        "total_margin_interest": result.total_margin_interest,
        "total_dividends_received": result.total_dividends_received,
    })

    # --- Graphique ---
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True,
                                     gridspec_kw={"height_ratios": [3, 1]})

    ax1.plot(result.equity_curve.index, result.equity_curve.values,
              label=f"Stratégie (levier {cfg.strategy.target_leverage}x)", color="#1f77b4")
    ax1.plot(result.benchmark_curve.index, result.benchmark_curve.values,
              label="Buy & Hold QQQ", color="#888888", linestyle="--")
    ax1.set_yscale("log")
    ax1.set_ylabel("Valeur du portefeuille ($, échelle log)")
    ax1.legend()
    ax1.set_title(f"Trend-following SMA{cfg.strategy.sma_window} + levier vs Buy & Hold "
                   f"({cfg.strategy.ticker}, frais IBKR inclus)")
    ax1.grid(alpha=0.3)

    strat_dd = result.equity_curve / result.equity_curve.cummax() - 1
    bh_dd = result.benchmark_curve / result.benchmark_curve.cummax() - 1
    ax2.fill_between(strat_dd.index, strat_dd.values * 100, 0, color="#1f77b4", alpha=0.4, label="Stratégie")
    ax2.fill_between(bh_dd.index, bh_dd.values * 100, 0, color="#888888", alpha=0.3, label="Buy & Hold")
    ax2.set_ylabel("Drawdown (%)")
    ax2.legend()
    ax2.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig("backtest_result.png", dpi=150)
    print("\nGraphique sauvegardé : backtest_result.png")

    result.trades.to_csv("trades.csv", index=False)
    print(f"Journal des trades sauvegardé : trades.csv ({len(result.trades)} trades)")


if __name__ == "__main__":
    main()
