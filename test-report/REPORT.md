# Blast Radius: end-to-end test report

Test of branch `feat/discord-demo` on 6 Nov 2026, with real people on Mattermost and Discord.

A few words used below:

- **Room**: a chat channel that Switch manages. On Discord, each room is a Discord channel.
- **Agent**: a bot that works in the rooms. Support and Fixer are AI agents. Investigator and Treasurer are plain Python programs.
- **Addressing**: Switch's rule for who may give an agent instructions. The Treasurer obeys only its owner (Amiya). Switch refuses everyone else.
- **Batch**: the list of refunds the Treasurer prepares and then executes.
- **PASS**: we have proof it worked. **FAIL**: we have proof it didn't. **NOT RUN**: we couldn't test it, and we say why.

## 1. The short answer

**Almost.** Don't record yet. Fix three things first.

The core story works, on both chat apps:

- The Investigator finds 313 customers and $21,607.00.
- The Fixer fixes the bug.
- Switch visibly refuses the Support agent and the Support lead.
- The Treasurer obeys only the Finance lead.
- 313 refunds and 313 emails go out.
- `make verify` shows 4 PASS on Mattermost and again on Discord.

But on Discord with two people, three problems would show on camera or break a second take:

1. **Support calls the Finance lead "Admin".** It couldn't add Amiya to the case room or ping her until Tushar told it her Discord username (see F2).
2. **Tushar couldn't read the apology he was asked to approve.** Discord doesn't show room documents (see F4).
3. **On a second run, the Fixer fixes the bug but can't post its summary** in the new room (see F5). So retakes don't work as things stand.

## 2. What we tested

| | |
|---|---|
| Branch and commit | `feat/discord-demo` at `cf1915e` |
| Date and time | Fri 6 Nov 2026, 10:08 to 14:25 IST |
| Switch Console | 0.40.1 (switch-core server 0.31.0) |
| Claude Code | 2.1.318 |
| Docker | Engine 29.9.2, Compose v5.6.1 |
| Python | 3.11.16 |
| macOS | 26.5.1 (build 25F80) |
| Mac | Apple M4, 16 GB RAM |

Who took part:

- **Amiya**: Finance lead and owner of the Switch server, on this Mac. Discord username `strider5791`, Mattermost username `user`.
- **Tushar**: Support lead, on another computer, Discord only. Discord username `phantom8817`, shown as "Tushar". No Switch account.
- **The tester**: ran the commands on Amiya's Mac, read the server, database and inbox, and collected the proof. The tester never typed as Amiya or Tushar and never did an agent's work.

What we ran:

- **Part 0**: setup, versions, tests, template check.
- **Part 1**: the full story on Mattermost. Amiya played both people.
- **Part 2**: the full story on Discord. Amiya was the Finance lead and Tushar the Support lead.
- **Part 3**: the room deleted, everything reset, and the story started again on Discord. We stopped after the Investigator's numbers, as the plan allows.

How we got proof: Switch doesn't let the owner's login read room messages (see F1). So the chat proof is screenshots taken by Amiya and Tushar. Everything else comes from read-only checks of Switch, the database, the Fixer's git folder and Mailpit, saved in `logs/`.

### Things we did differently from the plan

Each of these is recorded, with the reason:

- **An old `make agents` was still running** from 5 Nov 13:41, on older code. We stopped it before Part 1, so two copies of each agent wouldn't answer.
- **We archived the leftover Mattermost blast room before the Discord run.** SETUP.md D3 doesn't say to do this. Amiya chose it so Tushar's time wasn't risked. Proof: `logs/30-archive-mattermost-blast-room.txt`.
- **In Part 1, Amiya approved the fix about 10 seconds before the Fixer posted its summary.** Support noticed and said so in the room.
- **Tushar's first Discord complaint was missing "Customer emailed:" at the start.** It made no difference to the agents.
- **Tushar couldn't read the apology document**, so he asked Support in the channel to paste the wording (see F4).
- **Tushar answered Support's question with Amiya's Discord username.** That wasn't in the script. So Amiya was a room member when she typed "prepare refunds", and we did not test whether the Treasurer hears a Finance lead who isn't in the room.
- **On Discord, Amiya executed the refunds before Tushar tried.** So G12 couldn't be tested in the planned order (see the table).
- **The agents were run with `PYTHONUNBUFFERED=1`** so their logs filled in real time. No code was changed.

