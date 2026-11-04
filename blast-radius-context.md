# Blast Radius: Project Context (Flip the Switch Hackathon)

> **How to use this file:** Upload or paste it into a Claude chat, then say which person you are, for example: *"I'm Person B on this project. Help me build my part."* Everything the team has decided so far is in here.
>
> Last updated: Nov 4, 2026, ~2:30 PM IST. Team: Tushar Agrawal and teammate (2 people).

---

## 1. The hackathon

- **Name:** Flip the Switch Hackathon, hosted by WeMakeDevs and DevTools Academy, powered by Switch (made by SandboxAQ).
- **Dates:** Nov 4, 12:01 AM IST to **Nov 7, 11:59 PM IST** (submission deadline). Our target is to submit by the evening of Nov 7, not at the last minute.
- **Our track:** Track 01, **Best Business Workflow** ($2,000 cash). Brief: a practical workflow where people and AI agents get work done together.
- **What must be true about the project:**
  - A workflow in team chat where at least one AI agent and one person finish a real task together, connected through Switch.
  - Switch must be central, and the README must show how it is used.
  - AI coding tools are allowed, but we must understand our code and be able to explain it.
  - The Switch setup and the workflow must be built during the hackathon. Existing libraries and agents are fine.
- **Judging weights:**
  - **30% Use of Switch:** is Switch central, and would the project stop working without it?
  - **25% Technical execution:** does it run, and can someone clone the repo and reproduce it?
  - **25% Creativity and impact:** is it a fresh idea that solves a problem a real team has?
  - **20% Presentation:** do the demo video and README make clear how Switch is used?
- **Judging process:** WeMakeDevs reviews every submission and builds a shortlist. Finalists are then judged by Switch, DevTools Academy and WeMakeDevs. So we must survive a fast skim (first 15 seconds of the video plus the README), then impress the people who built Switch.
- **Optional extra entries using the same project:** Best Blog (AirPods 5), #HowISwitch social post (top 5 get a keyboard), Code with Wispr ($500 for building by voice with Wispr Flow).
- **Links:**
  - Hackathon: https://www.wemakedevs.org/hackathons/switch
  - Resources: https://www.wemakedevs.org/hackathons/switch/resources
  - Help: WeMakeDevs Discord https://discord.gg/E2rWw2Yhsm

---

## 2. What Switch is (only what we need)

- An open-source layer that puts AI agents (Claude Code, Codex, OpenCode, or custom agents) into team chat apps (Slack, Teams, Discord, Telegram, Mattermost).
- **Each chat channel becomes a "room."** People and agents in a room share the same history and context. Each agent appears with its own name.
- **Room building blocks:**
  - **Room instructions:** a briefing every agent reads when it joins the room.
  - **Roles:** a named job (e.g. `@reviewer`) with its own instructions. Anyone can address the role and it reaches whichever agent currently holds it. An agent holds one role at a time. A role can be shared or exclusive.
  - **References:** pointers to outside material (a GitHub repo, a Jira project, etc.) with instructions on when to use them.
  - **Room documents:** text stored inside the room. An agent can write one, e.g. a postmortem. Max 1 MB, and the name must be unique in the room.
  - **Room links:** connect rooms so agents know which other rooms matter and why.
- **Agents can set up the organization themselves.** They can create rooms, write room instructions, define and take roles, link rooms, attach references, and invite agents and people.
- **Handing work over:** one agent hands work to another with a targeted message or an @mention. **There is no separate "task" system**, so don't build around one.
- **Switch Console:** the desktop app. It runs our agents and starts a local Switch server in Docker.
  - Needs Docker. On Windows use Docker Desktop or Rancher Desktop (no WSL needed).
  - Windows and Linux builds are "early access."
  - The first server start downloads a few GB.
- **The local server comes with Mattermost** as the chat app. **Only one person can sign in to a server running on a laptop.** Colleagues can only reach it if we connect Slack, Discord or Telegram. So our baseline demo has one human playing every human part.
- **Templates:** Console can create rooms and agents from a saved setup file (YAML). Fields seen in Switch's examples:
  - an agent's name, description, addressing, provider and instructions;
  - a room's name, bridge, agents and users;
  - a kickoff message.

### Who can make an agent act ("addressing")

