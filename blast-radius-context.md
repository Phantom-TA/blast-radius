# Blast Radius: Full Project Context (Flip the Switch Hackathon)

> **For Claude Code:** read this whole file before doing anything in this repo. It holds every decision the team has made. If something here conflicts with the current Switch docs, the docs win; tell the user what differed.
>
> **For people:** keep this file in the repo root on `main`. If you start a new Claude chat, upload it and say which person you are (A or B).
>
> Version 2. Last updated: Nov 5, 2026, ~8 PM IST. Team: Tushar Agrawal and one teammate (2 people). This file records decisions only. It does not track build progress, so check git for what's actually done. Facts were corrected on Nov 5 against the Switch 0.31.0 source and what was built.

---

## 0. Quick summary

- **Project:** Blast Radius, for Track 01 (Best Business Workflow).
- **One line:** one customer complains about a double charge; AI agents in Switch find every customer the same bug hit, fix the bug, refund everyone and apologize before they complain. Humans approve the code fix and the money.
- **Chat platform:** Discord, connected to a Switch server running on one laptop. The bundled Mattermost stays available so judges can reproduce without Discord.
- **Agents:**
  - 2 Claude Code agents: Support and Fixer.
  - 2 plain-Python agents (no LLM): Investigator and Treasurer.
- **Humans:**
  - Person B is the Support lead: forwards the complaint, approves the fix and the apology.
  - Person A is the Finance lead: the only one who can trigger refunds.
- **The key Switch moment:** the Treasurer is set to "Only me". When the Support agent or the Support lead tells it to refund, Switch refuses visibly. Only the Finance lead can make it act.
- **Deadline:** Nov 7, 11:59 PM IST. Target: submit by the evening of Nov 7.

---

## 1. The hackathon

- **Name:** Flip the Switch Hackathon, hosted by WeMakeDevs and DevTools Academy, powered by Switch (made by SandboxAQ). Online, Nov 4 12:01 AM IST to Nov 7 11:59 PM IST. Teams of 1 to 4.
- **Track 01, Best Business Workflow ($2,000):** a practical workflow where people and AI agents get work done.
- **Rules:**
  - A workflow in team chat where at least one AI agent and one person finish a real task together, through Switch.
  - Switch is mandatory and must be central. The README must show how Switch is used.
  - AI coding tools are allowed, but we must understand our code and be able to explain it.
  - Existing agents and libraries are fine; the Switch setup and the workflow must be built during the hackathon.
- **Judging weights:**
  - **30% Use of Switch:** is Switch central, and would the project stop working without it?
  - **25% Technical execution:** does it run, and could someone clone the repo and reproduce it?
  - **25% Creativity and impact:** is it a fresh idea that solves a problem a real team has?
  - **20% Presentation:** do the demo video and README make clear how Switch is used?
- **Judging process:** WeMakeDevs reviews every submission and builds a shortlist. Finalists are judged by Switch, DevTools Academy and WeMakeDevs. So we must survive a fast skim (first 15 seconds of video + README), then impress the people who built Switch.
- **Submission form:**
  - **GitHub repository:** must be public, with a README that explains how to set it up.
  - **Demo video:** under 3 minutes, on YouTube or Loom, public or unlisted. For Tracks 1 and 2 it must **show the agent working in a real chat with your teammates.**
  - **Live demo link:** optional; leave it blank.
  - **"How did you use Switch?":** which agents, which platforms, what real work, how teammates work with it. Draft in section 12.
  - **"What did you like about Switch, and what would you improve?":** draft in section 12.
- **Optional extra entries with the same project:** Best Blog (AirPods 5), #HowISwitch social post (top 5 get a Logitech keyboard), Code with Wispr ($500, build by voice).
- **Links:**
  - Hackathon: https://www.wemakedevs.org/hackathons/switch
  - Resources: https://www.wemakedevs.org/hackathons/switch/resources
  - Help: WeMakeDevs Discord https://discord.gg/E2rWw2Yhsm

---

## 2. Switch facts we rely on (checked against the docs on Nov 4)

### Basics
- An open-source layer that puts AI agents (Claude Code, Codex, OpenCode, or custom agents) into chat apps (Slack, Teams, Discord, Telegram, Mattermost). Each channel becomes a **room** with shared history and context. Agents appear under their own names.
- **Switch Console** is the desktop app. It runs your agents and can start a local Switch server.
  - The local server itself runs without Docker. Mattermost and our payment app run in Docker, so we still need it. On Windows, Docker Desktop or Rancher Desktop; no WSL needed.
  - The first start downloads a few GB.
  - Windows and Linux Console builds are "early access"; macOS is fully supported.
