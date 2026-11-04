"""Where the Python agents get the payment logic from.

The real logic is Person B's payments_app (blast.py, refunds.py, notify.py). Until
that is merged, or to try the agents in Switch without a database, set
BLAST_BACKEND=fake and they use agents/tests/fakes.py instead.

Every function here takes and returns exactly what blast-radius-context.md
section 8 says, so the agents never compute counts or amounts themselves.
"""

import os
from types import SimpleNamespace


def load_backend() -> SimpleNamespace:
    if os.environ.get("BLAST_BACKEND") == "fake":
        from agents.tests import fakes

        return SimpleNamespace(
            find_affected_customers=fakes.find_affected_customers,
            summarize=fakes.summarize,
            create_refund_batch=fakes.create_refund_batch,
            execute_refund_batch=fakes.execute_refund_batch,
            send_apology_emails=fakes.send_apology_emails,
            db_path=fakes.DB_PATH,
            refusals=(fakes.RefundError, ValueError),
        )

    from payments_app import blast, notify, refunds
    from payments_app.service.store import get_db_path

    return SimpleNamespace(
        find_affected_customers=blast.find_affected_customers,
        summarize=blast.summarize,
        create_refund_batch=refunds.create_refund_batch,
        execute_refund_batch=refunds.execute_refund_batch,
        send_apology_emails=notify.send_apology_emails,
        db_path=get_db_path(),
        # Errors whose message is written for people: shown in the room as they are.
        refusals=(refunds.RefundError, ValueError, FileNotFoundError),
    )
