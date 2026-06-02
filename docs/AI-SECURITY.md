# AI-Powered Threat Detection — Plain-English Guide

This project's pipeline already runs a stack of **rule-based** security scanners
(Bandit, Semgrep, CodeQL, Trivy, Checkov, OWASP ZAP). Those are excellent at
finding *known* patterns, but they have two well-known weaknesses:

1. **Noise.** They report a lot, including false alarms, and they rank
   everything by generic severity — not by what actually matters in *our* code.
2. **They only see code, not a live attack.** They run before the app is
   deployed. Once the app is running in production, they're blind.

We've added three AI-powered layers to close those gaps. None of them replace
the existing scanners — they sit on top and make the whole system smarter.

Here's each one, what it means, and what it's for.

---

## 1. CodeQL Autofix — AI that *fixes* the bug, not just reports it

**What it is (in one line):** GitHub's AI reads a security bug that CodeQL found
and writes a suggested code fix, right on the pull request.

**What it means:** CodeQL (already in our pipeline) finds things like SQL
injection or unsafe data handling. Normally a human then has to figure out the
fix. Autofix uses AI to draft that fix for you — you review it, click commit if
it's right.

**What it's good for:** Cutting the time between "a bug was found" and "the bug
is fixed". It turns a finding into a one-click correction.

**Cost:** Free for this repo. It reuses the CodeQL analysis we already run.

### How to turn it on (one-time, ~30 seconds)

It's a repository setting, not code — there's nothing to write:

1. Go to the repo on GitHub → **Settings** → **Code security**
   (older UI: *Code security and analysis*).
2. Find **Code scanning** → **Copilot Autofix** (sometimes "CodeQL Autofix").
3. Click **Enable**.

From then on, every CodeQL finding on a pull request gets an AI-suggested fix
attached automatically.

---

## 2. AI Triage — turns scanner noise into a short, ranked review

**What it is (in one line):** After the scanners run, Claude (Anthropic's AI)
reads *all* their findings plus the code change, then posts one tidy comment on
the pull request saying what actually matters.

**What it means:** Instead of a reviewer wading through five separate tool
reports — many of which overlap or are false alarms — they get a single comment
that:

- merges duplicates (when three tools flag the same thing, it's one item),
- judges how risky each issue *really* is in our specific codebase,
- flags the likely false positives, with a reason,
- ranks the genuine issues so the important ones are read first,
- highlights problems introduced by *this* change.

**What it's good for:** Faster, more focused code review. Reviewers spend their
attention on real risks instead of triaging noise by hand.

**Important:** This is **advisory**. It can never block a merge. The hard
pass/fail gate (`security_gate`) is still the rule-based scanners. If the AI is
unavailable for any reason, the pipeline carries on unaffected.

### How it works (the moving parts)

| Piece | What it does |
|-------|--------------|
| Each scanner job | Saves its findings as a `sarif-*` artifact (SARIF is the standard format for scan results). |
| `scripts/ai_triage.py` | Reads those findings + the PR diff, asks Claude to de-duplicate / rank / explain, writes `triage.md`. |
| `ai_triage` job in `.github/workflows/api-ci.yml` | Runs the script on every pull request and posts `triage.md` as a PR comment. |

It uses Claude **Opus 4.8** with adaptive thinking, and caches the stable part
of the prompt so repeat runs are cheaper.

### Setup required (one-time)

The triage job needs an Anthropic API key:

1. Get a key from <https://console.anthropic.com> → *API Keys*.
2. In the repo: **Settings** → **Secrets and variables** → **Actions** →
   **New repository secret**.
3. Name it **`ANTHROPIC_API_KEY`**, paste the key, save.

That's it. (Until the secret is added, the job runs but politely skips with a
notice — it won't error. Pull requests opened from *forks* also skip, because
forks don't get access to secrets.)

**Cost:** A few cents per pull request — one short AI call per PR, with prompt
caching to keep it low.

### Running it locally

```bash
export ANTHROPIC_API_KEY=sk-ant-...
# point it at a folder of .sarif files and a diff
python scripts/ai_triage.py --sarif-dir sarif --diff-file pr.diff --output triage.md
```

---

## 3. Falco — catches an attacker in the *running* system

**What it is (in one line):** A watchdog that sits next to the running
containers and raises an alarm the moment one of them does something it never
should.

**What it means:** Everything above looks at *code*. Falco looks at *behaviour*
of the live, deployed app. It watches the Linux kernel (using a modern, low-
overhead technology called eBPF) and knows what "normal" looks like for our
containers. When something abnormal happens, it alerts. Examples it catches:

- a **shell opening inside** the API container (a classic sign of a break-in),
- a process **writing to system files** like `/etc` (tampering / persistence),
- a **package manager running** at runtime (an attacker installing tools),
- (extendable) unexpected outbound network connections.

**What it's good for:** Detecting an attack *after* deploy, which the CI scanners
fundamentally cannot. It's the difference between "is this code safe?" and "is
someone attacking us right now?"

### How it works

| Piece | What it does |
|-------|--------------|
| `falco` service in `docker-compose-prod.yml` | Runs the Falco watchdog alongside the app (privileged, so it can see the kernel). |
| `falco/falco_rules.local.yaml` | Our app-specific alert rules, layered on top of Falco's large built-in ruleset. |

It's already wired into the production compose file, so it starts with the rest
of the stack (`make prod-up`).

### Seeing the alerts

By default alerts print to the Falco container's logs:
 
```bash
make prod-logs            # all services
docker compose -f docker-compose-prod.yml logs -f falco   # just Falco
```

For real operations you'd forward these to somewhere a human will see them
(Slack, a SIEM, PagerDuty) using Falco's `json_output` plus an output channel or
[Falcosidekick](https://github.com/falcosecurity/falcosidekick). That's a
follow-up once you decide where alerts should land.

---

## How the layers fit together

```
        CODE (before deploy)                         RUNNING APP (after deploy)
 ┌─────────────────────────────────┐            ┌──────────────────────────────┐
 │ Scanners: Bandit, Semgrep,      │            │ Falco                        │
 │ CodeQL, Trivy, Checkov, ZAP     │            │ (behavioural alerts on the   │
 │            │                    │            │  live containers)            │
 │            ▼                    │            └──────────────────────────────┘
 │  [1] CodeQL Autofix             │
 │      (AI drafts the fix)        │     [3] runtime layer ▲
 │            │                    │
 │            ▼                    │
 │  [2] AI Triage (Claude)         │
 │      de-dupe · rank · explain   │
 │      → one PR comment           │
 └─────────────────────────────────┘
```

- **[1] and [2]** make the *code* checks smarter and faster to act on.
- **[3]** adds a whole new dimension: watching the *running* system.

All three are additive. The original rule-based gates still decide whether a
build passes — the AI layers help humans act on the results and extend coverage
to runtime.
