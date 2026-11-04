# What the Switch side needs from Person B

Person A doesn't edit these files, so here is what to change in them. Each item says why.

## 1. scripts/verify.py: the postmortem check (replaces the TODO)

The check is ready in `agents/postmortem.py`. It looks in every `blast-<order id>` room for a room document named `postmortem`, reading as the owner so it never disturbs a running agent.

```python
from agents.postmortem import check_postmortem  # noqa: E402

    checks = [
        ("Bug fixed with a regression test", check_fix),
        ("Refunds correct with no double refunds", check_refunds),
        ("Apology emails delivered", check_emails),
        ("Postmortem room document", check_postmortem),
    ]
```

Then delete the two TODO lines at the end of `main()`. `check_postmortem()` returns `(passed, detail)` like the other checks, and never raises.

## 2. README.md: install the agents' requirements too

The agents need `websockets` (and `pyyaml` for their tests), which `payments_app/requirements.txt` doesn't have:

```bash
pip install -r payments_app/requirements.txt -r agents/requirements.txt
```

The tests line could then be `python -m pytest payments_app agents/tests`.

## 3. README.md: a macOS line

The Switch machine is a Mac. Next to the Windows and Linux notes: on macOS use `python3 -m venv .venv` and `source .venv/bin/activate`.

## 4. run.py reset: archive the old blast room and reset the agents

The seed always picks the same complainer, so a second run would make Support ask for a `blast-ORD-...` room that already exists. `switch/archive_rooms.py` archives every `blast-` room (history and documents are kept). Please call it from `cmd_reset()`:

```python
    run_optional_script("switch/archive_rooms.py")
```

The Claude Code agents also still remember the last run, and the Fixer's folder has been recreated under it. Printing this at the end of `cmd_reset()` would help:

```
Now type !reset-all-agents in #support in Mattermost, so Support and Fixer start fresh.
```

## 5. run.py demo: import the template, and start the agents before the complaint

`demo` runs `up`, `register`, `scenario`, `agents`. Two things are missing on a fresh machine:

- The rooms and the Claude Code agents come from `python switch/import_template.py` (safe to run twice: it does nothing once #support exists). Please add a `rooms` command for it, and run it in `demo` right after `register`.
- `scenario` posts the complaint before `agents` starts the Investigator and Treasurer. They resume from where they last stopped, but on their very first start they only see new messages, so anything sent to them before that is missed. Starting the agents (in the background) before `scenario` avoids it.

switch/SETUP.md already follows this order: up, register, import_template, agents, scenario.

## Interface check (section 8): all good

I ran the Investigator and Treasurer against `feat/payments-core` (dfd4d98) with a scratch database: 313 affected, 312 silent, $21,607.00, batch prepared, executed, 313 emails sent, and a second execute refused. Everything matches the section 8 signatures. Two things the agents rely on, please keep them:

- `RefundError` and `ValueError` messages are shown in the room as they are, so keep them short and readable (they are now).
- `send_apology_emails` accepts only `{name}`, `{order_id}`, `{amount}`. Support is told to use exactly these.
