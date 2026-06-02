# ──────────────────────────────────────────────────────────────────────────────
# OPA / Conftest Policy-as-Code — docker-compose guardrails
#
# Evaluated by Conftest using its default YAML parser against docker-compose.yml.
# Enforces runtime-security defaults on every service so an insecure compose file
# can never reach main.
# ──────────────────────────────────────────────────────────────────────────────
package main

# DENY — no service may run privileged. Privileged disables almost every kernel
# isolation boundary and is effectively root-on-host.
deny[msg] {
	svc := input.services[name]
	svc.privileged == true
	msg := sprintf("service '%s' runs in privileged mode — drop 'privileged: true'.", [name])
}

# DENY — block host namespace sharing, which collapses container isolation.
deny[msg] {
	svc := input.services[name]
	forbidden := {"host"}
	forbidden[svc.network_mode]
	msg := sprintf("service '%s' uses network_mode: host — collapses network isolation.", [name])
}

# DENY — secrets must never be hardcoded inline in the compose environment.
# Use env_file / Docker secrets so credentials are not committed to git.
deny[msg] {
	svc := input.services[name]
	env := svc.environment[_]
	regex.match(`(?i)(password|secret|token|api[_-]?key)=.+`, env)
	msg := sprintf("service '%s' hardcodes a credential in 'environment' — move it to env_file/secrets.", [name])
}

# WARN — every long-running service should declare a restart policy.
warn[msg] {
	svc := input.services[name]
	not svc.restart
	msg := sprintf("service '%s' has no restart policy.", [name])
}