- **Who can reach a local server:** only the person running it can sign in to the server itself (the Gateway). Colleagues can still work with the agents: connect Slack, Discord or Telegram, and Switch connects *out* to the platform, so anyone in that Discord server can address the agents in a channel. No public address is needed. (Microsoft Teams is the exception: it needs a server reachable from the internet.)
- The agents only answer while the laptop running Switch Console is on.

### Room building blocks
- **Room instructions:** a briefing every agent reads when it joins. An agent already in the room keeps the instructions it got until it reconnects.
- **Roles:** named jobs (e.g. `@reviewer`) with their own instructions. Addressing the role reaches whoever holds it. A role can be shared or exclusive, and an agent holds one at a time. No spaces in role names. `!roles` lists them.
- **References:** pointers to outside material (GitHub, Jira, Confluence, Google Drive), with instructions saying when to use them.
- **Room documents:** text stored in the room, written by agents. Max 1 MB, and names must be unique in the room. An agent can only edit documents it wrote itself.
- **Room links:** connect rooms, so agents know which other rooms matter and why.
- **Agents can build the structure themselves:** create rooms, write instructions, define and take roles, link rooms, attach references, invite agents and people.
- **Handoffs happen by targeted message or @mention.** There is NO separate task system, so don't build around "tasks".
- **Templates:** Console can create rooms and agents from a saved YAML setup. Fields seen in Switch's examples:
  - an agent's name, description, addressing, provider and instructions;
  - a room's name, bridge, agents and users;
  - a kickoff message.

  Check the exact format on the Templates docs page.

### Who can make an agent act ("addressing")
- Set in Console under the agent → **General → "Who can talk to your agent"**:
  - **Me and my agents** (default): you and agents you own.
  - **Only me:** only you. Not colleagues, and **not your other agents**.
  - **Anyone:** anyone in the agent's rooms. **They don't need a Switch account or a linked chat account.**
  - **Custom rules:** name people, agents and rooms individually.
- The owner sets these through the Gateway: `PUT /gateway/agents/{id}/addressing-policy`. `policy: null` means Anyone. An agent calling `update_agent_detail` on itself gets a 403. Templates spell the options `owner`, `owner-agents` and `anyone`.
- **When someone not allowed tries, the agent posts a visible refusal.** A change applies from the next message. An agent or a linked person sees "You're not permitted to direct messages to me in this room". An unlinked chat account sees "I only take instructions from my owner, and this chat account isn't linked to a Switch user yet".
- An agent can't change its own policy; only its owner can.
- **Account linking matters:** a chat account not linked to a Switch user matches nobody. Without linking, your own "Only me" agent won't recognize you.
- **Follow-ups:** a reply in an agent's thread can reach it without its name, but follow-ups never let in anyone its rules refuse. `!follow-ups off` turns this off in a room.

### Other agent settings
- **Auto mode** (on by default): Claude Code and Codex use their own automatic review and post a permission request in the room for anything else.
- **Bypass permissions** (off by default): the agent never asks. Only use it for an agent you'd trust alone in its working directory; the Fixer in `demo-workspace/` is a candidate if permission prompts interrupt the demo.
- **Advanced configuration** (model, tools, etc.): applies from the next session. To apply it, stop the session in Console, then address the agent again.

### Connecting Discord (verified steps)
1. In the Discord Developer Portal: **New Application** → **Bot** tab → copy the token.
2. Under Privileged Gateway Intents, turn on **Server Members Intent** and **Message Content Intent**, then **Save**. Without Message Content, agents receive empty messages.
3. Under **OAuth2 → URL Generator**:
   - scopes: `bot` and `applications.commands`;
   - permissions: View Channels, Send Messages, Send Messages in Threads, Manage Webhooks, Manage Channels, Manage Roles, Read Message History, Attach Files, Add Reactions;
   - open the generated link and add the bot to your server.
4. In Discord, turn on Developer Mode, then right-click the server icon → **Copy Server ID**. The connect form calls this "Guild Id".
5. In Switch Console: select the server → **Home** → **Messaging apps** → **Connect** → Discord → paste the bot token and Guild Id → **Connect**.
6. **Link your Discord account ("This is me").** Don't skip this.
7. **Posting a message in a channel is what turns it into a room**; inviting the bot isn't enough. When an agent creates a room in Switch, Switch creates a matching Discord channel.

