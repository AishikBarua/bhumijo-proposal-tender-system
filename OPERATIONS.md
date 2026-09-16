# Bhumijo Proposal & Grant Tracker — v2

The same screens and the same records as before, rebuilt so each job lives in
its own folder, every record lives in a real database, and every change has a
name and a timestamp against it.

**Your existing system is untouched.** The tracker on port 8585 keeps running
exactly as it did. This folder is a separate system on port 8787, reading your
data files read-only. Nothing switches over until you say so.

---

## Getting started

Run these three, in order, by double-clicking them:

| Step | File | What it does |
|---|---|---|
| 1 | `install.bat` | Installs what Python needs, once |
| 2 | `migrate_data.bat` | Copies your records into the database |
| 3 | `start_server.bat` | Starts the system on port 8787 |

Then open **http://localhost:8787**. The address for other devices on the
office network is written to `data\SERVER_INFO.txt` every time the server
starts, along with the access token.

To check nothing was lost, run `run_tests.bat`.

---

## What the folders are

### `backend/` — the engine

```
api/          the reception desk — routes only, no rules and no SQL
security/     the guard: passwords, sessions, permissions, the audit trail
services/     the engine room: every business rule lives here
models/       the forms: what a proposal, grant, client or user must contain
database/     the strongroom: schema, versioned migrations, and the only
              code in the system that writes SQL
jobs/         the night shift: backups, deadline reminders, weekly digest
config/       the settings drawer — no address or path is written in code
tests/        the checks that prove the rebuild did not change your data
```

The rule that makes this worth having: **each layer may only call the one
below it.** A route never writes SQL. A business rule never knows it is being
called over HTTP. Change one part without the rest moving.

### `frontend/` — the screens

```
index.html            the shell: sidebar, top bar, and where screens load
pages/dashboard/      one folder per screen, each with its own .html and .js
pages/proposals/
pages/clients/
pages/reports/
services/             shared: server calls, state, formatting, navigation
resources/css/        tokens.css (colours, fonts) + components.css
resources/vendor/     Chart.js, stored locally so charts work offline
```

The 3,946-line file became a shell plus four screens. **The JavaScript was
moved, not rewritten** — each file is a verbatim slice of the original, and
the split was verified by checking that every line of the original still
appears exactly once. The screens look and behave identically.

---

## What changed underneath

Nothing a person sees is different. These are the things that changed behind
the screens:

**Two people can now work at the same time.** Saving used to send *all* 179
proposals and overwrite every file with them, so if two people had the page
open, whoever saved second wiped out the other's work — silently. Saves now
insert-or-update, and rows missing from a save are left alone. There is also
a proper endpoint to change one field on one record.

**The access token can no longer be downloaded.** The old server had a
catch-all handler that served any file sitting next to it — including
`proposal_access_token.txt`. Anyone on the office Wi-Fi could read the token
in a browser and then had full write access. Only the `frontend` folder is
served now, and the tests check that the token file, the database and the
source code all return 404.

**Every change is recorded.** Who changed what, when, from what value to what
value. `GET /api/v1/proposals/{id}/history` answers "who marked this
Rejected?" — a question the old system could not answer at all.

**Nothing is thrown away.** Where a value had to be cleaned — dates, money,
categories — the original string is kept beside it in an `original_*` column.
Any mapping decision can be revisited later without loss.

---

## Things that need a decision from you

**1. The category shortlist.** Your 179 proposals use 47 different category
values, including `"RFP for buiding design"` sitting next to
`"RFP for building design"`, and 25 that are blank. A draft mapping onto nine
categories is in `backend/database/category_mapping.py` — it produces:

| | | | |
|---|---|---|---|
| Proposal 77 | Other 29 | RFP 22 | EOI 18 |
| Branding 11 | Tender 9 | Meeting 7 | Consultancy 3 |
| Adhoc 3 | | | |

Someone who knows the business should check it. The screens still show the
original text either way — the shortlist is only used for grouping in reports.

**2. Two records need a human eye.** After migrating, look at
`data\migration_review_*.csv`. Currently two entries:

- Grant id `186` appears twice in `programs.jsonl` — two identical copies of
  "Fund for Innovation in Development". One was kept. Worth deleting the
  duplicate at source.
- One proposal value reads `"BDT 56729.17 lakh (Design+construction)"`, read
  as 5,672,917,000 BDT. Please confirm that is right.

