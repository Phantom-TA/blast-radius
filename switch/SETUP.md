# Setting up Switch for Blast Radius

Follow these steps in order on one computer. You play every human part yourself: Switch's local server allows one signed-in person.

## Versions we used

| | Version |
|---|---|
| Switch Console | **0.40.1** (macOS, Apple silicon) |
| Switch server (switch-core) | **0.31.0**, installed by Switch Console |
| Claude Code | 2.1.318 |
| Docker Desktop | Docker Engine 29.9.2, Compose v5.6.1 |
| Python | 3.11 |
| macOS | 26.5.1 |

**Use Switch Console 0.40.1.** Switch's agent connection changes between releases, and our two Python agents speak the version this server runs. Download it from [the Switch releases page](https://github.com/sandbox-quantum/switch/releases) (`arm64` for Apple silicon, `x64` for Intel).

## 1. Install the tools

- **Docker Desktop.** Open it and wait until it says the engine is running. Switch's built-in chat (Mattermost) and our payment app both run in Docker. **Start Docker before Switch Console**, and keep it running: if Docker stops, Mattermost stops and no room can be created.
- **Claude Code**, signed in: run `claude` once and log in.
- **Python 3.11 or newer** and **git**.
- **Switch Console 0.40.1.**

## 2. Start the Switch server

1. Open Switch Console and add a server: choose **Run a server on this computer**. Leave **Also run Mattermost** on. Console creates an admin account and signs you in by itself; there is nothing to copy. The first start downloads Mattermost, which takes a few minutes.
2. Finish the **Setting up Switch** checklist in the sidebar. It must find Claude Code as an agent provider, and this computer must be able to run agents.
3. **Link your Mattermost account.** On the **Home** page, under **Messaging apps**, select **Link** for **Local Mattermost** and pick your handle. Until you do, every agent ignores you, because Switch can't tell who you are.
4. Open Mattermost from Console. You'll use it to watch and to approve.

## 3. Get the project

```bash
git clone https://github.com/Phantom-TA/blast-radius.git
cd blast-radius
python3 -m venv .venv
source .venv/bin/activate
pip install -r payments_app/requirements.txt -r agents/requirements.txt
```

## 4. Start the payment app and the inbox

```bash
make up
```

The payment service runs on port 8400 and the Mailpit inbox on http://localhost:8025.

## 5. Register the Python agents

```bash
make register
```

This runs `scripts/register_agents.py`. It:

- signs in to Switch's Gateway API as the agents' owner. On the server Console runs it uses Console's own admin login, so it asks nothing. On any other server it asks for your Switch email and password;
- creates a registration key (the local server has no Gateway web page with an API Keys button, so the script asks the API) and saves it in `agents/.secrets/`;
- registers **investigator**, **treasurer** and **customer-sim**, and saves each one's API key in `agents/.secrets/`. Running it again skips agents that are already registered;
- sets who may instruct each one:

| Agent | Who can instruct it | Why |
|---|---|---|
| investigator | you, and your own agents | Support hands it work |
| treasurer | **people only**: any linked person, never an agent | Money moves only on a person's word |
| customer-sim | only you | It just posts the complaint |

**No addressing setting to change by hand.** To see it, open the Treasurer's page in Console (**Your Agents**, then **treasurer**): **Who can talk to your agent** shows a custom rule. Leave it as it is.

## 6. Create the rooms and the Claude Code agents

```bash
python switch/import_template.py
```

This imports `switch/template.yaml` through the Gateway API. Switch first checks the whole template, then creates:

- **support** and **fixer**, two Claude Code agents that run on this computer. Fixer works in `demo-workspace/payments-service`; the script creates that folder if it's missing, and the next step fills it;
- **#support** (Support, customer-sim and you) and **#finance-approvals** (Treasurer, Support and you), in a room group called **Blast Radius**, linked to each other;
- a kickoff message. Support says hello in #support. It may take a minute to start.

To do the same by hand in Console: open **Templates**, paste the contents of `switch/template.yaml`, set **Fixer's folder** to the full path of `demo-workspace/payments-service` in your clone, and **Messaging app** to **Local Mattermost**.

## 7. Start the Python agents

In a second terminal (`source .venv/bin/activate` first), and leave it running:

```bash
make agents
```

## 8. Run the story

```bash
make scenario
```

This resets the database to the seed, recreates the Fixer's folder with the buggy payment service, empties the inbox, and posts the customer's complaint in #support as customer-sim.

What you do, as the one person in the story:

1. Watch #support. Support answers the customer and creates **#blast-ORD-100953**, with you, the Investigator, the Fixer and the Treasurer in it.
2. The Investigator posts the numbers: **313 customers, 312 who never complained, $21,607.00**.
3. The Fixer posts its fix and test result. Reply in its thread: `Approved.`
4. Support writes the apology as the room document **apology-email** and asks you to approve it. Read it, then reply: `Approved.`
5. Support hands the refunds to the Treasurer, and **Switch refuses it**: the Treasurer takes instructions from people only. Support then asks you.
6. In #blast-ORD-100953, send: `@treasurer prepare refunds`
7. In **#finance-approvals**, the Treasurer posts the batch and mentions you. Reply in that thread with the line it gives you: `@treasurer execute rb-...`
8. The Treasurer refunds 313 customers and sends 313 apology emails. Watch http://localhost:8025 fill up.
9. Support writes the **postmortem** room document and tells the customer in #support.