- A new agent answers only its owner and the owner's other agents. Everyone else gets a visible reply saying it can't act.
- The policy options are `owner_only`, `owner_and_owner_agents` and `anyone`. Templates spell the second one `owner-agents`.
- Custom rules can also limit by user, by agent, by room, or by room group. A "people only" rule is possible: allow humans, with an empty agent list.
- **An agent cannot change its own policy.** Only its owner can, in Console.
- **When someone not allowed tries to instruct the agent, it posts a visible refusal in the room.** This is our key demo moment (see section 4).
- Gotcha: a chat account that isn't linked to a Switch user matches nobody, so the agent ignores it. Local Mattermost links your account automatically.

### Custom agents (the "agent protocol")

A custom agent can be plain Python with no LLM. The steps:

1. Register once: `POST /agents` with a *registration* API key (created on the Gateway's API Keys page). The request needs `name`, `description`, `connector_type` and an `integration_profile` containing `connection_model`, `message_exchange` and empty mediation lists. The response returns `{id, api_key}`, and the key is shown only once. Save it.
2. Set who it answers: `POST /agents/{id}/ops/update_agent_detail` with `addressing`.
3. Open a WebSocket at `/agents/{id}/connection/ws` with a Bearer API key and a fixed connection id (a UUID you reuse on every reconnect). Answer every ping with a pong.
4. React only to `message` events where `payload.addressed == true`.
5. Call operations with `POST /agents/{id}/ops/{operation}` plus the header `X-Switch-Connection-Id`. List the available ones with `GET /agents/{id}/ops`.
6. To post without any connection: `POST /agents/{id}/message` with `{room_id, content}`.

More details:

- **Operations include:**
  - rooms: `create_room`, `invite_agent_to_room`, `add_users_to_room`
  - messages: `post_message`, `send_targeted_message`, `read_context`
  - roles: `define_role`, `assume_role`
  - other: `link_rooms`, `create_room_document`, `attach_reference_to_room`
- The bridge URL is usually **not** the Gateway URL. `GET /health` tells you if you found the right one.
- The old SSE connection is deprecated; use the WebSocket. The docs also warn that "connection models" will change, so **pin the Switch Console version** and note it in the README.

### Docs

- Index: https://docs.switchagents.ai/llms.txt
- Agent protocol: https://docs.switchagents.ai/switch-rooms/internals/agent-protocol.md
- Who can talk to an agent: https://docs.switchagents.ai/switch-rooms/internals/identity-and-access.md
- Payments room tutorial (very relevant): https://docs.switchagents.ai/switch-rooms/building/payments-room.md
- Quickstart: https://docs.switchagents.ai/switch-rooms/getting-started
- Let Claude Code read the docs directly: `claude mcp add switch-docs --transport http https://docs.switchagents.ai/mcp`
- Repo: https://github.com/sandbox-quantum/switch

---

## 3. Ideas we rejected, and why

| Idea | Why not |
|---|---|
| Incident response / bug triage → fix → deploy | Switch's own README, landing-page demo and docs already show it. Dozens of teams will build it. |
| Vendor purchase review across security, legal, finance | Already a scenario in Switch's docs. |
| Follow-the-sun handoff across time zones | Already a scenario in Switch's docs. |
| Agent code reviewed by a different AI provider, with an audit trail | Narrow audience, weaker demo. |

**Chosen idea: Blast Radius.** It isn't in Switch's docs, it crosses three departments (support, engineering, finance), and it has the strongest demo hook.

---

## 4. Our project: Blast Radius

### Pitch

One customer complains about being charged twice. Our agents find every other customer the same bug hit (most never complained), fix the bug, refund everyone, and apologize to them before they complain. Humans approve the code fix and the money.

### The bug we plant

The fake payment service retries a charge after a timeout **without an idempotency key**. Some orders get charged twice.

- **Fix:** send an idempotency key per order, and have the fake payment provider ignore repeat keys.
- **Regression test:** simulate a timeout followed by a retry, and check there is exactly one charge.

### Seeded scenario (always the same)

- A fixed random seed gives the same data every run.
- Target numbers: **313 affected customers = 1 who complains + 312 who stay silent.**
- Use whatever the seed actually produces, and keep the README, video and `make verify` consistent with it.
- Currency: USD.

### The story (what the demo shows)

1. A customer message appears in `#support`: "I was charged twice for order X."
2. **Support agent** (Claude Code) reads it, opens a new room for this problem (e.g. `#blast-<id>`), invites the other agents, and hands out the work by @mention.
3. **Investigator agent** (plain Python, no LLM) runs read-only checks on the database and posts the result: 313 affected customers and the total amount.
4. **Fixer agent** (Claude Code, working in the payment app repo) finds the bug, fixes it, and adds the regression test on a branch.
5. **The human approves the fix.**
6. **Support agent** drafts the apology email text. **The human approves the wording.**
7. **Treasurer agent** (plain Python, no LLM) builds the refund batch and posts it in `#finance-approvals`.
   - **The key moment:** another agent tells the Treasurer to execute the refunds, and **Switch refuses it** with a visible reply, because the Treasurer only takes instructions from people.
   - The human then approves, and the Treasurer executes.
8. **Treasurer** sends the apology emails to a local fake inbox (Mailpit): 312 emails, plus a reply to the customer who complained.
9. An agent writes a short postmortem as a **room document**.

### Rooms

- `#support`: complaints land here.
- `#blast-<id>`: created by the Support agent for each problem.
- `#finance-approvals`: a standing room where every money action waits for a human.

### Agents

| Agent | Built with | Why |
|---|---|---|
| Support | Claude Code | Needs judgment and language |
| Fixer | Claude Code | Writes code |
| Investigator | Plain Python, Switch agent protocol | Numbers must be identical every run |
| Treasurer | Plain Python, Switch agent protocol, addressing = people only | Money must never come from an LLM; Switch blocks agents from triggering it |
| (Optional) Reviewer | Codex or OpenCode | Cut first if short on time |

### "Why this breaks without Switch" (goes in the README)

- The complaint, the database findings, the code diff and both approvals live in one trail across three rooms.
- Each agent starts from the room's context instead of being re-briefed.
- Switch's addressing rules decide who is allowed to trigger refunds.
- The postmortem is written from that trail.
- Without Switch, you'd have four disconnected bots and a human copy-pasting between them.

---

## 5. Design decisions (discuss before changing)

1. **Only one login is required: Claude Code.** Codex/OpenCode is optional.
2. **The money and data agents are plain Python.** An LLM never calculates counts or refund amounts.
3. **Never use the word "incident" and never show server errors.** Lead with customers and money; the engineering part is the part that overlaps Switch's own docs.
4. **If we're behind, cut in this order:**
   1. the optional Reviewer agent;
   2. the email blast (show one drafted email instead).

   Never cut the core: complaint → affected customers found → fix → human-approved refund.
5. The README says plainly that the payment service and data are simulated.
6. Keep the laptop load light: SQLite, one FastAPI process, Mailpit, and at most two Claude Code sessions running at once.

---

## 6. Making it easy for judges to reproduce

- `make up`: starts the fake payment app and Mailpit.
- `make register`: registers the two Python agents with Switch and sets their addressing.
- A Console **template file** for the rooms and the Claude Code agents, so a judge imports one file instead of clicking through setup.
- `make scenario`: resets the database to the seed, resets the sample repo, and posts the customer complaint.
- `make reset`: starts over.
- `make verify`: prints PASS/FAIL for each check:
  - the fixed code's tests pass;
  - refunds are recorded with the correct total;
  - the expected number of emails is in Mailpit;
  - the postmortem document exists.
- Commit a **reference transcript** (exported room history from a good run) to the repo.
- README: the pinned Switch Console version, setup steps, an architecture diagram, the "why this breaks without Switch" section, and troubleshooting:
  - link your chat account;
  - start Docker before Switch;
  - the Windows SmartScreen warning.
- On Nov 6, someone follows the README on a clean machine.

---

## 7. Team split

**Person A runs the "Switch machine,"** whichever laptop is stronger. Tushar's laptop has 8 GB RAM and an i5-12500H; if the teammate's has more RAM, the teammate is Person A. Only one person can sign in to a local Switch server, and the demo video is recorded on this machine.

| Person A (Switch machine) | Person B (any laptop, Switch not needed) |
|---|---|
| Install Switch Console, run the local server, connect Claude Code | Fake payment app with the planted bug (FastAPI + SQLite) |
| Rooms, room instructions, Support and Fixer agents, the template file | Seed data with a fixed random seed (313 affected) |
| The Switch side of the Python agents: register, WebSocket, calling operations | The logic: find affected customers, refund batch, execute refunds, send emails to Mailpit |
| Addressing setup and the "refused" moment | Makefile (`up`, `scenario`, `reset`, `verify`), README, video editing |
| Recording the demo, exporting the transcript | Clean-machine test on Nov 6 |

**Where the halves join:** Person A's Python agents call Person B's functions. Agree on the interface below early.

**How we work together:**

- One GitHub repo, separate folders, small and frequent pushes.
- Two 10-minute calls a day (morning and night).
- Both of us must read and understand all the code.

---

## 8. Interface between A and B (proposal, adjust together)

```python
# payments_app/blast.py
def find_affected_customers(db_path: str) -> list[dict]:
    """Each item: customer_id, email, order_id, charge_ids, overcharge_amount (USD)."""

def summarize(affected: list[dict]) -> dict:
    """Returns {"count": int, "silent_count": int, "total_overcharge": float, "currency": "USD"}"""

# payments_app/refunds.py
def create_refund_batch(affected: list[dict]) -> str:
    """Creates a batch with status 'pending_approval'. Returns batch_id."""

def execute_refund_batch(batch_id: str, approved_by: str) -> dict:
    """Refuses unless the status is 'pending_approval' and approved_by is set.
    Marks the refunds done in the database. Returns {"refunded": int, "total": float}."""

# payments_app/notify.py
def send_apology_emails(batch_id: str, subject: str, body_template: str) -> int:
    """Sends one email per refunded customer to Mailpit (SMTP localhost:1025).
    Returns the count sent."""
```

**Treasurer approval check:** Switch's addressing rule is the main gate. `execute_refund_batch` also checks `approved_by` as a second safety layer.

---

## 9. Suggested repo layout

```
blast-radius/
├── payments_app/        # Person B: fake payment service, bug, logic
├── seed/                # Person B: seed script with a fixed random seed
├── agents/
│   ├── investigator/    # Person A: Switch wrapper around blast.py
│   └── treasurer/       # Person A: Switch wrapper around refunds.py + notify.py
├── switch/
│   ├── template.yaml    # Person A: rooms + Claude Code agents
│   └── room-instructions/
├── scripts/             # register, scenario, verify
├── docs/                # architecture diagram, reference transcript
├── docker-compose.yml   # payment app + Mailpit
├── Makefile
└── README.md
```

---

## 10. Schedule

- **Nov 4 (today):**
  - A: Switch working, plus the tests in section 11.
  - B: fake payment app, bug and seed data.
- **Nov 5:**
  - A: all four agents talking in rooms, with the Python agents calling B's functions.
  - B: refunds, emails, Makefile.
- **Nov 6:** run the full story end to end at least 5 times, tighten room instructions, clean-machine README test.
- **Nov 7:** record the video (several takes), edit it, finish the README, **submit by evening.**

---

## 11. Go/no-go tests for today (Person A)

| Test | If it fails |
|---|---|
| Quickstart works and two Claude Code agents run; watch RAM | Run the Switch server on a cloud machine (Console supports a remote host) and keep only the agents local |
| A plain Python agent registers, receives a message addressed to it, and replies | Make Investigator/Treasurer Claude Code agents that must run fixed scripts (numbers stay deterministic) |
| Treasurer set to "people only"; a Claude Code agent tells it to act and gets a visible refusal | Enforce the rule in the Treasurer's own code |
| A Claude Code agent creates a room and invites another agent | Predefine the rooms in the template |

Each test has a fallback that keeps the idea alive. The only real blocker is the laptop.

---

## 12. Demo video script (under 3 minutes)

- **0:00–0:07:** open on the ending. The Mailpit inbox fills with "you were double-charged, we've already refunded you" emails while a counter ticks up. Caption: *"None of these customers complained."*
- **0:07–0:15:** *"One did. Here's what happened in the next N minutes."* Use the real elapsed time.
- **0:15–2:20:** the story from section 4.
  - Speed up the parts where agents are thinking; keep the human approvals at real speed.
  - Label each Switch feature on screen: room created by an agent, handoff by message, people-only refund agent, **Switch refuses an agent**, human approves, room document written.
- **2:20–2:50:** the postmortem, then one summary frame: 3 departments · 4 agents · 1 human · 1 trail.
- **2:50–3:00:** `git clone … && make demo`.

---

## 13. Known risks and open questions

- **Laptop RAM (8 GB)** with Docker, Mattermost and two Claude Code sessions may be too slow. Test today.
- Not yet checked:
  - the exact template YAML fields for roles and custom addressing rules (check the Templates docs page or ask the Switch expert agent in Console);
  - whether a second human could join through Discord for a two-person demo. Optional, not part of the baseline.
- The Switch protocol is still changing: pin the Console version.
- AI agents behave a little differently each run: seed the scenario, write tight room instructions, record several takes.
- Freshness: Switch's docs include an overnight incident scenario and a payments-team tutorial. Our new part is the customer and finance half, so protect it.

---

## 14. Notes for Claude (if you're the assistant reading this)

- The user is Person A or Person B; ask which if they haven't said.
- Keep explanations simple and practical; the team prefers plain language.
- Respect the design decisions in section 5 unless the team asks to change them.
- Check Switch details against the docs links in section 2 rather than guessing; Switch changes often.