**3. Keep the database on a local disk.** `data\` must sit on a real local
drive. A network share, or a synced folder like OneDrive, Dropbox or Google
Drive, does not support the file locking a database needs — the server will
tell you so in plain words and refuse to start rather than corrupt anything.
Backups can go anywhere; the live database cannot.

**4. Where backups go.** Open `.env` and set `BHUMIJO_BACKUP_DIR` to a
**different disk** — a second drive, a network share, or a USB drive swapped
weekly. The server warns you on startup if backups are going to the same disk
as the live data, which is the exact weakness the old snapshot folder had.

**5. Who the users are.** Logins are built and working but no accounts exist
yet, so the shared token still lets everyone in — the same access everyone has
today, no more and no less. When you are ready, give me a list of names and
which of the five roles each person gets, and logins switch on.

---

## Useful things

| | |
|---|---|
| API documentation | http://localhost:8787/docs — every endpoint, try them live |
| Server details | `data\SERVER_INFO.txt` — address and token, rewritten on each start |
| Logs | `data\logs\bhumijo.log` |
| Database | `data\bhumijo.db` — one file, safe to copy when the server is stopped |
| Settings | `.env` — ports, folders, backup location |

### The access token

The token is generated by the server the first time it starts — you do not
choose it. Three places to find it, easiest first:

1. **The console window**, right after you run `start_server.bat`. It is
   printed on its own line as `ACCESS TOKEN:`.
2. **`data\SERVER_INFO.txt`** — the address and the token together, rewritten
   every time the server starts.
3. **`data\access_token.txt`** — just the token, nothing else.

To use it: open the tracker, click **Server Connection** in the sidebar, and
enter the address (`http://localhost:8787` on this PC, or the network address
from `SERVER_INFO.txt` on any other device) and the token. The browser
remembers it, so this is a one-time step per device.

This is a **different token** from the one your old 8585 tracker uses — that
one lives in `D:\Tracker\proposal_access_token.txt`. The two are not
interchangeable.

Unlike the old server, this token file cannot be downloaded over the network:
requesting it returns 404, and there is a test that checks this.

To issue a new token, stop the server, delete `data\access_token.txt`, and
start it again. Everyone will need to re-enter the new one.

### Starting automatically at login

Run **`install_autostart.bat`** once. After that the system starts silently
every time you log in to Windows — no window appears. `uninstall_autostart.bat`
undoes it.

This is a separate entry from your old 8585 tracker's autostart and the 8000
dashboard's. All three can start at login on their own ports without
interfering.

Because nothing appears on screen, two things change:

- **The token is not printed anywhere you can see it.** Read it from
  `data\SERVER_INFO.txt`, rewritten on every start.
- **If something goes wrong it fails quietly.** Two logs say what happened:
  `data\logs\autostart.log` (starts, stops, restarts) and
  `data\logs\server_console.log` (what the server printed).

Two deliberate choices in how it works:

- **Autostart never imports data.** It runs the server only. Re-running the
  import at every login would wipe the database and rebuild it from the old
  JSONL files, throwing away anything entered since. Importing stays a
  separate, deliberate action.
- **It checks the port before starting.** If a server is already running it
  waits rather than starting a second copy — otherwise the second one fails
  to claim the port and restarts forever, invisibly. This is the `[Errno
  10048] only one usage of each socket address` error, and it is easy to hit
  once autostart is on and you also double-click `start_server.bat`.

If you need to stop a hidden server, end the `python.exe` process in Task
Manager, or restart the PC with autostart uninstalled.

### Automatic jobs

Running inside the server, no scheduling to set up:

- **02:00** nightly backup, compressed, 30 kept
- **07:00** deadline reminders (currently written to the log — tell me which
  mail account to use and they become emails)
- **Monday 08:00** weekly digest

### Old and new endpoints

The nine endpoints your current screens call still work identically, so the
old HTML runs against this server unchanged. The new `/api/v1/...` endpoints
are the real ones. The old ones get deleted once the screens have moved over.

---

## What is deliberately not done yet

- **Logins are not switched on.** Built, tested, and waiting for your list of
  users. Turning them on is a visible change for staff, so it is your call.
- **The frontend files share one scope**, loaded in a fixed order, exactly as
  the original single `<script>` block did. That is what makes the split
  provably behaviour-identical. Converting to true ES modules with explicit
  imports is a real change and belongs in its own step, with its own testing.
- **`collector.py`** — the HR and vendor dashboard on port 8000 — is not
  folded in. It has the same weaknesses and would take roughly two more weeks
  to bring across, which would give you one login for everything.
- **`SEED`** — the 179 hardcoded records inside the old JavaScript — is still
  in `frontend/services/state.js`. It is redundant now the database holds the
  records, but removing it is a behaviour change, so it was left alone.
