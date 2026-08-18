"""
Métriques de performance ajustées au risque.
"""

import pandas as pd
import numpy as np


def _cagr(equity: pd.Series) -> float:
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    if years <= 0 or equity.iloc[0] <= 0:
        return float("nan")
    return (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1


def _max_drawdown(equity: pd.Series) -> float:
    running_max = equity.cummax()
    drawdown = equity / running_max - 1
    return drawdown.min()


def _annualized_vol(returns: pd.Series) -> float:
    return returns.std() * np.sqrt(252)


def _sharpe(returns: pd.Series, risk_free_annual: float = 0.04) -> float:
    """Risk-free ~ taux T-bill court terme approximatif ; ajuste si besoin."""
    excess_daily = returns - risk_free_annual / 252
    if excess_daily.std() == 0:
        return float("nan")
    return excess_daily.mean() / excess_daily.std() * np.sqrt(252)


def _calmar(cagr: float, max_dd: float) -> float:
    if max_dd == 0:
        return float("nan")
    return cagr / abs(max_dd)


def compute_metrics(equity: pd.Series, label: str) -> dict:
    equity = equity.dropna()
    returns = equity.pct_change().dropna()

    cagr = _cagr(equity)
    max_dd = _max_drawdown(equity)
    vol = _annualized_vol(returns)
    sharpe = _sharpe(returns)
    calmar = _calmar(cagr, max_dd)

    return {
        "label": label,
        "CAGR": cagr,
        "Volatilité annualisée": vol,
        "Max Drawdown": max_dd,
        "Sharpe (rf=4%)": sharpe,
        "Calmar": calmar,
        "Valeur finale": equity.iloc[-1],
        "Valeur initiale": equity.iloc[0],
    }


def print_report(strategy_metrics: dict, benchmark_metrics: dict, extra: dict):
    def pct(x):
        return f"{x*100:6.2f}%" if pd.notna(x) else "  N/A "

    print("=" * 62)
    print(f"{'Métrique':<28}{'Stratégie':>16}{'Buy & Hold':>16}")
    print("-" * 62)
    rows = [
        ("CAGR", strategy_metrics["CAGR"], benchmark_metrics["CAGR"]),
        ("Volatilité annualisée", strategy_metrics["Volatilité annualisée"], benchmark_metrics["Volatilité annualisée"]),
        ("Max Drawdown", strategy_metrics["Max Drawdown"], benchmark_metrics["Max Drawdown"]),
        ("Sharpe (rf=4%)", strategy_metrics["Sharpe (rf=4%)"], benchmark_metrics["Sharpe (rf=4%)"]),
        ("Calmar", strategy_metrics["Calmar"], benchmark_metrics["Calmar"]),
    ]
    for name, s, b in rows:
        if name in ("Sharpe (rf=4%)", "Calmar"):
            print(f"{name:<28}{s:>16.2f}{b:>16.2f}")
        else:
            print(f"{name:<28}{pct(s):>16}{pct(b):>16}")

    print("-" * 62)
    print(f"{'Valeur finale ($)':<28}{strategy_metrics['Valeur finale']:>16,.0f}{benchmark_metrics['Valeur finale']:>16,.0f}")
    print("=" * 62)
    print(f"\nNombre de trades (stratégie)      : {extra['n_trades']}")
    print(f"Commissions totales payées        : {extra['total_commissions']:,.2f} $")
    print(f"Intérêts de marge totaux payés     : {extra['total_margin_interest']:,.2f} $")
    print(f"Dividendes reçus (stratégie)       : {extra['total_dividends_received']:,.2f} $")
    total_costs = extra['total_commissions'] + extra['total_margin_interest']
    print(f"Coûts totaux (comm. + intérêts)    : {total_costs:,.2f} $")
