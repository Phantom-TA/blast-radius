# Setting up Switch for Blast Radius

There are two ways to run this:

- **One person on Mattermost.** Nothing to set up beyond Switch itself, because Mattermost comes with Switch's local server. You play both people. This is the path for trying the project yourself: follow steps 1 to 9.
- **Two people on Discord.** A real Support lead and a real Finance lead work in one Discord server. This is how we recorded the demo. Do steps 1 to 5, then [Two people on Discord](#two-people-on-discord).

Either way, Switch runs on one computer. On a local server only one person can sign in to Switch, so the second person only needs Discord.

`make <command>` and `python run.py <command>` do the same thing.

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
3. **Link your Mattermost account.** On the **Home** page, under **Messaging apps**, select **Link** for **Local Mattermost** and pick your handle. Until you do, the Treasurer refuses you, because Switch can't tell you are its owner.
4. Open Mattermost from Console. You'll use it to watch and to approve.

## 3. Get the project

```bash
git clone https://github.com/Phantom-TA/blast-radius.git
cd blast-radius
python3 -m venv .venv
source .venv/bin/activate
pip install -r payments_app/requirements.txt -r agents/requirements.txt
```

On Windows use `python -m venv .venv` and `.venv\Scripts\activate`.

## 4. Start the payment app and the inbox

```bash
make up
```

The payment service runs on port 8400 and the Mailpit inbox on http://localhost:8025.

## 5. Register the Python agents

```bash
make register
```

**Docker and Mattermost must be running when you do this.** Switch gives each agent its own Mattermost account at registration; if Mattermost is down then, the agents later post under your name or not at all (see "If something goes wrong").

This runs `scripts/register_agents.py`. It:

- signs in to Switch's Gateway API as the agents' owner. On the server Console runs it uses Console's own admin login, so it asks nothing. On any other server it asks for your Switch email and password;
- creates a registration key (the local server has no Gateway web page with an API Keys button, so the script asks the API) and saves it in `agents/.secrets/`;
- registers **investigator**, **treasurer** and **customer-sim**, and saves each one's API key in `agents/.secrets/`. Running it again skips agents that are already registered;
- sets who may instruct each one:

| Agent | Who can instruct it | Why |
|---|---|---|
| investigator | anyone in its rooms | Support and both people can ask it |
| treasurer | **only you**, its owner | You are the Finance lead, and money moves only on your word |
| customer-sim | only you | It just posts the complaint |

**No addressing setting to change by hand.** To see it, open the Treasurer's page in Console (**Your Agents**, then **treasurer**): **Who can talk to your agent** shows it. Leave it as it is.

## 6. Create the rooms and the Claude Code agents

```bash
make rooms
```

This runs `switch/import_template.py`, which imports `switch/template.yaml` through the Gateway API. Switch first checks the whole template, then creates:

- **support** and **fixer**, two Claude Code agents that run on this computer, open to anyone in their rooms. Fixer works in `demo-workspace/payments-service`; the script creates that folder if it's missing, and the next step fills it;
- **#support** (Support, Fixer, customer-sim and you) and **#finance-approvals** (Treasurer, Support and you), in a room group called **Blast Radius**, linked to each other;
- a kickoff message. Support says hello in #support. It may take a minute to start.

To do the same by hand in Console: open **Templates**, paste the contents of `switch/template.yaml`, set **Fixer's folder** to the full path of `demo-workspace/payments-service` in your clone, **Support lead's chat username** to your own username, and **Messaging app** to **Local Mattermost**.

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

You are both the Support lead and the Finance lead here:

1. Watch #support. Support answers the customer and creates **#blast-ORD-100953**, with you, the Investigator, the Fixer and the Treasurer in it.
2. The Investigator posts the numbers: **313 customers, 312 who never complained, $21,607.00**.
3. The Fixer posts its fix and test result. Reply: `@support Fix approved.`
4. Support writes the apology as the room document **apology-email** and asks you to approve it. Read it, then reply: `@support Wording approved.`
5. Support asks you to prepare the refunds. In #blast-ORD-100953, send: `@treasurer prepare refunds`
6. The Treasurer posts the batch in **#finance-approvals**. Support tries to execute it, and **Switch refuses**: the Treasurer takes instructions from you alone.
7. In #finance-approvals, reply with the line the Treasurer gave you: `@treasurer execute rb-...`
8. The Treasurer refunds 313 customers and sends 313 apology emails. Watch http://localhost:8025 fill up.
9. Support writes the **postmortem** room document and tells the customer in #support.

## 9. Check the result

```bash
make verify
```

All four lines should say PASS.

## Run it again

```bash
make reset
```

This also archives the old blast room (its history and documents are kept), because the next run needs that name again. Then type `!reset-all-agents` in #support, so Support and Fixer forget the last run, and run `make scenario`.

## Two people on Discord

| Person | Plays | Needs |
|---|---|---|
| The one running Switch | **Finance lead**, the Treasurer's owner | Everything in steps 1 to 5, plus a linked Discord account |
| The other person | **Support lead** | Only a Discord account, on any computer |

The Support lead has no Switch account. That's why Support, Fixer and the Investigator are open to anyone, and why Switch can tell them apart from the Treasurer's owner.

**Use a private Discord server.** Anyone in it can give instructions to the open agents, and the Fixer can run commands on the Switch computer.

### D1. Create the Discord bot

1. In a new or private Discord server, invite the Support lead.
2. In the [Discord Developer Portal](https://discord.com/developers/applications), select **New Application**. On the **Bot** tab, copy the token. Paste it only into Switch Console: never put it in this repo or send it in a chat.
3. Under **Privileged Gateway Intents**, turn on **Server Members Intent** and **Message Content Intent**, then **Save Changes**. Without Message Content, agents receive empty messages.
4. Under **OAuth2 > URL Generator**, select the scopes `bot` and `applications.commands`, and these permissions: View Channels, Send Messages, Send Messages in Threads, Manage Webhooks, Manage Channels, Manage Roles, Read Message History, Attach Files, Add Reactions. Open the generated link and add the bot to your server.
5. In Discord, turn on **Developer Mode** (User Settings > Advanced), then right-click the server icon and select **Copy Server ID**.

### D2. Connect it to Switch

1. In Switch Console, on the server's **Home** page, under **Messaging apps**, select **Connect**, then **Discord**.
2. Name the connection **Discord**, paste the **Bot Token**, and paste the server ID as **Guild Id**. Leave **Agent name autocomplete** selected. Select **Connect**.
3. **Link your Discord account**: search for yourself and select **This is me**. Don't skip this, or the Treasurer will refuse you too.

### D3. Create the rooms on Discord

Get the Support lead's Discord **username**, not their display name (it's under their name in Discord's User Settings). Then:

```bash
python switch/import_template.py --support-lead <their username>
```

When Discord is connected, this uses it instead of Mattermost. **#support** and **#finance-approvals** appear as channels, visible to everyone in the Discord server.

If you already ran this project on Mattermost on this server, clear that first, because the agents and rooms already exist:

1. In Console, delete the **support** and **fixer** agents.
2. Run `python switch/archive_rooms.py support` and `python switch/archive_rooms.py finance-approvals`.

### D4. Get ready

In a second terminal, leave this running:

```bash
make agents
```

Then, in the first terminal:

```bash
make prepare
```

This is `make scenario` without the complaint, because a real person posts it. The Support lead should also post one message in #support now, like `hello`. Switch only turns `@name` into a real Discord mention for people who have posted since the connection started.

### D5. Run the story

| # | Who | Where | What |
|---|---|---|---|
| 1 | Support lead | #support | `Customer emailed: charged twice for order ORD-100953. @support can you check?` |
| 2 | Support agent | #support | Replies, then creates a new channel, **#blast-ord-100953** (Discord lowercases channel names) |
| 3 | Investigator | blast channel | Posts **313 customers, 312 who never complained, $21,607.00** |
| 4 | Fixer | blast channel | Fixes the bug and posts the result |
| 5 | Support lead | blast channel | `@support Fix approved.` |
| 6 | Support agent | blast channel | Writes the room document **apology-email** and asks for approval |
| 7 | Support lead | blast channel | `@support Wording approved.` |
| 8 | Support agent | blast channel | Asks the Finance lead to prepare the refunds |
| 9 | Finance lead | blast channel | `@treasurer prepare refunds` |
| 10 | Treasurer | #finance-approvals | Posts the batch and its id |
| 11 | Support agent | blast channel | Tries to execute the batch, and **Switch refuses it** |
| 12 | Support lead | #finance-approvals | `@treasurer execute rb-...`, and **Switch refuses them too** |
| 13 | Finance lead | #finance-approvals | `@treasurer execute rb-...`, and the refunds go out |
| 14 | Treasurer | both | Reports 313 refunds and 313 emails. Mailpit fills up at http://localhost:8025 |
| 15 | Support agent | blast channel | Writes the **postmortem** room document and tells #support |

Then run `make verify`.

### D6. Run it again

If the run was a good one, save it first:

```bash
python switch/export_transcript.py
```

Archiving leaves the Discord channel in place, so for a clean sidebar, delete the room and its channel before you reset. This can't be undone: the room's history and documents go too.

```bash
python switch/archive_rooms.py --delete
make reset
```

Type `!reset-all-agents` in #support, then run `make prepare`.

If Claude Code's permission prompts interrupt a recording, turn on **Bypass permissions** for the **fixer** agent only, in Console. It only works in `demo-workspace/`.

## If something goes wrong

- **The Investigator, Treasurer or customer's messages show under your name in Mattermost, or don't show at all.** Mattermost wasn't running when they were registered, so they have no Mattermost account in the channels. In Switch Console open **Admin**, select **Restart** (Switch creates the missing accounts when it starts), wait for **Running**, then run `python switch/rejoin_agents.py` to put each agent's account into its channels.
- **Switch can't reach Mattermost after a restart, and the server log says `Mattermost post /users/login failed`.** Usually a second Mattermost is running, for example one started by hand on port 8065, and Switch's connection still holds that one's login. Use only Console's own Mattermost: stop the other one (`docker ps` shows it), then on **Home → Messaging apps** open the Mattermost row's **⋮** menu and choose **Disconnect app…**, and on **Admin** turn **Mattermost** off and on. Console makes a fresh connection; link your account again, then run `python switch/import_template.py` to recreate the rooms.
- **The Treasurer refuses you, its owner.** Your chat account isn't linked to your Switch user. See step 2, or D2 on Discord.
- **"Switch answered 500" when a room is created, or rooms don't show up in Mattermost.** Mattermost isn't running, usually because Docker Desktop stopped. Start Docker, then check that **Also run Mattermost** is on, on the server's page in Console.
- **An agent says "Starting a session to handle this — one moment." and nothing follows.** Look in Switch Console: Claude Code may be waiting for you to allow an action.
- **"You're not permitted to direct messages to me in this room"** from the Treasurer. That's correct whenever an agent asks it for something. Only its owner can.
- **"I only take instructions from my owner, and this chat account isn't linked"** from the Treasurer. That's correct for the Support lead. For the Finance lead, link your Discord account.
- **`make register` says `/auth/login failed with 401`.** You're on a server Console doesn't run, and the email or password doesn't belong to the account that should own the agents.
- **Agents get empty messages on Discord.** Turn on **Message Content Intent** (D1), then restart the connection.
- **Discord's slash commands don't appear.** The bot was invited without `applications.commands`. Re-invite it with both scopes, then restart the connection.
- **A channel in Discord isn't a room yet.** Post a message in it. Inviting the bot isn't enough.
- **An `@name` shows as plain text on Discord.** That person hasn't posted since the connection started. They should post once.
- **Rooms were created on the wrong app.** `import_template.py` prefers Discord when it's connected. To choose, add `--bridge "<connection name>"`.

## Where Switch differs from what we expected

We checked every API path, field and template setting against Switch's documentation (the `docs/` folder of [sandbox-quantum/switch](https://github.com/sandbox-quantum/switch), as of 4 Nov 2026) and against the server we ran, switch-core 0.31.0. Where they disagreed with our planning notes, the docs won:

| We expected | What Switch does | What we did |
|---|---|---|
| Console runs the server in Docker | The local server runs without Docker. Only Mattermost runs in Docker beside it | Docker is needed for Mattermost and our payment app, not for Switch |
| Set addressing with `POST /agents/{id}/ops/update_agent_detail` | An agent can't change its own policy (403). The owner sets it from the Gateway | `register_agents.py` calls `PUT /gateway/agents/{id}/addressing-policy` as the owner |
| Make the registration key on the Gateway's API Keys page | The local server has no Gateway web page | `POST /gateway/api-keys` as the owner |
| A teammate on chat needs a Switch account | On "Anyone", clearing the policy admits people with no Switch account or linked chat account. Any owner-only rule refuses them, with its own message | Support, Fixer and the Investigator are open to anyone, and the Treasurer is owner only |
| A message says who the agent's owner is | `sender_role` is the sender's role in the workspace, not whether they own this agent. `get_my_context` lists the owner's usernames on each messaging app | The Treasurer's own check compares the sender with those usernames, and refuses if it can't look them up |
| Register with `POST /agents` | The docs prefer `POST /agents/register-known` for known agent types. `POST /agents`, with a full integration profile, is the route for a custom agent | We use `POST /agents` |
| Use the WebSocket; SSE is deprecated | The protocol page still describes SSE with a heartbeat every 2 s. The changelog and switch-core 0.31.0 run the connection over `GET /agents/{id}/connection/ws`, where the server sends `ping` and the client answers `{"type": "pong", "cursor": n}`. SSE is now the fallback | WebSocket, answering every ping, pinned to 0.31.0 |
| Template fields as in the examples | Templates are `version: 2`, with `resources:` keyed by name. Agent addressing in a template is `owner`, `owner-agents`, `anyone` or `anyone_in` | `switch/template.yaml` is version 2. The Treasurer isn't in the template; `register_agents.py` sets it |
| Rooms appear in Mattermost | Mattermost isn't the local server's default messaging app. A room created without naming it is Switch-only and invisible in chat | The template names the bridge, and Support is told to use the bridge #support is on |
| — | An agent's fields in a template can't use a bridge or room param, and importing through the API doesn't pick the default bridge | Support reads the bridge from #support with `get_room_detail`; `import_template.py` passes the bridge. A plain string param, like the Support lead's name, does work |
| — | `connect_to_room`, `post_message` and document reads need an open connection (`X-Switch-Connection-Id`). `POST /agents/{id}/message` doesn't | The agents call operations only while their socket is open. `post_complaint.py` uses `/message` |
| A message says whether a person or an agent sent it (`sender_kind`) | `sender_kind` is only set, to `platform`, on Switch's own messages. A person a Switch user has claimed is recognised by `sender_role` (`owner`, `admin` or `member`), which is empty for agents. And a message's `sender` id isn't a participant id, so it can't be looked up in the room's participant list | The Treasurer treats a message as a person's only when it has a `sender_role` |
| — | Every agent posts a short greeting when it joins a room | Nothing; expect those lines in each new room |
| Reading room documents from Python may be hard | It works: `connect_to_room` lists the room's documents, and `load_internal_documents` returns their text | The Treasurer reads "apology-email" from the room. `agents/treasurer/apology_template.md` is used only if that document is missing |
| A Discord user can be targeted like anyone else | `send_targeted_message` refuses a name that isn't a room participant, and Discord lets people post in a public channel without being one | `send` falls back to naming them in a plain post |
| Markdown works everywhere | Discord shows Markdown tables as raw pipe characters | The Investigator posts a list |
| Archiving a room clears the way | On Discord the channel stays, and a new room makes a second channel with the same name | `archive_rooms.py --delete` removes the room and its channel |

The switch-docs MCP server wasn't connected when we built this, so we read the same documentation from the Switch repository, plus the server's own `get_template_guide` operation and its source.
