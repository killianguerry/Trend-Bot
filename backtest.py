"""
Moteur de simulation de portefeuille.

Deux portefeuilles sont simulés en parallèle sur les mêmes données :
1. "strategy"  : trend-following (SMA) avec levier, marge et frais IB réels
2. "buy_hold"  : achat unique au départ, dividendes réinvestis, frais IB réels
                 (sans levier, benchmark de référence)
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass

from config import BacktestConfig
from strategy import sma_signal
from costs import commission, daily_margin_interest


@dataclass
class BacktestResult:
    equity_curve: pd.Series
    benchmark_curve: pd.Series
    trades: pd.DataFrame
    total_commissions: float
    total_margin_interest: float
    total_dividends_received: float
    n_trades: int


def run_backtest(df: pd.DataFrame, cfg: BacktestConfig) -> BacktestResult:
    strat_cfg = cfg.strategy
    costs = cfg.costs

    df = df.copy()
    signal = sma_signal(df, strat_cfg)
    # Anti-lookahead : le signal du jour t (calculé à la clôture) ne peut être
    # exécuté qu'à la clôture du jour t+1 (on simplifie en tradant "au close"
    # du jour suivant plutôt qu'à l'open, ce qui est conservateur sur les frais
    # mais légèrement optimiste sur le slippage — non modélisé ici).
    executable_signal = signal.shift(1).fillna(0.0)

    df = df.loc[df.index >= df.index[strat_cfg.sma_window]]  # tronque le warm-up SMA
    executable_signal = executable_signal.loc[df.index]

    # --- Simulation stratégie (levier) ---
    strat_equity, strat_trades, strat_stats = _simulate(
        df, executable_signal, strat_cfg, costs, leveraged=True
    )

    # --- Simulation buy & hold (référence, sans levier) ---
    bh_signal = pd.Series(1.0, index=df.index)
    bh_equity, _, bh_stats = _simulate(
        df, bh_signal, strat_cfg, costs, leveraged=False, single_entry=True
    )

    return BacktestResult(
        equity_curve=strat_equity,
        benchmark_curve=bh_equity,
        trades=strat_trades,
        total_commissions=strat_stats["commissions"],
        total_margin_interest=strat_stats["margin_interest"],
        total_dividends_received=strat_stats["dividends"],
        n_trades=len(strat_trades),
    )


def _simulate(df, signal, strat_cfg, costs, leveraged: bool, single_entry: bool = False):
    dates = df.index
    n = len(dates)

    cash = strat_cfg.initial_capital
    shares = 0.0
    equity_curve = pd.Series(index=dates, dtype=float)
    trades = []

    total_commissions = 0.0
    total_margin_interest = 0.0
    total_dividends = 0.0

    prev_signal = 0.0
    last_rebalance_month = None

    for i, date in enumerate(dates):
        close = df["Close"].iloc[i]
        div = df["Dividends"].iloc[i]

        # 1. Dividendes reçus sur les actions détenues
        if shares > 0 and div > 0:
            cash += shares * div
            total_dividends += shares * div

        # 2. Intérêts de marge sur l'emprunt de la veille
        borrowed = max(0.0, -cash) if cash < 0 else 0.0
        if leveraged and borrowed > 0:
            interest = daily_margin_interest(borrowed, costs)
            cash -= interest
            total_margin_interest += interest

        # 3. Valorisation au close du jour
        equity = shares * close + cash

        # 4. Décision de rebalancement
        sig = signal.iloc[i]
        should_trade = False

        if single_entry:
            should_trade = (i == 0 and shares == 0)
        else:
            signal_changed = (sig != prev_signal)
            monthly_due = False
            if strat_cfg.rebalance_mode == "monthly" and sig == 1.0:
                month_key = (date.year, date.month)
                if last_rebalance_month != month_key:
                    monthly_due = True
            should_trade = signal_changed or monthly_due

        if should_trade:
            leverage = strat_cfg.target_leverage if leveraged else 1.0
            target_exposure = equity * leverage if sig == 1.0 else 0.0
            target_shares = target_exposure / close
            delta_shares = target_shares - shares

            if abs(delta_shares) > 1e-9:
                is_sell = delta_shares < 0
                trade_shares = abs(delta_shares)
                fee = commission(trade_shares, close, is_sell, costs)
                cash -= delta_shares * close  # achat: cash diminue; vente: cash augmente
                cash -= fee
                total_commissions += fee
                shares = target_shares

                trades.append({
                    "date": date,
                    "action": "SELL" if is_sell else "BUY",
                    "shares": trade_shares,
                    "price": close,
                    "commission": fee,
                    "equity_after": shares * close + cash,
                })

            last_rebalance_month = (date.year, date.month)

        prev_signal = sig
        equity = shares * close + cash
        equity_curve.iloc[i] = equity

    trades_df = pd.DataFrame(trades)
    stats = {
        "commissions": total_commissions,
        "margin_interest": total_margin_interest,
        "dividends": total_dividends,
    }
    return equity_curve, trades_df, stats
