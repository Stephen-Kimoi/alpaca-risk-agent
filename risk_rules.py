"""Pure risk-management math. No I/O, no API calls — testable in isolation
and the one module the rest of the agent is not allowed to route around."""

from dataclasses import dataclass


@dataclass
class RiskLimits:
    max_risk_per_trade_pct: float = 0.005      # lose at most 0.5% of equity if the stop fills
    max_daily_loss_pct: float = 0.03           # halt all new entries after -3% on the day
    max_position_concentration_pct: float = 0.20  # no single symbol > 20% of equity
    stop_loss_pct: float = 0.03                # stop sits 3% below entry
    reward_risk_ratio: float = 2.0             # take-profit is 2x the stop distance


def stop_loss_price(entry_price: float, limits: RiskLimits) -> float:
    return round(entry_price * (1 - limits.stop_loss_pct), 2)


def take_profit_price(entry_price: float, stop_price: float, limits: RiskLimits) -> float:
    risk_per_share = entry_price - stop_price
    return round(entry_price + risk_per_share * limits.reward_risk_ratio, 2)


def position_size(equity: float, entry_price: float, stop_price: float, limits: RiskLimits) -> int:
    """Size the trade so a stop-out costs at most max_risk_per_trade_pct of equity.

    This is the actual risk control — position size is derived from the stop
    distance, not picked first and checked after. A wide stop on a volatile
    symbol automatically produces a smaller size; the dollar risk per trade
    stays constant even though share count doesn't.
    """
    risk_per_share = entry_price - stop_price
    if risk_per_share <= 0:
        return 0
    dollar_risk_budget = equity * limits.max_risk_per_trade_pct
    return max(int(dollar_risk_budget // risk_per_share), 0)


def breaches_daily_loss_limit(equity: float, last_equity: float, limits: RiskLimits) -> bool:
    if last_equity <= 0:
        return False
    daily_pnl_pct = (equity - last_equity) / last_equity
    return daily_pnl_pct <= -limits.max_daily_loss_pct


def breaches_concentration_limit(
    equity: float, existing_position_value: float, new_order_value: float, limits: RiskLimits
) -> bool:
    projected = existing_position_value + new_order_value
    return projected > equity * limits.max_position_concentration_pct
