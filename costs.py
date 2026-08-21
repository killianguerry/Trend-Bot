"""
Modélisation des coûts Interactive Brokers.
"""

from config import IBCosts


def commission(shares: float, price: float, is_sell: bool, costs: IBCosts) -> float:
    """
    Commission IBKR Tiered pour un ordre US stocks/ETF.
    shares : nombre d'actions (peut être fractionnaire dans le backtest, IB
             autorise les fractional shares sur beaucoup d'ETF US).
    """
    if shares <= 0:
        return 0.0

    trade_value = shares * price
    base_commission = max(costs.commission_min, shares * costs.commission_per_share)
    base_commission = min(base_commission, trade_value * costs.commission_max_pct)

    reg_fees = 0.0
    if is_sell:
        sec_fee = trade_value * costs.sec_fee_per_dollar_sold
        taf_fee = min(shares * costs.finra_taf_per_share_sold, costs.finra_taf_cap)
        reg_fees = sec_fee + taf_fee

    return base_commission + reg_fees


def margin_rate_for_balance(borrowed_amount: float, costs: IBCosts) -> float:
    """
    Taux de marge "blended" IBKR : chaque palier du barème est facturé à son
    propre taux (pas juste le taux du palier final), comme documenté par IBKR
    ("for a balance over USD 1,000,000, the first 100,000 is charged at the
    Tier I rate, the next 900,000 at the Tier II rate, etc.").
    """
    if borrowed_amount <= 0:
        return 0.0

    total_interest_rate_weighted = 0.0
    remaining = borrowed_amount

    for low, high, rate in costs.margin_rate_tiers:
        if remaining <= 0:
            break
        tier_size = min(high, borrowed_amount) - low
        if tier_size <= 0:
            continue
        amount_in_tier = min(tier_size, remaining)
        total_interest_rate_weighted += amount_in_tier * rate
        remaining -= amount_in_tier

    blended_rate = total_interest_rate_weighted / borrowed_amount
    return max(blended_rate, costs.margin_rate_floor)


def daily_margin_interest(borrowed_amount: float, costs: IBCosts) -> float:
    """Intérêt de marge dû pour UNE journée (facturation calendaire, base 365j)."""
    if borrowed_amount <= 0:
        return 0.0
    annual_rate = margin_rate_for_balance(borrowed_amount, costs)
    return borrowed_amount * annual_rate / costs.days_per_year
