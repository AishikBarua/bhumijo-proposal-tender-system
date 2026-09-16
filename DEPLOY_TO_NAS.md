# Running Bhumijo on the Synology NAS

Your NAS is `BHUMIJO_NAS`, a **Synology at 192.168.1.200**. It is on 24/7, so
once this is done Bhumijo stays up whether or not your PC is switched on.

The final address will be **http://192.168.1.200:8787**

Everything below happens on the NAS. Your PC keeps running its copy until you
confirm the NAS one works — nothing is deleted.

---

## Step 1 — Check the NAS can run containers

Open **http://192.168.1.200:5000**, log in, open **Package Center**, search for
**Container Manager** (called **Docker** on DSM 6).

- **Present or installable** → carry on to step 2.
- **Not there at all** → the NAS is an ARM model that cannot run containers.
  Stop here and tell me; we use a spare office PC instead.

---

## Step 2 — Make a folder on the NAS

In **File Station**, create: `docker/bhumijo`

The full path will be `/volume1/docker/bhumijo`. This is the NAS's own internal
disk, which is what SQLite needs. Do not use a mounted external share.

---

## Step 3 — Copy the project across

From your PC, open `\\192.168.1.200\docker\bhumijo` in File Explorer and copy
in the whole contents of `D:\Tracker\bhumijo_system`.

**Then do this one thing, or the AI Agent will lose its settings:**

> Move `tender_agent.db` **into the `data` folder**.
>
> On your PC it sits in the project root. In the container everything lives in
> `data/`, so that one file has to move. It holds your company profile and
> email settings — 53 KB, easy to overlook.

After copying, `data\` on the NAS should contain **both**:

```
data\bhumijo.db          ~310 KB   179 proposals, 191 grants, 45 clients
data\tender_agent.db      ~53 KB   company profile, email settings
```

---

## Step 4 — Put the AI Agent's secrets in place

The agent's keys are **not** in the project folder — they have to be supplied
separately. Create a file called `.env` in `/volume1/docker/bhumijo` containing:

```
ANTHROPIC_API_KEY=sk-ant-...
IMAP_HOST=imappro.zoho.com
IMAP_PORT=993
IMAP_APP_PASSWORD=...
SMTP_HOST=...
SMTP_PORT=587
GMAIL_APP_PASSWORD=...
APP_TIMEZONE=Asia/Dhaka
```

Fill in the values from wherever they are set on your PC now.

Without `ANTHROPIC_API_KEY` the tracker works perfectly but the AI Agent
cannot call Claude. It will say so plainly in the log at startup:

```
startup: anthropic_api_key=MISSING imap_app_password=MISSING
```

---

## Step 5 — Create the container

**Container Manager → Project → Create**

- Project name: `bhumijo`
- Path: `/volume1/docker/bhumijo`
- Source: **Use existing docker-compose.yml**
- Click through and **Build**

The first build takes a few minutes — it downloads Python and installs the
requirements. Watch the log; you are looking for:

```
[entrypoint] applying AI Agent database migrations...
[entrypoint] agent database is up to date
Bhumijo Proposal & Grant Tracker v2.0.0 (production)
Holding 179 proposals, 191 grant programmes, 45 clients
AI Agent module ready at /agent
```

Those last two lines are the ones that matter: the right record counts, and
the agent loading.

---

## Step 6 — Check it

From any office device:

| | |
|---|---|
| Tracker | http://192.168.1.200:8787 |
| AI Agent | http://192.168.1.200:8787/agent |
| API docs | http://192.168.1.200:8787/docs |

Nothing to type — office devices are let in automatically.

**No firewall change is needed on the NAS by default.** Synology's firewall is
off unless someone turned it on. If the page does not load, check
**Control Panel → Security → Firewall**; if it is enabled, allow TCP 8787.

---

## Step 7 — Fix the address so it never moves

Your PC's IP has already changed twice in a week, which is why bookmarks kept
breaking. Ask whoever manages the router to set a **DHCP reservation** for the
NAS on `192.168.1.200`, so this address is permanent.

Then share `http://192.168.1.200:8787` with everyone.

---

## Step 8 — Switch off the old one

Only after the NAS copy has been used for a day or two:

1. On your PC, run `uninstall_autostart.bat` so it stops starting at login.
2. Keep `D:\Tracker` as it is for a few weeks. It is your fallback.

Your PC can then be switched off without affecting anyone.

---

## Living with it

**It restarts itself.** `restart: unless-stopped` in `docker-compose.yml` means
the container comes back when the NAS reboots, with nobody logged in. That is
the thing that solves your original problem.

**Logs:** Container Manager → Container → `bhumijo` → Log. On disk they are in
`data/logs/bhumijo.log`.

**Restart it:** Container Manager → Container → `bhumijo` → Stop, then Start.

**Update the code later:** copy the changed files into
`/volume1/docker/bhumijo`, then Project → **Build** again. Your data is in the
mounted `data/` folder, so a rebuild never touches it.

**Backups:** the nightly job writes to `data/backups` inside the container,
which is `/volume1/docker/bhumijo/data/backups` on the NAS. That is already
better than on your PC — the NAS has redundant disks — and Synology's own
**Hyper Backup** can copy that folder somewhere else again.

**Both databases are in `data/`.** Back up that one folder and you have
everything.
