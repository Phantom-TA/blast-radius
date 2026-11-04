# Switch side: handoff to Person B

From Person A (branch `feat/switch-agents`), for Person B (branch `feat/payments-core`).

**Do you need to do anything right now? No.** Nothing here blocks either of us. My code already runs against your branch as it is (tested against `dfd4d98`). The changes below are for when we merge, so `make demo` and `make verify` cover the Switch side too. I only edited my own files: `agents/`, `switch/`, `scripts/register_agents.py` and `scripts/post_complaint.py`.

## What the Switch side is

| File | What it does |
|---|---|
| `agents/common/switch_client.py` | The connection to Switch: registers an agent, keeps its WebSocket open (answers pings, reconnects, resumes where it stopped), and posts, mentions and reads room documents |
| `agents/common/backend.py` | Loads your functions from `payments_app`. With `BLAST_BACKEND=fake` it loads `agents/tests/fakes.py` instead |
| `agents/investigator/` | `python -m agents.investigator`. When @mentioned, it calls `find_affected_customers()` and `summarize()` and posts the counts, the total and the five biggest overcharges |
| `agents/treasurer/` | `python -m agents.treasurer`. `prepare refunds` calls `create_refund_batch()` and posts the batch in #finance-approvals for a person; `execute <batch id>` calls `execute_refund_batch(batch_id, approved_by=<that person>)`, then `send_apology_emails()` with the wording Support wrote as the room document "apology-email" |
| `agents/postmortem.py` | `check_postmortem()` for `verify.py` (item 1 below) |
| `switch/template.yaml` | The Switch Console template: the Support and Fixer Claude Code agents, #support and #finance-approvals. Generated from `switch/template.src.yaml` and the `.md` instructions by `switch/build_template.py` |
| `switch/import_template.py` | Imports that template through Switch's API, so nobody clicks through Console |
| `switch/archive_rooms.py` | Archives old `blast-` rooms so a rerun starts clean |
| `scripts/register_agents.py` | `make register`: registers investigator, treasurer and customer-sim and sets who may instruct each |
| `scripts/post_complaint.py` | The last step of your `scenario`: posts the complaint in #support as customer-sim, using `seed/complainer.json` |
| `switch/SETUP.md` | The judge's setup steps, in order |

Two things to know about how the money is protected:

- **Switch blocks agents from the Treasurer.** It is registered "people only" (any linked person, no agent). When an agent @mentions it, Switch itself replies in the room: "You're not permitted to direct messages to me in this room". We tested it with our own Claude Code agent. In the story, Support hands the refunds to the Treasurer like any other job, gets that refusal, and asks the person.
- **The Treasurer checks again in its own code**, and `execute_refund_batch` checks `approved_by` too. We tested that with Switch's rule opened by mistake: the code still refused the agent.

## What I need at merge time

### 1. `scripts/verify.py`: the postmortem check (replaces the TODO)

```python
from agents.postmortem import check_postmortem  # noqa: E402

    checks = [
        ("Bug fixed with a regression test", check_fix),
        ("Refunds correct with no double refunds", check_refunds),
        ("Apology emails delivered", check_emails),
        ("Postmortem room document", check_postmortem),
    ]
```

Then delete the two TODO lines at the end of `main()`. `check_postmortem()` returns `(passed, detail)` like your checks and never raises. It looks in every `blast-<order id>` room for a room document named `postmortem`, reading as the Switch owner so it never disturbs a running agent.

### 2. `README.md`: install the agents' requirements too

The agents need `websockets` (and `pyyaml` for their tests), which aren't in `payments_app/requirements.txt`:

```bash
pip install -r payments_app/requirements.txt -r agents/requirements.txt
```

The tests line could become `python -m pytest payments_app agents/tests` (77 tests on my side).

Please keep the virtualenv at `.venv` in the repo root, as the README says now. The Fixer runs your service's tests with `../../.venv/bin/python` from `demo-workspace/payments-service`, because the shell Switch Console starts for it has no virtualenv active.

### 3. `README.md`: a macOS line

The Switch machine is a Mac. Next to the Windows and Linux notes: on macOS use `python3 -m venv .venv` and `source .venv/bin/activate`.

### 4. `run.py demo`: import the template, and start the agents before the complaint

`demo` runs `up`, `register`, `scenario`, `agents`. On a fresh machine two things are missing:

- The rooms and the Claude Code agents come from `python switch/import_template.py`. It is safe to run twice: it does nothing once #support exists. Please add a `rooms` command for it and run it in `demo` right after `register`.
- `scenario` posts the complaint before `agents` starts the Investigator and Treasurer. They resume from where they last stopped, but on their very first start they only see new messages, so anything sent to them before that is missed. Starting the agents (in the background) before `scenario` avoids it.

`switch/SETUP.md` already uses this order: up, register, import_template, agents, scenario.

### 5. `run.py reset`: archive the old blast room and reset the agents

The seed always picks the same complainer, so a second run would make Support ask for a `blast-ORD-100953` room that already exists. Please call this from `cmd_reset()`:

```python
    run_optional_script("switch/archive_rooms.py")
```

And print at the end of `cmd_reset()`:

```
Now type !reset-all-agents in #support in Mattermost, so Support and Fixer start fresh.
```

## What my code relies on in yours (please keep these)

I ran both agents against your real code with a seeded scratch database, including the failure cases. Everything matches section 8 of the context file:

- 313 affected, 312 silent, $21,607.00. Prepare twice gives the same batch id; execute twice is refused; prepare after refunding finds nothing; 313 refunds in the database.
- A wording typo is refused by `send_apology_emails` before any email goes out. With the mail server down, a retry later sends all 313, and a second retry sends nobody twice.

So please keep:

- `RefundError`, `ValueError` and the "No database at ..." `FileNotFoundError` messages short and readable. The agents show them in the room as they are.
- The placeholders `{name}`, `{order_id}`, `{amount}`, and only those. Support is told to use exactly these.
- `create_refund_batch` returning the existing batch for the same charges, and `send_apology_emails` skipping customers already emailed. The Treasurer's retry command relies on both.
- `seed/complainer.json` with `order_id`, `customer_name`, `description` and `amount`. `post_complaint.py` reads them.
- `charge_order(provider, order_id, amount_cents)` and `FakeProvider(conn, should_timeout=None, now=None)`. The Fixer is told not to change these signatures, because your `verify.py` probe calls them.