## 3. Results

### Part 0 and Part 1: one person on Mattermost

| ID | What we checked | Result | What actually happened | Proof |
|---|---|---|---|---|
| M1 | All 173 tests pass | PASS | `173 passed, 1 warning in 1.82s`. The warning is a library deprecation notice. | `logs/02-tests.txt` |
| — | Template check | PASS | "Switch accepts the template." | `logs/03-template-check.txt` |
| M2 | Addressing after registering | PASS | `investigator: addressing set to anyone`, `treasurer: addressing set to owner_only` | `logs/11-register.txt` |
| M3 | Support replies and creates #blast-ORD-100953 | PASS | Complaint at 11:32:54. Room created at 11:33:55. Support answered Victor in #support. | `screenshots/M3-support-replies-and-opens-blast-room.png` |
| M4 | Investigator: 313, 312 silent, $21,607.00, as a list | PASS | Exactly those numbers, and the top 5 as a bullet list, not a table. | `screenshots/M4-investigator-list.png` |
| M5 | Fixer commits a fix and a regression test on `fix/double-charge` | PASS | Commit `968df2f` at 11:36:10 changes `charge_client.py` and adds `test_double_charge.py`. `make verify` confirms the new test fails on the old code. | `logs/15-fixer-commit.txt`, `screenshots/M5-fixer-summary.png` |
| M6 | Support writes `apology-email` and asks for approval | PASS | Written at 11:35:21. Support asked "Could you also approve the wording…". | `logs/16-apology-email-doc.txt`, `screenshots/M6-support-asks-wording-approval.png` |
| M7 | Support tries to execute and Switch visibly refuses | PASS | Support: "@Treasurer execute rb-da973e02dfbf". Treasurer: *"You're not permitted to direct messages to me in this room — my operator has restricted who can address me here."* Server log: `Addressing denied for treasurer` at 11:39:08. | `screenshots/M7-switch-refuses-support.png` |
| M8 | Treasurer obeys Amiya: 313 refunds, 313 emails | PASS | Amiya's execute at 11:39:38. Batch `executed`, `approved_by` = `user`, 313 refunded, 313 emailed, no charge refunded twice. | `logs/20-db-after-mattermost.txt`, `screenshots/M8-treasurer-obeys-amiya.png` |
| M9 | Mailpit shows 313 emails | PASS | 313 emails to 313 different addresses. Victor's email says "$59.00". | `logs/17-mailpit.txt` |
| M10 | Support writes the postmortem | PASS | Created at 11:40:12, with correct numbers and a timeline. | `logs/18-room-documents-after-run.txt`, `screenshots/M10-postmortem-written.png` |
| M11 | `make verify` shows 4 PASS | PASS | 4 PASS | `logs/19-verify-mattermost.txt` |
| M12 | Complaint to postmortem | **7 min 18 s** | 11:32:54 → 11:40:12 | `logs/14-scenario.txt`, `logs/18-room-documents-after-run.txt` |
| X1 | `export_transcript.py` (first real run) | FAIL | Exit code 1, no file written. See F1. | `logs/21-export-transcript-mattermost.txt` |

### Part 2: two people on Discord

