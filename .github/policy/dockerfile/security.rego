# ──────────────────────────────────────────────────────────────────────────────
# OPA / Conftest Policy-as-Code — Dockerfile guardrails
#
# Evaluated by Conftest using its `dockerfile` parser, which turns the Dockerfile
# into an ordered array of instructions: [{ "Cmd": "from", "Value": [...] }, ...].
# Every `deny` rule that matches blocks the pipeline; `warn` rules only annotate.
# This is the codified, machine-enforced version of our container hardening rules.
# ──────────────────────────────────────────────────────────────────────────────
package main

# Helper: true if the Dockerfile declares at least one USER instruction.
has_user {
	input[_].Cmd == "user"
}

# DENY — image must not run as root. Require an explicit USER instruction.
# Root containers turn a single app RCE into host-level compromise.
deny[msg] {
	not has_user
	msg := "No USER instruction found — the final image would run as root."
}

# DENY — base images must be version-pinned. ':latest' (or no tag) is mutable
# and breaks build reproducibility + supply-chain provenance.
deny[msg] {
	input[i].Cmd == "from"
	image := input[i].Value[0]
	endswith(lower(image), ":latest")
	msg := sprintf("FROM '%s' uses the ':latest' tag — pin an explicit version.", [image])
}

# DENY — never use ADD with a remote URL. ADD silently fetches+unpacks remote
# content (MITM / tarbomb risk). Use COPY for local files, RUN curl when remote
# fetch is genuinely required (so it is visible and checksum-able).
deny[msg] {
	input[i].Cmd == "add"
	src := input[i].Value[0]
	regex.match(`^https?://`, src)
	msg := sprintf("ADD pulls a remote URL '%s' — use COPY or an explicit, checksummed RUN curl.", [src])
}

# Helper: true if the Dockerfile declares at least one HEALTHCHECK instruction.
has_healthcheck {
	input[_].Cmd == "healthcheck"
}

# WARN — prefer an explicit HEALTHCHECK so orchestrators detect a wedged process.
warn[msg] {
	not has_healthcheck
	msg := "No HEALTHCHECK instruction — orchestrators cannot detect an unhealthy container."
}