## 9. Check the result

```bash
make verify
```

## Run it again

```bash
make reset
python switch/archive_rooms.py
```

Then type `!reset-all-agents` in #support, so Support and Fixer forget the last run. `archive_rooms.py` archives the old blast room (its history and documents are kept), because the next run needs that name again. Then run `make scenario`.

## If something goes wrong

- **An agent ignores you.** Your Mattermost account isn't linked to your Switch user. See step 2.
- **"Switch answered 500" when a room is created, or rooms don't show up in Mattermost.** Mattermost isn't running, usually because Docker Desktop stopped. Start Docker, then check that **Also run Mattermost** is on, on the server's page in Console.
- **An agent says "Starting a session to handle this — one moment." and nothing follows.** Look in Switch Console: Claude Code may be waiting for you to allow an action.
- **"You're not permitted to direct messages to me in this room"** from the Treasurer. That's correct whenever an agent asks it for something. Only a person can.
- **`make register` says `/auth/login failed with 401`.** You're on a server Console doesn't run, and the email or password doesn't belong to the account that should own the agents.

## Where Switch differs from what we expected

We checked every API path, field and template setting against Switch's documentation (the `docs/` folder of [sandbox-quantum/switch](https://github.com/sandbox-quantum/switch), as of 4 Nov 2026) and against the server we ran, switch-core 0.31.0. Where they disagreed with our planning notes, the docs won:

| We expected | What Switch does | What we did |
|---|---|---|
| Console runs the server in Docker | The local server runs without Docker. Only Mattermost runs in Docker beside it | Docker is needed for Mattermost and our payment app, not for Switch |
| Set addressing with `POST /agents/{id}/ops/update_agent_detail` | An agent can't change its own policy (403). The owner sets it from the Gateway | `register_agents.py` calls `PUT /gateway/agents/{id}/addressing-policy` as the owner |
| Make the registration key on the Gateway's API Keys page | The local server has no Gateway web page | `POST /gateway/api-keys` as the owner |
| "People only" is an option | It is a custom rule: people `*`, agents none. Console only offers owner-only, owner and owner's agents, or anyone | `register_agents.py` writes that rule for the Treasurer |
| Register with `POST /agents` | The docs prefer `POST /agents/register-known` for known agent types. `POST /agents`, with a full integration profile, is the route for a custom agent | We use `POST /agents` |
| Use the WebSocket; SSE is deprecated | The protocol page still describes SSE with a heartbeat every 2 s. The changelog and switch-core 0.31.0 run the connection over `GET /agents/{id}/connection/ws`, where the server sends `ping` and the client answers `{"type": "pong", "cursor": n}`. SSE is now the fallback | WebSocket, answering every ping, pinned to 0.31.0 |
| Template fields as in the examples | Templates are `version: 2`, with `resources:` keyed by name. Agent addressing in a template is `owner`, `owner-agents`, `anyone` or `anyone_in` | `switch/template.yaml` is version 2. The Treasurer isn't in the template, so its custom rule doesn't need to be |
| Rooms appear in Mattermost | Mattermost isn't the local server's default messaging app. A room created without naming it is Switch-only and invisible in chat | The template names the bridge, and Support is told to pass `bridge_id` |
| — | An agent's fields in a template can't use a bridge or room param, and importing through the API doesn't pick the default bridge | Support's instructions don't use `{bridge}`; `import_template.py` passes the bridge |
| — | `connect_to_room`, `post_message` and document reads need an open connection (`X-Switch-Connection-Id`). `POST /agents/{id}/message` doesn't | The agents call operations only while their socket is open. `post_complaint.py` uses `/message` |
| A message says whether a person or an agent sent it (`sender_kind`) | `sender_kind` is only set, to `platform`, on Switch's own messages. A person a Switch user has claimed is recognised by `sender_role` (`owner`, `admin` or `member`), which is empty for agents. And a message's `sender` id isn't a participant id, so it can't be looked up in the room's participant list | The Treasurer's own check treats a message as a person's only when it has a `sender_role` |
| — | Every agent posts a short greeting when it joins a room | Nothing; expect those lines in each new room |
| Reading room documents from Python may be hard | It works: `connect_to_room` lists the room's documents, and `load_internal_documents` returns their text | The Treasurer reads "apology-email" from the room. `agents/treasurer/apology_template.md` is used only if that document is missing |

The switch-docs MCP server wasn't connected when we built this, so we read the same documentation from the Switch repository, plus the server's own `get_template_guide` operation and its source.
