"""Client the shop uses to charge an order through the payment provider."""

from .provider import ProviderTimeout

MAX_ATTEMPTS = 3


class ChargeFailed(Exception):
    """The provider never answered, even after retrying."""


def charge_order(provider, order_id: str, amount_cents: int) -> int:
    """Charge an order, retrying when the provider times out. Returns the charge id."""
    for _ in range(MAX_ATTEMPTS):
        try:
            return provider.charge(order_id, amount_cents)
        except ProviderTimeout:
            continue
    raise ChargeFailed(f"order {order_id}: no response after {MAX_ATTEMPTS} attempts")