What to expect in Discord:
- Agents post under their own names and avatars.
- A 👀 reaction marks the message an agent is working on.
- A "Working…" message shows its progress.
- Slash commands reply in a thread.
- If the slash commands don't appear, the bot was invited without `applications.commands`: re-invite it with both scopes, then restart the connection.
- Discord lowercases channel names, so the room `blast-ORD-100953` shows as `#blast-ord-100953`.
- Rooms created as `channel_public` are visible to everyone in the Discord server.
- An `@name` only becomes a real mention once that person has posted since the connection started, or they were picked from the `@` menu.
- Archiving a room keeps its Discord channel, so reruns add a second channel with the same name.
- Don't delete a room between takes. Console 0.40.1 keeps it in the Claude Code agents' session lists, and the Fixer can then no longer post. `make reset` archives instead.
- Discord can't open room documents, so Support pastes the apology when it asks for approval.
- In an agent's instructions `{$creator}` becomes the Switch account's name ("Admin"). The template's `finance_lead` param carries the chat username instead.

### Custom agents (the "agent protocol")
1. Register once: `POST /agents`, using a *registration* API key (`POST /gateway/api-keys` as the owner; the local server has no API Keys page) as the Bearer token.
   - Body: `name` (lowercase, matching `^[a-z0-9][a-z0-9._-]*$`), `description`, `connector_type` (free text), and `integration_profile` = {`connection_model`, `message_exchange` (bool), `pre_invocation_mediation: []`, `post_invocation_mediation: []`, `event_reporting: []`}.
   - Response: `{id, api_key}`. **The key is shown once, so save it.**
   - Don't use `/agents/register-known`.
   - Registering an existing name returns 409. `overwrite: true` issues a new key and invalidates the old one.
2. A new agent answers only its owner and the owner's agents. Change that as its owner with the Gateway call above.
3. Open a WebSocket at `/agents/{id}/connection/ws` with the Bearer API key, a fixed connection id (a UUID you reuse on every reconnect), and the rooms to claim.
   - Read `rooms`, `cursor` and `generation` from the `connection_state` frame.
   - Answer every ping with a pong that carries the cursor.
4. React only to `message` events where `payload.addressed == true`. By default a connection receives every message in its rooms.
5. Operations: `POST /agents/{id}/ops/{operation}` with the header `X-Switch-Connection-Id`; the arguments go unwrapped in the body. List them with `GET /agents/{id}/ops`. Arguments are checked against the function signature, so unexpected keys are rejected.
6. To post without a connection: `POST /agents/{id}/message` with `{room_id, content}`.

More details:
- **Operations include:**
  - rooms: `list_rooms`, `create_room`, `invite_agent_to_room`, `add_users_to_room`, `get_room_detail`
  - messages: `post_message`, `send_targeted_message`, `read_context`
  - documents and references: `create_room_document`, `update_room_document`, `load_internal_documents`, `attach_reference_to_room`
  - roles and links: `define_role`, `assume_role`, `link_rooms`
- An agent inherits exactly its owner's permissions.
- The bridge URL is usually NOT the Gateway URL; `GET /health` (public) tells you if you've found the right one.
- SSE is deprecated, so use the WebSocket. "Connection models" are expected to change, so **pin the Switch Console version** and write it in the README.

### Docs links
- Index: https://docs.switchagents.ai/llms.txt
- Docs inside Claude Code: `claude mcp add switch-docs --transport http https://docs.switchagents.ai/mcp`
- Agent protocol: https://docs.switchagents.ai/switch-rooms/internals/agent-protocol.md
- Identity and access: https://docs.switchagents.ai/switch-rooms/internals/identity-and-access.md
- Agent settings: https://docs.switchagents.ai/switch-rooms/getting-started/agent-settings.md
- Connect Discord: https://docs.switchagents.ai/switch-rooms/deploy/messaging-apps/discord.md
- Choose how to run Switch: https://docs.switchagents.ai/switch-rooms/deploy/index.md
- Payments room tutorial: https://docs.switchagents.ai/switch-rooms/building/payments-room.md
- Templates: https://docs.switchagents.ai/switch-rooms/administer/room-templates.md
- Repo: https://github.com/sandbox-quantum/switch

---

## 3. How we picked the idea

