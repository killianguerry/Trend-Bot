"""
Interface Streamlit pour le backtest trend-following + levier.

Déploiement : pousse ce dossier sur GitHub, puis connecte le repo sur
share.streamlit.io. Fichier d'entrée : streamlit_app.py

Deux modes disponibles dans la barre latérale :
- Backtest simple  : un seul jeu de paramètres, résultats détaillés + graphique
- Balayage de paramètres : teste une grille de (SMA, levier) sur plusieurs
  périodes pour vérifier la robustesse (évite le surajustement à un seul réglage)
"""

import itertools
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st

from config import BacktestConfig, StrategyConfig, IBCosts
from data_loader import load_price_data
from backtest import run_backtest
from metrics import compute_metrics

st.set_page_config(page_title="Trend-following QQQ + levier", layout="wide")

st.title("Trend-following QQQ + levier — backtest avec frais IBKR réels")
st.caption(
    "Signal SMA sur QQQ, levier modéré, coûts Interactive Brokers réels "
    "(commissions + intérêts de marge par palier). Ceci n'est pas un conseil "
    "financier — un backtest n'est pas une garantie de performance future."
)

mode = st.sidebar.radio(
    "Mode",
    ["Backtest simple", "Balayage de paramètres (robustesse)"],
    help="Le balayage teste plusieurs réglages sur plusieurs périodes pour "
         "vérifier qu'un bon résultat n'est pas juste un coup de chance.",
)


@st.cache_data(show_spinner=False)
def get_data(ticker: str, start: str):
    """Cache les données téléchargées pour éviter de re-télécharger à chaque run."""
    return load_price_data(ticker, start=start)


def build_costs(margin_rate_tier1: float, commission_per_share: float) -> IBCosts:
    costs = IBCosts()
    tiers = list(costs.margin_rate_tiers)
    tiers[0] = (tiers[0][0], tiers[0][1], margin_rate_tier1)
    costs.margin_rate_tiers = tuple(tiers)
    costs.commission_per_share = commission_per_share
    return costs


