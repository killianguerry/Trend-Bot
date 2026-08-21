"""
Configuration centrale du bot trend-following + levier.
Toutes les hypothèses de coûts et de paramètres de stratégie sont ici,
pour être faciles à auditer et ajuster.
"""

from dataclasses import dataclass, field


@dataclass
class IBCosts:
    """
    Modèle de coûts Interactive Brokers (IBKR Pro, tarification Tiered, actions/ETF US).
    Sources vérifiées le 18/08/2026 :
    - Commissions Tiered US stocks/ETFs : https://www.interactivebrokers.com/en/pricing/commissions-home.php
    - Taux de marge USD IBKR Pro       : https://www.interactivebrokers.com/en/trading/margin-rates.php
    Ces valeurs changent dans le temps (IBKR peut les modifier sans préavis) :
    à re-vérifier périodiquement, notamment le taux de marge qui suit le benchmark Fed Funds.
    """

    # --- Commissions (Tiered, actions/ETF cotés US) ---
    commission_per_share: float = 0.0035      # $ par action
    commission_min: float = 0.35              # $ minimum par ordre
    commission_max_pct: float = 0.01           # 1% max de la valeur de l'ordre

    # Frais réglementaires additionnels (approximatifs, appliqués à la vente)
    sec_fee_per_dollar_sold: float = 0.0000278  # SEC fee ~ $27.80 / million vendu (2026)
    finra_taf_per_share_sold: float = 0.000166  # TAF FINRA par action vendue (plafonné)
    finra_taf_cap: float = 8.30                 # plafond TAF par ordre

    # --- Taux de marge USD, IBKR Pro, au 07/08/2026 (barème par palier, taux "blended") ---
    # (seuil_bas, seuil_haut, taux_annuel)
    margin_rate_tiers: tuple = (
        (0, 100_000, 0.0513),
        (100_000, 1_000_000, 0.0463),
        (1_000_000, 50_000_000, 0.0438),
        (50_000_000, 250_000_000, 0.0413),
        (250_000_000, float("inf"), 0.0413),
    )
    margin_rate_floor: float = 0.0075  # plancher IBKR quel que soit le benchmark

    # --- Calendrier ---
    days_per_year: int = 365  # IBKR facture les intérêts sur base calendaire (365j), pas jours de bourse


@dataclass
class StrategyConfig:
    ticker: str = "QQQ"
    sma_window: int = 200          # moyenne mobile simple, en jours de bourse
    target_leverage: float = 1.25   # levier cible en position longue (1.2-1.3x demandé)
    confirm_days: int = 0           # nb de jours de confirmation du signal avant d'agir (0 = immédiat)
    rebalance_mode: str = "signal_only"  # "signal_only" ou "monthly"
    allow_short: bool = False       # pas de vente à découvert (limite le risque, cf. consigne)
    band_pct: float = 0.0           # bande morte optionnelle autour de la SMA pour éviter le bruit (ex: 0.01 = 1%)

    initial_capital: float = 10_000.0
    start_date: str = "2000-01-01"
    end_date: str = None  # None = aujourd'hui


@dataclass
class BacktestConfig:
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    costs: IBCosts = field(default_factory=IBCosts)
