import pytest

from ..charge_client import MAX_ATTEMPTS, ChargeFailed, charge_order
from ..provider import ProviderTimeout


class ScriptedProvider:
    """Times out a set number of times, then answers."""

    def __init__(self, timeouts):
        self.timeouts = timeouts
        self.calls = 0

    def charge(self, order_id, amount_cents, idempotency_key=None):
        self.calls += 1
        if self.calls <= self.timeouts:
            raise ProviderTimeout(order_id)
        return 42


def test_returns_the_charge_id():
    assert charge_order(ScriptedProvider(timeouts=0), "ORD-1", 4900) == 42


def test_retries_after_a_timeout():
    provider = ScriptedProvider(timeouts=1)

    assert charge_order(provider, "ORD-1", 4900) == 42
    assert provider.calls == 2


def test_gives_up_after_max_attempts():
    provider = ScriptedProvider(timeouts=MAX_ATTEMPTS)

    with pytest.raises(ChargeFailed):
        charge_order(provider, "ORD-1", 4900)
    assert provider.calls == MAX_ATTEMPTS