# ============================================================
# MODE 1 : BACKTEST SIMPLE
# ============================================================
if mode == "Backtest simple":
    st.sidebar.header("Paramètres de la stratégie")

    ticker = st.sidebar.text_input("Ticker", value="QQQ")
    sma_window = st.sidebar.slider("Fenêtre SMA (jours de bourse)", 50, 350, 200, step=10)
    target_leverage = st.sidebar.slider("Levier cible", 1.0, 2.0, 1.25, step=0.05)
    band_pct = st.sidebar.slider("Bande morte autour de la SMA (%)", 0.0, 5.0, 0.0, step=0.5) / 100
    confirm_days = st.sidebar.slider("Jours de confirmation du signal", 0, 10, 0)
    rebalance_mode = st.sidebar.selectbox("Mode de rebalancement", ["signal_only", "monthly"])
    initial_capital = st.sidebar.number_input("Capital initial ($)", value=10_000, step=1_000)

    st.sidebar.header("Période")
    start_date = st.sidebar.date_input("Date de début", value=pd.Timestamp("2000-01-01"))
    end_date = st.sidebar.date_input("Date de fin", value=pd.Timestamp.today())

    st.sidebar.header("Coûts IBKR (avancé)")
    st.sidebar.caption("Taux vérifiés le 18/08/2026 — à mettre à jour périodiquement.")
    margin_rate_tier1 = st.sidebar.number_input(
        "Taux de marge palier 1 (%, jusqu'à $100k)", value=5.13, step=0.1
    ) / 100
    commission_per_share = st.sidebar.number_input(
        "Commission par action ($)", value=0.0035, step=0.0005, format="%.4f"
    )

    run_button = st.sidebar.button("Lancer le backtest", type="primary")

    if run_button:
        strat_cfg = StrategyConfig(
            ticker=ticker,
            sma_window=sma_window,
            target_leverage=target_leverage,
            band_pct=band_pct,
            confirm_days=confirm_days,
            rebalance_mode=rebalance_mode,
            initial_capital=float(initial_capital),
            start_date=str(start_date),
            end_date=str(end_date),
        )
        costs = build_costs(margin_rate_tier1, commission_per_share)
        cfg = BacktestConfig(strategy=strat_cfg, costs=costs)

        with st.spinner(f"Téléchargement des données {ticker} et calcul du backtest..."):
            try:
                df = get_data(ticker, str(start_date))
                df = df.loc[df.index <= pd.Timestamp(end_date)]
            except Exception as e:
                st.error(f"Erreur lors du chargement des données : {e}")
                st.stop()

            if len(df) < sma_window + 10:
                st.error(
                    f"Pas assez de données ({len(df)} jours) pour une SMA de {sma_window} jours. "
                    f"Élargis la période ou réduis la fenêtre SMA."
                )
                st.stop()

            result = run_backtest(df, cfg)

        strat_metrics = compute_metrics(result.equity_curve, "Stratégie")
        bh_metrics = compute_metrics(result.benchmark_curve, "Buy & Hold")

        st.subheader("Résumé")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric(
            "CAGR stratégie", f"{strat_metrics['CAGR']*100:.2f}%",
            delta=f"{(strat_metrics['CAGR']-bh_metrics['CAGR'])*100:+.2f} pts vs B&H",
        )
        col2.metric(
            "Max Drawdown", f"{strat_metrics['Max Drawdown']*100:.1f}%",
            delta=f"{(strat_metrics['Max Drawdown']-bh_metrics['Max Drawdown'])*100:+.1f} pts vs B&H",
            delta_color="inverse",
        )
        col3.metric("Sharpe (rf=4%)", f"{strat_metrics['Sharpe (rf=4%)']:.2f}",
                    delta=f"{strat_metrics['Sharpe (rf=4%)']-bh_metrics['Sharpe (rf=4%)']:+.2f} vs B&H")
        col4.metric("Calmar", f"{strat_metrics['Calmar']:.2f}",
                    delta=f"{strat_metrics['Calmar']-bh_metrics['Calmar']:+.2f} vs B&H")

        st.subheader("Tableau comparatif complet")
        comp_df = pd.DataFrame({
            "Stratégie": {
                "CAGR": f"{strat_metrics['CAGR']*100:.2f}%",
                "Volatilité annualisée": f"{strat_metrics['Volatilité annualisée']*100:.2f}%",
                "Max Drawdown": f"{strat_metrics['Max Drawdown']*100:.2f}%",
                "Sharpe (rf=4%)": f"{strat_metrics['Sharpe (rf=4%)']:.2f}",
                "Calmar": f"{strat_metrics['Calmar']:.2f}",
                "Valeur finale ($)": f"{strat_metrics['Valeur finale']:,.0f}",
            },
            "Buy & Hold": {
                "CAGR": f"{bh_metrics['CAGR']*100:.2f}%",
                "Volatilité annualisée": f"{bh_metrics['Volatilité annualisée']*100:.2f}%",
                "Max Drawdown": f"{bh_metrics['Max Drawdown']*100:.2f}%",
                "Sharpe (rf=4%)": f"{bh_metrics['Sharpe (rf=4%)']:.2f}",
                "Calmar": f"{bh_metrics['Calmar']:.2f}",
                "Valeur finale ($)": f"{bh_metrics['Valeur finale']:,.0f}",
            },
        })
        st.table(comp_df)

        st.subheader("Coûts réels payés")
        cost1, cost2, cost3 = st.columns(3)
        cost1.metric("Commissions totales", f"{result.total_commissions:,.2f} $")
        cost2.metric("Intérêts de marge totaux", f"{result.total_margin_interest:,.2f} $")
        cost3.metric("Nombre de trades", f"{result.n_trades}")

        st.subheader("Courbe d'équité")
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), sharex=True,
                                         gridspec_kw={"height_ratios": [3, 1]})

        ax1.plot(result.equity_curve.index, result.equity_curve.values,
                  label=f"Stratégie (levier {target_leverage}x)", color="#1f77b4")
        ax1.plot(result.benchmark_curve.index, result.benchmark_curve.values,
                  label=f"Buy & Hold {ticker}", color="#888888", linestyle="--")
        ax1.set_yscale("log")
        ax1.set_ylabel("Valeur du portefeuille ($, échelle log)")
        ax1.legend()
        ax1.grid(alpha=0.3)

        strat_dd = result.equity_curve / result.equity_curve.cummax() - 1
        bh_dd = result.benchmark_curve / result.benchmark_curve.cummax() - 1
        ax2.fill_between(strat_dd.index, strat_dd.values * 100, 0, color="#1f77b4", alpha=0.4, label="Stratégie")
        ax2.fill_between(bh_dd.index, bh_dd.values * 100, 0, color="#888888", alpha=0.3, label="Buy & Hold")
        ax2.set_ylabel("Drawdown (%)")
        ax2.legend()
        ax2.grid(alpha=0.3)

        plt.tight_layout()
        st.pyplot(fig)

        st.subheader("Journal des trades")
        if len(result.trades) > 0:
            st.dataframe(result.trades, use_container_width=True)
            csv = result.trades.to_csv(index=False).encode("utf-8")
            st.download_button("Télécharger trades.csv", csv, "trades.csv", "text/csv")
        else:
            st.info("Aucun trade sur la période sélectionnée.")

    else:
        st.info("Configure les paramètres dans la barre latérale puis clique sur **Lancer le backtest**.")