| ID | What we checked | Result | What actually happened | Proof |
|---|---|---|---|---|
| G1 | #support and #finance-approvals appear on the right server | PASS | Both appear in the private "Blast Radius Demo" server. | `screenshots/G1-G2-discord-channels-and-agent-names.png` |
| G2 | Agents post under their own names | PASS | Support, Fixer, Investigator, Treasurer and Customer (simulated) each have their own name and avatar. | `screenshots/G1-G2-discord-channels-and-agent-names.png` |
| G3 | Tushar's complaint reaches Support (no Switch account) | PASS | Posted at 12:38. Support reacted 👀 and replied in a thread. | `screenshots/G3-tushar-complaint-reaches-support-thread.jpg`, `screenshots/G3-support-channel-tushar-view.jpg` |
| G4 | Investigator and Fixer work through Support, and Tushar can reach them | PASS | Support asked the Investigator at 12:39:07. The Fixer committed `3a4471c` at 12:39:49 and posted its summary. Tushar asked the Investigator directly at 13:02 and got an `@Tushar` reply. (Tushar didn't address the Fixer directly.) | `screenshots/G4-fixer-summary-mentions-tushar.jpg`, `screenshots/G4-tushar-reaches-investigator.png`, `logs/agents-discord.log` |
| G5 | Blast channel appears by itself and Tushar sees it | PASS | Name in Discord: **`#blast-ord-100953`** (Switch room `blast-ORD-100953`). Created at 12:38:37, about 37 s after the complaint, after one refused attempt (F3). | `screenshots/G5-blast-channel-appears-tushar-view.jpg` |
| G6 | Tushar gets a real Discord mention | PASS | `@Tushar` mentions show highlighted on his screen. (Amiya did *not* get pinged until Tushar gave Support her username. See F2.) | `screenshots/G6-support-mentions-tushar-cannot-add-admin.jpg` |
| G7 | Investigator's list looks clean, with no pipes | PASS | Bold numbers and a bullet list. | `screenshots/G7-investigator-list-discord.jpg` |
| G8 | Tushar's approvals reach Support and the story continues | PASS, with a workaround | "Fix approved" (12:41) and "Wording approved." (12:49) both reached Support. But Tushar first had to ask Support to paste the wording (F4). | `screenshots/G8-fix-approval-reaches-support.jpg`, `screenshots/G8-apology-document-not-readable-in-discord.png`, `screenshots/G8-support-pastes-wording-on-request.png`, `screenshots/G8-wording-approved-support-asks-admin.png` |
| G9 | Amiya sends `@treasurer prepare refunds` and the batch appears in #finance-approvals | PASS | Asked at 12:53:09. Batch `rb-da973e02dfbf` posted with an `@strider5791` ping. | `screenshots/G9-G11-finance-approvals-batch-raw-mention-code.png`, `logs/agents-discord.log` |
| G10 | Support tries to execute and Switch refuses (exact words) | PASS | *"You're not permitted to direct messages to me in this room — my operator has restricted who can address me here."* Then Support: *"Switch blocked my handover, as it should: only you can approve refunds."* Server log 12:53:14. | `screenshots/G10-switch-refuses-support-discord.png` |
| G11 | Tushar tries `@treasurer execute` and Switch refuses (exact words) | PASS | *"I only take instructions from my owner, and this chat account isn't linked to a Switch user yet — so I can't tell whether that's you. If it is, link this account to your Switch user in Switch Console and try again."* Switch refused it at 12:55:24. The Treasurer program never even received the message. | `screenshots/G11-switch-refuses-tushar.png` |
| G12 | After both refusals, 0 refunds have happened | NOT RUN (as written) | Amiya executed at 12:54:03, before Tushar tried at 12:55:24. What we did prove: after Support's refusal there were 0 refunds (checked 12:53:17), and Tushar's refusal changed nothing (same 313 refunds, same refund time). | `logs/discord-state-timeline.log`, `logs/42-db-after-amiya-execute-discord.txt`, `logs/43-db-after-tushar-refused.txt` |
| G13 | Amiya executes and `approved_by` is right | PASS | `approved_by` = `strider5791` (Amiya's Discord username) | `logs/42-db-after-amiya-execute-discord.txt`, `screenshots/G13-treasurer-obeys-amiya-discord.png` |
| G14 | The Treasurer's own owner check doesn't wrongly refuse Amiya | PASS | It obeyed both "prepare refunds" and "execute". | `logs/agents-discord.log` |
| G15 | 313 refunds and 313 emails | PASS | 313 refunded, 313 emailed, 313 different customers, 0 refunded twice | `logs/43-db-after-tushar-refused.txt`, `logs/45-mailpit-discord.txt` |
| G16 | Email uses Tushar's approved wording, with one dollar sign | PASS | Word for word what Support pasted and Tushar approved. Victor's email says "$59.00", with exactly 1 dollar sign. | `logs/45-mailpit-discord.txt`, `screenshots/G8-support-pastes-wording-on-request.png` |
| G17 | Postmortem exists with correct numbers | PASS | 313 customers, 312 silent, $21,607.00, batch id, 313 refunds and emails. It even notes the "Admin" problem. | `logs/46-room-documents-discord.txt` |
| G18 | `make verify` shows 4 PASS | PASS | 4 PASS | `logs/47-verify-discord.txt` |
| G19 | Complaint to postmortem | **about 16 min 30 s** | 12:38:00 → 12:54:34. About 10 minutes of that was F2 and F4. | `logs/44-discord-rooms-and-docs-after-run.txt` |
| X2 | `export_transcript.py` after the Discord run | FAIL | Same 403 error as X1 | `logs/51-export-transcript-discord.txt` |

### Part 3: run it again on Discord

| ID | What we checked | Result | What actually happened | Proof |
|---|---|---|---|---|
| R1 | The old blast channel is gone from Discord | PASS | `archive_rooms.py --delete` (Amiya agreed first). Server: "Deleted room 4c8fdd05…". Amiya's channel list has no blast channel. (Tushar's list wasn't captured.) | `logs/52-delete-and-reset.txt`, `screenshots/R1-blast-channel-gone-amiya-view.png` |
| R2 | A new blast channel for the same order | PASS | Tushar's complaint at 14:19. New room at 14:20:02, and only one `#blast-ord-100953` in the sidebar. The Investigator posted 313 / 312 / $21,607.00 at 14:20. | `screenshots/R2-new-blast-channel-investigator-numbers.png` |
| R3 | Support and Fixer don't remember the last run | PASS | Support treated it as a new case. The Fixer started from the clean code and made a new commit (`2068a81`). | `screenshots/R3-support-treats-rerun-as-new-case.png`, `logs/54-fixer-commit-rerun.txt` |
| R3b | (extra) The Fixer reports back on a rerun | **FAIL** | The Fixer's summary never reached the room: 8 failed calls (F5). | `screenshots/R3-fixer-summary-never-posted.png`, `logs/55-server-warnings-rerun.txt` |
| R4 | The last run's batch id doesn't confuse Support | NOT RUN | We stopped after the Investigator's numbers, as the plan allows. Also, the Fixer failure meant Tushar had nothing to approve. Note: batch ids are made from the charges (`payments_app/refunds.py:19-22`), so every run's batch is called `rb-da973e02dfbf`. | — |

## 4. What went wrong

### F1. `export_transcript.py` can't read the rooms

- **Expected:** it writes `docs/reference-transcript.md` with the history of the rooms.
- **What happened:** it stopped at the first room (#support) with exit code 1. It wrote nothing, on both Mattermost and Discord.
- **Exact error:** `/chats/4a8a2b6a-059d-4deb-b73a-0e20d5502a3f/messages?limit=200 failed with 403: {"detail":{"code":"NOT_A_MEMBER","message":"You are not a member of this chat."}}`
- **Where it first went wrong:** `switch/export_transcript.py:34`, the call `GET /chats/{room_id}/messages`. The script signs in as Console's admin account, and that account isn't a member of the room's chat. Switch's own API description says only members can list messages; a manager can add themselves to the room first. The same 403 happens for `/chats/{room}/activity` and `/members`.
- **Why it matters:** the repo has no reference transcript yet. Deleting a room before the next take loses its history.

### F2. On Discord, Support thinks the Finance lead is called "Admin"

- **Expected:** Support's instructions name the Finance lead by her Discord username, `strider5791`. Support adds her to the case room and pings her.
- **What happened:** Support's instructions say "`@Admin is the Finance lead`" and list `user_names: [Admin, phantom8817]`. "Admin" is the Switch account's display name, and Discord has no user with that name. The room member lists were right (strider5791); only the agents' instructions were wrong.
- **Exact errors:**
  - `Room … created with 1 attachment failure(s): [{'kind': 'user', 'id': 'Admin', 'error': 'no account with this name is known on the bridge'}]`
  - `send_targeted_message → 400: Targets not in room: Admin. Room participants: fixer, investigator, phantom8817, support, treasurer.`
- **What people saw:**
  - Support asked Tushar to "invite Admin".
  - Support wrote "Admin (Finance lead): …" as plain text, so Amiya got no ping.
  - Only after Tushar typed `strider5791` (12:51) did Support add and ping Amiya.
  - The same thing happened again on the rerun.
- **Where it first went wrong:** `python switch/import_template.py --support-lead phantom8817`, the fresh import in SETUP.md D3. A fresh import lets Switch fill `{$creator}` in the agents' instructions, and it uses "Admin". The script's `--update` step (`update_instructions` in `switch/import_template.py`) fills it with the chat username instead. Part 1 only worked because `--update` was run there. D3 doesn't ask for it.
- **Probable files:** `switch/import_template.py` (the fresh-import path in `main`, around line 171) and `switch/SETUP.md` D3.

### F3. Two room groups called "Blast Radius"

- **Expected:** Support creates the case room inside the "Blast Radius" group.
- **What happened:** Switch refused the first try, and Support's backup plan created the room without a group. It worked, but Discord shows "✗ 1 failed" under Support's progress line.
- **Exact error:** `create_room → 400: Multiple room groups named 'Blast Radius'; ask the user which one to use` (12:38:24, and again at 14:19:48 on the rerun).
- **Where it first went wrong:** D3. Archiving the old Mattermost rooms leaves the old group with 5 archived rooms in it. `switch/import_template.py:157-162` only deletes a leftover group when it's empty, so a second group with the same name was made. Proof: `logs/37-room-groups-after-create-room-400.txt`.
- **Probable files:** `switch/import_template.py:157-162`, `switch/SETUP.md` D3.

### F4. Tushar can't read the apology he must approve

- **Expected:** Tushar reads the `apology-email` document and approves it.
- **What happened:** Discord only shows the line "📄 created room document 'apology-email'", with no way to open it. Tushar had to ask: "@support I can't open the apology-email document in Discord. Please paste the wording here." Support then pasted it, and Tushar approved.
- **Exact error:** none. There's simply no way to open the document in Discord.
- **Cost:** about 7 minutes in this run, from the fix approval at 12:41 to Tushar's question at 12:48.
- **Where it first went wrong:** step 6 of Support's instructions asks for approval of the document but doesn't say to paste the wording into the chat.
- **Probable files:** `switch/agent-instructions/support.md` (and `switch/template.yaml`, which is built from it).

### F5. On a rerun, the Fixer can't post in the new room

- **Expected:** after `!reset-all-agents` and a new complaint, the Fixer fixes the bug and posts its summary in the new #blast-ord-100953.
- **What happened:** the Fixer did fix the bug and commit (`2068a81` at 14:21:33). But every attempt to read or post in the room was refused. Discord only shows "Worked for 1m 20s. 22 tool calls. ✓ 14 done · ✗ 8 failed". No summary reached the room, so the Support lead has nothing to approve.
- **Exact error** (9 times between 14:21:00 and 14:21:51): `POST /agents/05c49a48-…/ops/send_targeted_message → 400: Not connected to a room. Call connect_to_room first.` (also for `read_context` and `post_message`)
- **Where it first went wrong:** the first task after `!reset-all-agents`. Probable cause: the reset happens in #support, so the Fixer's new session is attached to #support. When Support hands it work in a *new* room, the Fixer never calls `connect_to_room`. In the first Discord run the Fixer was brand new, and it worked.
- **Probable files:** `switch/agent-instructions/fixer.md` (no step to connect to the room it was asked in), and the rerun steps in `switch/SETUP.md` (D6) and `README.md`.
- **Not tested:** whether `!reset @fixer` typed inside the new blast room avoids it.

### Smaller problems

- **Mattermost keeps refusing one progress post.** The server log shows `Mattermost post /posts failed: Invalid RootId parameter` for the same agent turn in #support at 11:36:17, 11:46:17 and 11:56:17. Switch retries it every 10 minutes. We saw nothing missing in the chat. This is probably inside Switch, not this repo.
- **Archived rooms leave their channels behind on Mattermost too.** The Mattermost sidebar showed three channels called `blast-ORD-100953`. The server logged `A channel with that name already exists on the same team` when the new one was made.
- **After the refunds, the Investigator tells Tushar "No double charges found. Every order has at most one successful charge."** That's true once refunds exist, but it sounds like it contradicts its own earlier "313".

## 5. What was confusing or slow

**Permission prompts: 0.** We saw no permission prompt from Support or Fixer in any run, in the chat or in the screenshots. Amiya didn't see any in Console either, but in Part 1 Console wasn't watched the whole time. **Bypass permissions was not turned on.**

What in SETUP.md was wrong, missing or unclear:

- **D3 is missing three steps for people coming from Mattermost:**
  - archive the leftover blast room;
  - deal with the old "Blast Radius" group (F3);
  - run `import_template.py --update` after the import, so the agents know the Finance lead's Discord username (F2).
- **D1 and D2 worked as written.** Amiya followed them without problems. A useful tip: copy the bot token last, right before pasting it into Console, so it only lives on the clipboard. After connecting, Console already showed the Discord account as `@strider5791` and Switch listed it as linked, so we didn't see a separate "This is me" step.
- **D5 assumes the Support lead can read the apology document.** On Discord they can't (F4).
- **D5 doesn't say to wait for the Fixer's summary before approving the fix.** In Part 1 the approval came first.
- **Nothing says to check for an old `make agents`.** One from the day before was still running. Two copies would answer every message twice.
- **The plan's order puts Amiya's execute after Tushar's attempt,** but nothing in Discord stops the Finance lead from executing early. That's how G12 was missed. It helps to tell both people the order before starting.
- **`!reset-all-agents` makes customer-sim answer "My session can't be reset — this isn't supported for me" every time.** That's harmless but looks like an error.
- **The rerun steps don't work for the Fixer** (F5).

What was slow:

- The Discord run took about 16½ minutes; Mattermost took about 7. The agents themselves were quick: on Discord, the complaint at 12:38 had the room, the numbers, the fix and the apology draft by 12:39–12:40. Most of the extra time was F4 (about 7 min) and F2 (about 3 min).
- Each Support turn took 12 seconds to 1½ minutes.

## 6. What looked good or bad for the video

**Good:**

- **The refusal to Support is clear:** *"You're not permitted to direct messages to me in this room — my operator has restricted who can address me here."* Then Support says itself: *"Switch blocked my handover, as it should: only you can approve refunds."* This is the key Switch moment, and it reads well.
- **The refusal to Tushar is clear:** *"I only take instructions from my owner, and this chat account isn't linked to a Switch user yet — so I can't tell whether that's you. If it is, link this account to your Switch user in Switch Console and try again."*
- **The new `#blast-ord-100953` channel appears by itself**, about 40 seconds after the complaint.
- **The agents have their own names and avatars.** The Investigator's list is clean, and the Treasurer's batch post is a tidy list.
- **Mailpit fills with 313 emails**, and each one has the right name, order and amount.

**Bad, or worth hiding:**

- **Raw codes in Discord thread titles.** Every reply opens a thread titled like `<@&1568158123254874144> Fix approved`, and they stack up in the sidebar.
- **The Treasurer's "To approve, reply:" line shows a raw code on Discord:** `` <@&1568155875019849768> execute rb-da973e02dfbf `` instead of `@treasurer execute rb-da973e02dfbf`. Copying it wouldn't work. (On Mattermost it was fine.)
- **"✗ 1 failed"** under Support's progress lines (F3), and **"✗ 8 failed"** under the Fixer's on the rerun (F5).
- **Support asking people to "invite Admin"** (F2).
- **Support's "Worked for 22s. 4 tool calls."** and "Starting a session…" lines, plus the bot's "Template kickoff on behalf of @strider5791" thread at the top of #support.
- **#finance-approvals keeps old batches with the same id** (`rb-da973e02dfbf`) from earlier runs. A viewer could think it's the same batch.
- **The Fixer's commits end with a `Co-Authored-By` line naming its AI model.** That's only visible if the video shows the git log.
- **Most of the conversation happens inside threads.** The main channel view shows only the first line of each.

**Real time for the opening line** ("Here's what happened in the next N minutes"):

- **Mattermost: 7 minutes** (7 min 18 s).
- **Discord with two people: 16½ minutes** in this run. With F2 and F4 fixed it should be closer to 7, but it needs a re-measure.

## 7. How the laptop coped

- **No crashes and no visible slowness.** The agents answered within seconds. The server logged a short database hold (about 2 s) twice, both times while creating a room.
- **Memory was under heavy pressure.** At 14:20, swap was 13.4 GB used out of 14.3 GB, free memory was 35%, and the load average was about 3.4. Many other apps were open: VS Code, IntelliJ, Brave, WhatsApp. The project's own Docker containers were small: payments 36 MB, Mailpit 40 MB, Mattermost 201 MB. Close other apps before recording. Proof: `logs/60-laptop-snapshot.txt`.
- **Disk was very low at the start**: only 3.2 GB free at 10:09, against the 15–20 GB the context file asks for. By 14:20 it was 25 GB free (macOS freed space by itself). Check free space before recording.

## 8. What still needs doing (most important first)

1. **Fix F2 ("Admin").** The Discord path must give Support and Fixer the Finance lead's Discord username, for example by running the `--update` step automatically after a fresh import, or adding it to SETUP.md D3. Without this, the Finance-lead handoff breaks on camera.
2. **Fix F4.** Support should paste the apology wording into the chat when it asks for approval, because Discord can't show room documents.
3. **Fix F5.** The Fixer must be able to post in a new room after `!reset-all-agents`, or there are no retakes. Then re-test Part 3 to the end, which also covers R4.
4. **Fix F3.** Remove or rename the leftover "Blast Radius" group, in `import_template.py` or as a SETUP.md step.
5. **Fix F1, or say it's not possible.** No reference transcript can be exported right now.
6. **Tidy for the video:** the raw `<@&…>` codes in thread titles and in the Treasurer's approval line.
7. **Update SETUP.md:** archive the old blast room in D3, check for an old `make agents`, and wait for the Fixer's summary before approving.
8. **Re-run the checks we couldn't finish:** G12 in the planned order (Tushar tries before Amiya executes), R4, and the case where the Finance lead isn't a member of the blast room.
9. **Smaller:** the Investigator's "No double charges found" after refunds, and customer-sim's reply to `!reset-all-agents`.

## Security check

Before committing, the whole `test-report/` folder was searched for tokens, passwords and API keys: the words token, password, API key, secret, bearer and authorization, plus anything shaped like a Discord bot token. **Nothing was found, and nothing had to be removed.** Every screenshot was looked at before it was kept. None shows a token. The bot token was pasted into Switch Console by Amiya and never seen by the tester. Nothing from `agents/.secrets/`, `.env` or any database file is in this folder.
