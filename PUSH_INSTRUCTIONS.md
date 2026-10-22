# How to push this project to GitHub (two contributors, no conflicts)

The project is split into two parts that share **no files**, so each of you can
commit and push your own half and the two halves combine with no merge conflict.
After both halves are pushed, the repository runs as-is.

- **Part A — Policy engine & configuration** → Ankit Ray (24BCE0497)
- **Part B — Daemon, service & packaging** → Naman Jain (24BKT0140)

## Who owns which files

```
Shared scaffold (goes in the first push, by Naman)
  .gitignore
  README.md
  CONTRIBUTORS.md
  requirements.txt
  CPU_Affinity_Priority_Agent.docx
  cpu_affinity_agent/__init__.py

Part B  (Naman Jain)
  cpu_affinity_agent/agent.py
  systemd/cpu-affinity-agent.service
  install.sh
  tests/test_agent.py

Part A  (Ankit Ray)
  cpu_affinity_agent/config.py
  cpu_affinity_agent/matching.py
  cpu_affinity_agent/enforcement.py
  config/agent.json
  tests/test_engine.py
```

Because the two parts touch different files, nobody overwrites anybody. The only
rule: **do not edit the shared files in your own half**, or that file could
conflict.

## Before you start: use the right email

A commit only counts toward your GitHub contributions if its author email is one
of **your** verified GitHub emails. Find yours at GitHub → Settings → Emails. If
you prefer not to expose a real address, use your GitHub no-reply email, which
looks like `12345678+username@users.noreply.github.com` (the number and name are
on that same settings page). Set it per-repo with `git config user.email "..."`.

---

## Option 1 — Sequential (simplest, recommended)

### Step 1 — Naman creates the repo and pushes Part B + the shared files

Run from the project folder (`OS_PROJECT`) on the machine that has the code:

```bash
git init -b main
git config user.name  "Naman Jain"
git config user.email "<Naman's GitHub email>"

# stage the shared scaffold + Part B only (not Part A)
git add .gitignore README.md CONTRIBUTORS.md requirements.txt \
        CPU_Affinity_Priority_Agent.docx \
        cpu_affinity_agent/__init__.py cpu_affinity_agent/agent.py \
        systemd/cpu-affinity-agent.service install.sh tests/test_agent.py

git commit -m "Part B: daemon, systemd service, packaging, docs"

# create the GitHub repo and push (needs the gh CLI, already logged in as Naman080706)
gh repo create cpu-affinity-priority-agent --public --source=. --remote=origin --push
```

If you do not want to use `gh`, create an empty repo on github.com (no README),
then:

```bash
git remote add origin https://github.com/Naman080706/cpu-affinity-priority-agent.git
git push -u origin main
```

### Step 2 — Give Ankit his Part A files

Send Ankit these five files (email, drive, chat, anything):

```
cpu_affinity_agent/config.py
cpu_affinity_agent/matching.py
cpu_affinity_agent/enforcement.py
config/agent.json
tests/test_engine.py
```

### Step 3 — Ankit clones, adds Part A, and pushes

On Ankit's machine:

```bash
git clone https://github.com/Naman080706/cpu-affinity-priority-agent.git
cd cpu-affinity-priority-agent
git config user.name  "Ankit Ray"
git config user.email "<Ankit's GitHub email>"

# put the five Part A files into place (same paths as above),
# creating the config/ folder if needed, then:
git add cpu_affinity_agent/config.py cpu_affinity_agent/matching.py \
        cpu_affinity_agent/enforcement.py config/agent.json tests/test_engine.py

git commit -m "Part A: policy engine (config, matching, enforcement) + tests"
git push
```

All of Ankit's files are new, so the push applies cleanly with no conflict. The
repository now has two commits from two authors and is complete.

---

## Option 2 — Branch + Pull Request (if you want to show PRs/merges)

1. Naman does Step 1 above, but commits only the shared scaffold first
   (`git add .gitignore README.md CONTRIBUTORS.md requirements.txt CPU_Affinity_Priority_Agent.docx cpu_affinity_agent/__init__.py`),
   pushes `main`, then adds Part B on a branch:
   ```bash
   git switch -c part-b
   git add cpu_affinity_agent/agent.py systemd/ install.sh tests/test_agent.py
   git commit -m "Part B: daemon, systemd service, packaging"
   git push -u origin part-b
   ```
   Open a Pull Request from `part-b` into `main` and merge it.
2. Ankit clones, branches, adds his files, pushes, and opens a PR:
   ```bash
   git switch -c part-a
   git add cpu_affinity_agent/config.py cpu_affinity_agent/matching.py \
           cpu_affinity_agent/enforcement.py config/agent.json tests/test_engine.py
   git commit -m "Part A: policy engine + tests"
   git push -u origin part-a
   ```
   Open a PR from `part-a` into `main` and merge it.

Both PRs change different files, so GitHub merges them with no conflict.

---

## After both halves are pushed: verify it runs

Anyone can clone the finished repo and check it:

```bash
git clone https://github.com/Naman080706/cpu-affinity-priority-agent.git
cd cpu-affinity-priority-agent
pip install -r requirements.txt          # or: sudo apt install python3-psutil
python -m pytest tests/ -v               # expect 15 passed
python -m cpu_affinity_agent.agent --config config/agent.json --check
```

On Ubuntu, install it as a service with `sudo ./install.sh`.

## Confirm both contributors

On the repo page, open **Insights → Contributors**, or run:

```bash
git shortlog -sne
```

You should see both Ankit Ray and Naman Jain.