# ============================================================
# MODE 2 : BALAYAGE DE PARAMÈTRES
# ============================================================
else:
    st.sidebar.header("Grille à tester")

    ticker = st.sidebar.text_input("Ticker", value="QQQ")

    sma_min, sma_max = st.sidebar.select_slider(
        "Plage de fenêtres SMA (jours)",
        options=[50, 100, 150, 200, 250, 300, 350],
        value=(100, 300),
    )
    sma_step = st.sidebar.selectbox("Pas entre chaque fenêtre SMA", [25, 50, 100], index=1)
    sma_windows = list(range(sma_min, sma_max + 1, sma_step))

    lev_min, lev_max = st.sidebar.select_slider(
        "Plage de levier",
        options=[1.0, 1.15, 1.25, 1.35, 1.5, 1.75, 2.0],
        value=(1.15, 1.5),
    )
    leverages = sorted(set([lv for lv in [1.0, 1.15, 1.25, 1.35, 1.5, 1.75, 2.0]
                             if lev_min <= lv <= lev_max]))

    st.sidebar.header("Périodes à comparer")
    st.sidebar.caption(
        "On teste chaque combinaison sur les deux périodes pour repérer les "
        "réglages qui marchent partout, pas seulement grâce à un crash particulier."
    )
    period_full_start = st.sidebar.date_input("Période 1 — début", value=pd.Timestamp("2000-01-01"))
    period_recent_start = st.sidebar.date_input("Période 2 — début", value=pd.Timestamp("2003-01-01"))

    st.sidebar.header("Coûts IBKR (avancé)")
    margin_rate_tier1 = st.sidebar.number_input(
        "Taux de marge palier 1 (%, jusqu'à $100k)", value=5.13, step=0.1, key="sweep_margin"
    ) / 100
    commission_per_share = st.sidebar.number_input(
        "Commission par action ($)", value=0.0035, step=0.0005, format="%.4f", key="sweep_comm"
    )

    n_combos = len(sma_windows) * len(leverages) * 2
    st.sidebar.caption(f"{n_combos} backtests seront lancés.")

    run_sweep = st.sidebar.button("Lancer le balayage", type="primary")

    if run_sweep:
        if n_combos == 0:
            st.error("Aucune combinaison à tester avec ces réglages, élargis les plages.")
            st.stop()

        periods = {
            "Période 1": str(period_full_start),
            "Période 2": str(period_recent_start),
        }
        costs = build_costs(margin_rate_tier1, commission_per_share)

        with st.spinner(f"Téléchargement des données {ticker}..."):
            try:
                df_full = get_data(ticker, min(periods.values()))
            except Exception as e:
                st.error(f"Erreur lors du chargement des données : {e}")
                st.stop()

        df_by_period = {
            label: df_full.loc[df_full.index >= pd.Timestamp(start)]
            for label, start in periods.items()
        }

        progress = st.progress(0.0, text="Lancement du balayage...")
        combos = list(itertools.product(sma_windows, leverages, periods.keys()))
        rows = []

        for i, (sma_window, leverage, period_label) in enumerate(combos):
            df = df_by_period[period_label]
            if len(df) < sma_window + 10:
                progress.progress((i + 1) / len(combos))
                continue

            strat_cfg = StrategyConfig(
                ticker=ticker,
                sma_window=sma_window,
                target_leverage=leverage,
                start_date=periods[period_label],
            )
            cfg = BacktestConfig(strategy=strat_cfg, costs=costs)
            result = run_backtest(df, cfg)
            strat_m = compute_metrics(result.equity_curve, "Stratégie")
            bh_m = compute_metrics(result.benchmark_curve, "Buy & Hold")

            rows.append({
                "Période": period_label,
                "SMA": sma_window,
                "Levier": leverage,
                "CAGR strat.": strat_m["CAGR"],
                "CAGR B&H": bh_m["CAGR"],
                "Écart CAGR": strat_m["CAGR"] - bh_m["CAGR"],
                "MaxDD strat.": strat_m["Max Drawdown"],
                "MaxDD B&H": bh_m["Max Drawdown"],
                "Sharpe strat.": strat_m["Sharpe (rf=4%)"],
                "Sharpe B&H": bh_m["Sharpe (rf=4%)"],
                "Écart Sharpe": strat_m["Sharpe (rf=4%)"] - bh_m["Sharpe (rf=4%)"],
                "Calmar strat.": strat_m["Calmar"],
                "Calmar B&H": bh_m["Calmar"],
                "Trades": result.n_trades,
            })
            progress.progress((i + 1) / len(combos),
                               text=f"Combinaison {i+1}/{len(combos)} : SMA={sma_window}, levier={leverage}, {period_label}")

        progress.empty()
        results = pd.DataFrame(rows)

        if results.empty:
            st.error("Aucun résultat — vérifie que les périodes contiennent assez de données pour les SMA choisies.")
            st.stop()

        st.success(f"{len(results)} backtests terminés.")

        # --- Combinaisons robustes : Sharpe > B&H sur TOUTES les périodes testées ---
        pivot_sharpe_edge = results.pivot_table(index=["SMA", "Levier"], columns="Période", values="Écart Sharpe")
        robust_mask = (pivot_sharpe_edge > 0).all(axis=1)
        robust = pivot_sharpe_edge[robust_mask]

        st.subheader("Combinaisons robustes")
        st.caption(
            "Réglages où la stratégie bat le buy&hold en Sharpe (rendement ajusté au "
            "risque) sur **toutes** les périodes testées — pas seulement une."
        )
        if len(robust) > 0:
            st.dataframe(robust.round(3), use_container_width=True)
        else:
            st.warning(
                "Aucune combinaison ne bat le buy&hold en Sharpe sur toutes les périodes "
                "à la fois. Le signal SMA seul n'apporte probablement pas d'edge en "
                "rendement ajusté au risque en dehors de crashs extrêmes type 2000-2002. "
                "Il faudra soit changer de signal, soit accepter l'objectif "
                "'réduction du drawdown' plutôt que 'battre le marché en performance'."
            )

        st.subheader("Écart de Sharpe (stratégie − buy&hold) par combinaison et période")
        st.dataframe(pivot_sharpe_edge.round(3), use_container_width=True)

        pivot_cagr_edge = results.pivot_table(index=["SMA", "Levier"], columns="Période", values="Écart CAGR") * 100
        st.subheader("Écart de CAGR en points (stratégie − buy&hold) par combinaison et période")
        st.dataframe(pivot_cagr_edge.round(2), use_container_width=True)

        st.subheader("Résultats complets")
        st.dataframe(results, use_container_width=True)
        csv = results.to_csv(index=False).encode("utf-8")
        st.download_button("Télécharger sweep_results.csv", csv, "sweep_results.csv", "text/csv")

    else:
        st.info(
            "Configure la grille dans la barre latérale puis clique sur "
            "**Lancer le balayage**. Selon le nombre de combinaisons, ça peut "
            "prendre de quelques secondes à quelques minutes."
        )
