"""Fake card processor. Stands in for an external provider such as a bank gateway."""

from datetime import datetime, timezone


class ProviderTimeout(Exception):
    """The provider did not answer in time. The charge may still have gone through."""


class FakeProvider:
    def __init__(self, conn, should_timeout=None, now=None):
        self._conn = conn
        self._should_timeout = should_timeout or (lambda order_id: False)
        self._now = now or (lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))

    def charge(self, order_id: str, amount_cents: int, idempotency_key: str | None = None) -> int:
        """Charge the card and return the charge id.

        A repeat call with the same idempotency_key returns the original charge
        instead of charging again.
        """
        if idempotency_key is not None:
            row = self._conn.execute(
                "SELECT id FROM charges WHERE idempotency_key = ?", (idempotency_key,)
            ).fetchone()
            if row is not None:
                return row["id"]

        cursor = self._conn.execute(
            "INSERT INTO charges (order_id, amount_cents, status, idempotency_key, created_at) "
            "VALUES (?, ?, 'succeeded', ?, ?)",
            (order_id, amount_cents, idempotency_key, self._now()),
        )

        # The money has moved by this point. A timeout only loses the response.
        if self._should_timeout(order_id):
            raise ProviderTimeout(f"no response for order {order_id}")
        return cursor.lastrowid