### Rejected ideas
| Idea | Why not |
|---|---|
| Incident response / bug triage → fix → deploy | Switch's own README, landing-page demo and docs already show it. Very crowded. |
| Vendor purchase review across security, legal, finance | Already a scenario in Switch's docs. |
| Follow-the-sun handoff across time zones | Already a scenario in Switch's docs. |
| Agent code reviewed by a different AI, with an audit trail | Narrow, and a weaker demo. |
| **No-Code Workshop** (teammate's idea): a shop owner on Telegram asks for a website; Interviewer, Builder and Inspector agents build and check it in separate rooms; humans approve | See below. |

### Blast Radius vs. No-Code Workshop (final comparison)
| Criterion | Blast Radius | No-Code Workshop |
|---|---|---|
| Use of Switch (30%) | 5 | 4.5 (two chat apps with real people is strong; but handoffs ran through a human "Foreman" and a shared folder) |
| Technical execution (25%) | 4 | 3 (two chat apps + two AI providers; a different website every run; slow builds) |
| Creativity and impact (25%) | 3.5 | 2.5 ("describe it in chat, AI builds a website" is one of the most common AI demos right now) |
| Presentation (20%) | 5 | 4 |
| **Weighted** | **≈ 4.4** | **≈ 3.5** |

**Decision: Blast Radius.** Locked. Switch to No-Code only if the payment app and the two Python agents still aren't working by the evening of Nov 5; it needs far less code.

---

## 4. Blast Radius: the project

### The planted bug
The fake payment service retries a charge after a timeout **without an idempotency key**, so some orders get charged twice.
- **Fix:** send an idempotency key per order, and have the fake payment provider ignore repeated keys.
- **Regression test:** simulate a timeout followed by a retry, and check there is exactly one charge.

### Seeded scenario (identical on every run)
- A fixed random seed and about 2,000 orders.
- **313 affected customers = 1 who complains + 312 who stay silent.** Amounts in USD. Use whatever the seed produces, and keep the README, video and `verify` consistent with it.

### Rooms (Discord channels)
- `#support`: complaints arrive here; the Support lead works here.
- `#blast-<order_id>`: created by the Support agent for each case, and appears live as a new Discord channel.
- `#finance-approvals`: every money action waits here for the Finance lead.

### Agents and their permission settings
| Agent | Built with | "Who can talk to your agent" | Job |
|---|---|---|---|
| support | Claude Code | **Anyone** | Reads the complaint, creates `#blast-<order_id>`, links it to the other two rooms, invites the agents, hands out work by @mention, writes the apology as the room document `apology-email`, writes the postmortem room document at the end |
| fixer | Claude Code, working in `demo-workspace/payments-service` | **Anyone** | Finds and fixes the bug, adds the regression test, runs the tests, commits on branch `fix/double-charge`, posts a short diff summary, waits for approval |
| investigator | Plain Python, agent protocol, no LLM | **Anyone** | Calls `find_affected_customers()` + `summarize()` and posts: affected count, silent count, total overcharge, top 5 rows |
| treasurer | Plain Python, agent protocol, no LLM | **Only me** (`owner_only`), owned by Person A | "prepare refunds" → creates the batch and posts it in `#finance-approvals`. "execute <batch_id>" → executes the refunds, then sends the apology emails. Also refuses in code if the sender isn't its owner, as a second safety layer |
| customer-sim | Plain Python (posting only) | n/a | Used by `scripts/post_complaint.py` so judges can trigger the complaint without a second person |

### Humans in the demo
- **Person B, Support lead,** on their own laptop in Discord: forwards the customer's complaint in `#support`, approves the fix, approves the apology text.
- **Person A, Finance lead,** on the laptop running Switch: the only person the Treasurer obeys.

### The story (what the demo shows)
1. The Support lead posts in `#support`: "Customer emailed: charged twice for order ORD-100953. @support can you check?" (For judges, `make scenario` posts the complaint as customer-sim. For the two-person demo, `make prepare` sets everything up without posting it.)
2. The Support agent replies, creates `#blast-ord-100953` (it appears in the Discord sidebar), and invites investigator, fixer and treasurer.
3. The Investigator posts: 313 affected (312 never complained) and the total overcharge.
4. The Fixer fixes the bug and adds the test. **The Support lead approves.**
5. The Support agent writes the apology. **The Support lead approves the wording.**
6. The Finance lead sends "@treasurer prepare refunds", and the Treasurer posts the batch in `#finance-approvals`. Under "Only me", nobody else can start this.
7. **The Support agent tells the Treasurer to execute, and Switch refuses.** The Support lead tries too, and is also refused.
8. **The Finance lead:** "@treasurer execute <batch_id>". The refunds go out, and 313 apology emails land in Mailpit: the 312 silent customers plus the one who complained.
9. The Support agent writes the postmortem as a room document.

### "Why this breaks without Switch" (README section)
- The complaint, the findings, the code diff and both approvals live in one trail across three rooms.
- Each agent starts from its room's context instead of being re-briefed.
- Switch's addressing decides who may trigger refunds, and refuses everyone else visibly.
- The Support agent builds the structure itself: it creates the case room, links it, and invites the agents.
- Without Switch: four disconnected bots and a human copy-pasting between them.

---

## 5. Design decisions (discuss before changing)

1. Only one AI login is required: **Claude Code.** A Codex/OpenCode reviewer is optional; cut it first if short on time.
2. **An LLM never calculates counts or money.** The Investigator and Treasurer are plain Python.
3. **Never say "incident" and never show server errors.** Lead with customers and money; the engineering part overlaps Switch's own docs.
4. **Cut order if behind:** (1) the optional reviewer, (2) the email blast (show one drafted email instead). Never cut the core: complaint → affected customers found → fix → human-approved refund.
5. The README says plainly that the payment service and data are simulated.
6. Keep the laptop load light: SQLite, one FastAPI process, Mailpit, and at most two Claude Code sessions running at once.
7. **Discord is required** for the demo, because the form demands a real chat with teammates. Mattermost stays as the judge's no-setup path.
8. Treasurer = "Only me"; every other agent = "Anyone".

---

## 6. Making it easy for judges to reproduce

- `run.py` subcommands, with a Makefile that just calls `run.py` (so it works on Windows without make):
  - `up`: start the payment app and Mailpit.
  - `seed`: rebuild the database from the seed.
  - `prepare`: run seed, copy the buggy service into `demo-workspace/payments-service/` and `git init` it there, and empty the Mailpit inbox.
  - `scenario`: `prepare`, then run `post_complaint.py`.
  - `register`: register the Python agents and set their addressing.
  - `rooms`: create the rooms and the Claude Code agents from the template.
  - `agents`: start the Investigator and Treasurer.
  - `verify`: prints PASS/FAIL for each check:
    - the tests pass in `demo-workspace/` (bug fixed + regression test present);
    - refunds are correct, with no double refunds;
    - the expected number of emails is in Mailpit (via its API on port 8025);
    - the postmortem room document exists (Person A adds this check after the merge).
  - `reset`: back to the starting state.
  - `demo`: up + register + rooms + agents + scenario. The agents start first so they can't miss the complaint.
- A Console template for the rooms and the Claude Code agents.
- `switch/SETUP.md`: exact steps, including the Switch Console version used and the Discord setup.
- Commit a reference transcript (exported room history from a good run).
- README troubleshooting:
  - link your chat account;
  - start Docker first;
  - the Windows SmartScreen warning;
  - Discord intents and the bot scopes.
- On Nov 6, someone follows the README on a clean machine.

---

## 7. Team setup and workflow

- **Repo name:** `blast-radius` (public before submission).
- **Repo description:** "One customer complaint → AI agents in Switch find every customer the bug hit, fix the code, and refund them all, with humans approving the money."
- **Person A = the laptop with more RAM** (16 GB is comfortable, 8 GB may be slow; also needs at least 15–20 GB free disk; if RAM is equal, prefer a Mac). Tushar's laptop: 8 GB RAM, i5-12500H. Person A runs Switch, owns the agents, is the Finance lead in the demo, and records the video.
- **Person B** doesn't need Switch installed. They build the payment core and are the Support lead in the demo, on Discord from their own laptop.
- **Branches:** each person branches from `main`:
  - Person A: `feat/switch-agents`
  - Person B: `feat/payments-core`

  Commit small and often, push your own branch, and never merge into `main` directly.
- **File ownership (prevents merge conflicts):**
  - **Person A:** `agents/` (including `agents/requirements.txt`, `agents/.gitignore`, `agents/.secrets/` for keys), `switch/`, `scripts/register_agents.py`, `scripts/post_complaint.py`.
  - **Person B:** `payments_app/`, `seed/`, `scripts/verify.py`, `scripts/scenario.py`, `run.py`, `Makefile`, `docker-compose.yml`, `README.md`, the root `.gitignore`.
  - Need something from the other person's files? Write it in `switch/NEEDS_FROM_B.md` (Person A) or ask in chat. Never edit the other person's files.
- **Before the merge:** Person A tests against fakes (`agents/tests/fakes.py`) that implement the section 8 signatures exactly. No files go in `payments_app/`.
- **Merge order:**
  1. Merge Person B's pull request into `main` first.
  2. Person A merges `main` into their branch, switches from the fakes to the real functions, and runs `python run.py demo`.
  3. Fix what breaks, then merge Person A's pull request.
  4. The other person reviews each pull request.
- Two 10-minute calls a day. Both people must understand all the code.

---

## 8. Interface between A and B (exact signatures)

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
    """Refuses unless the status is 'pending_approval' and approved_by is non-empty.
    Never refunds anyone twice. Returns {"refunded": int, "total": float}."""

# payments_app/notify.py
def send_apology_emails(batch_id: str, subject: str, body_template: str) -> int:
    """Sends one email per refunded customer through Mailpit (SMTP localhost:1025).
    Returns the count sent."""
```

- **Database path:** the `BLAST_DB_PATH` environment variable if set, otherwise `data/payments.db`.
- **Complainer's order id:** in `seed/complainer.json`.
- **Mailpit:** SMTP on port 1025, web inbox on port 8025.
- **The buggy retry code** lives in one small file (e.g. `payments_app/service/charge_client.py`). **Person B must NOT fix the bug.** The Fixer agent fixes it live in the demo.
- **Apology text:** the Treasurer reads it from the room document `apology-email`. If reading room documents from Python is hard, fall back to `agents/treasurer/apology_template.md` and note it.

### Suggested repo layout
```
blast-radius/
├── blast-radius-context.md   # this file
├── payments_app/             # B
├── seed/                     # B
├── agents/                   # A (investigator/, treasurer/, common/switch_client.py, tests/)
├── switch/                   # A (template.yaml, room-instructions/, SETUP.md)
├── scripts/                  # verify.py + scenario.py (B); register_agents.py + post_complaint.py (A)
├── docs/                     # architecture diagram, reference transcript
├── run.py, Makefile, docker-compose.yml, README.md, .gitignore   # B
```

Root `.gitignore` must include: `.venv/`, `__pycache__/`, `data/*.db`, `demo-workspace/`, `.env`, `agents/.secrets/`.

---

## 9. Go/no-go tests (Person A, before building on Switch)

| Test | If it fails |
|---|---|
| Quickstart works and two Claude Code agents run; watch RAM | Run the Switch server on a cloud host (Console supports remote hosts) and keep only the agents local |
| A plain Python agent registers, receives a message addressed to it, and replies | Make Investigator/Treasurer Claude Code agents that must run fixed scripts (numbers stay deterministic) |
| Treasurer set to "Only me": the Support agent and the teammate (on Discord) are refused visibly; Person A is obeyed | Enforce the rule in the Treasurer's code |
| A Claude Code agent creates a room (and it appears as a Discord channel) and invites another agent | Predefine the rooms in the template |
| Teammate on Discord can address the "Anyone" agents | Check that the Discord intents are on and the channel is a room (post a message in it first) |

---

## 10. Schedule

- **Nov 4:** idea locked; go/no-go tests; payment app + seed.
- **Nov 5:** all four agents working in rooms; Discord connected; merge B, then A.
- **Nov 6:** refunds and emails end to end; run the full story 5+ times; tighten room instructions; clean-machine README test.
- **Nov 7:** record the video (several takes, both people on a voice call), edit it, finish the README, make the repo public, **submit by evening.**

---

## 11. Demo video script (under 3 minutes)

- **0:00–0:07:** the Mailpit inbox filling with "you were double-charged, we've already refunded you" emails while a counter ticks up. Caption: *"None of these customers complained."*
- **0:07–0:15:** *"One did. Here's what happened in the next N minutes."* Use the real elapsed time.
- **0:15–2:20:** the story from section 4, in Discord, with two real usernames.
  - Speed up the parts where agents are thinking; keep the human approvals at real speed.
  - Label each Switch feature on screen: room created by an agent (new channel appears), handoff by @mention, "Only me" refund agent, **Switch refuses an agent and a teammate**, the Finance lead approves, room document written.
- **2:20–2:50:** the postmortem, then one summary frame: 3 departments · 4 agents · 2 people · 1 trail.
- **2:50–3:00:** `git clone … && python run.py demo`.
- **How to record:** record Person A's screen (Discord + the Mailpit tab) while both people are on a voice call to time their messages.

---

## 12. Draft answers for the submission form

**Edit these to match what was actually built. Keep only experiences we really had: the Switch team reads them.**

**How did you use Switch in your project?**
> We built Blast Radius: when one customer reports a double charge, a team of agents in Switch finds every other customer the same bug hit, fixes the bug, refunds everyone and apologizes before they complain, with people approving the code and the money.
>
> Agents: two Claude Code agents run through Switch Console. Support reads the complaint, opens a room for the case, hands out the work, drafts the apology and writes the postmortem. Fixer fixes the bug in the payment service and adds a regression test. Two custom Python agents join through the Switch agent protocol with no LLM, so the numbers are identical on every run: Investigator finds the affected customers and the total overcharge, and Treasurer prepares and executes the refunds and sends the emails.
>
> Platform: Discord. Our Switch server runs locally through Switch Console and Discord connects to it, so both of us work in the same channels. The bundled Mattermost lets anyone reproduce the project without setting up Discord.
>
> How we work with it: one of us is the support lead in #support, who passes on the complaint and approves the fix and the apology. The other is the finance lead in #finance-approvals. The Support agent creates a new room for each case, invites the other agents and hands work over by @mention. The Treasurer takes instructions only from the finance lead: when the Support agent or anyone else tells it to send refunds, Switch refuses, and it acts only after the finance lead approves. The complaint, findings, fix and approvals all stay in one trail across three rooms.

**What did you like about Switch, and what would you improve?**
> What worked: agents can set up the work themselves. Our Support agent creates a room for each case, invites the right agents and links the rooms, so the workflow behaves like a team rather than a chain of scripts. Addressing rules gave us a real permission boundary: our refund agent takes instructions only from the finance lead, and the visible refusal made that easy to see. The agent protocol was simple enough that a plain Python script could join a room as a full agent. Connecting Discord to a server on a laptop needed no public address.
>
> What got in the way: an agent only wakes when it is @mentioned, so our story stalled until every agent mentioned whoever asked, and an `@name` counts as addressing that agent even inside backticks. A deleted room stays in a Claude Code agent's session list and stops it posting anywhere, and Discord can't open room documents, so people can't read what they're asked to approve. There is no built-in approval step, so we used addressing rules as our approval gate. A first-class "needs sign-off from this person" step would make human-in-the-loop workflows much clearer. The protocol is still changing (SSE moving to WebSocket, connection models expected to change), so we pinned the Console version.
>
> What we'd want next: an approval step with an audit record, a way to package a whole multi-room workflow (rooms, roles, agents and permissions) as one shareable template, and finer per-person permissions for teammates who join only through a chat app.

---

## 13. Self-assessment against the judging criteria

| Criterion | Expected | Biggest risk |
|---|---|---|
| Use of Switch (30%) | Strong | Falling back to workarounds if the go/no-go tests fail |
| Technical execution (25%) | **Medium (weakest)** | Setup breaks on a judge's machine. Mitigations: run.py, verify, reference transcript, clean-machine test |
| Creativity and impact (25%) | Good | Cutting the refund/email half makes it look like Switch's incident example |
| Presentation (20%) | Strong | A messy recording, or a README that doesn't spell out how Switch is used |

About 4.4 out of 5 if built as planned; about 3 if the refund half is cut or judges can't run it. The real danger is time, not the idea.

---

## 14. Known risks and open questions

- 8 GB RAM with Docker, Mattermost and two Claude Code sessions may be slow.
- The protocol is still changing: pin the Console version.
- AI agents behave a little differently each run: seed everything, write tight room instructions, record several takes.
- Claude Code permission prompts may appear in the room during the demo: approve them, or use Bypass permissions for the Fixer only.

---

## 15. Notes for Claude

- Ask whether the user is Person A or Person B if they haven't said, and stay inside that person's file ownership (section 7).
- Use plain, simple language; the team prefers short, practical answers.
- Respect the design decisions in section 5 unless the team asks to change them.
- Check Switch API details against the docs (switch-docs MCP or the links in section 2) before writing code that depends on them.
- At the end of a work session, explain in simple words what each file does, so the team can explain it to the judges.
