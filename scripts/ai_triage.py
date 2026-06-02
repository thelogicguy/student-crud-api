#!/usr/bin/env python3
"""AI-powered triage of the pipeline's security findings.

Reads the SARIF reports produced by the shift-left scanners (Bandit, Semgrep,
Trivy, Checkov, ...), pairs them with the pull-request diff, and asks Claude to:

  * de-duplicate findings that several tools reported,
  * judge how exploitable each one really is *in this codebase*,
  * flag the likely false positives,
  * rank what's left so a reviewer reads the important things first.

The result is written as Markdown to ``--output`` (default ``triage.md``); the
workflow posts that file as a single pull-request comment.

This is an *advisory* step. It never fails the build — the rule-based gates in
``security_gate`` remain the hard pass/fail. If the API key is missing (e.g. a
fork PR with no access to secrets) the script writes a short notice and exits 0.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from collections import defaultdict

# Opus 4.8 — most capable model; same request surface as 4.7.
MODEL = "claude-opus-4-8"

SYSTEM_PROMPT = """\
You are a senior application-security engineer triaging the automated findings \
from a DevSecOps pipeline for a small Python/Flask REST API (student CRUD \
service, SQLAlchemy, Gunicorn, Docker, Nginx).

You are given (1) raw findings from several scanners — Bandit and Semgrep \
(SAST), Trivy and Checkov (dependencies + IaC) — and (2) the diff of the pull \
request under review.

Your job is to turn noise into a short, ranked, reviewer-friendly report. For \
the findings:

1. De-duplicate: when multiple tools report the same underlying issue, merge \
   them into one entry and note which tools flagged it.
2. Assess real exploitability *in the context of this codebase and this diff* — \
   not the generic CWE severity. A hard-coded secret in a test fixture is not \
   the same as one in production config.
3. Mark likely false positives explicitly, with a one-line reason.
4. Rank the genuine issues by real-world risk (Critical → Low).
5. Prefer issues introduced or touched by THIS diff; call those out first.

Output GitHub-flavoured Markdown only — no preamble, no code fences around the \
whole thing. Use exactly this structure:

## 🤖 AI Security Triage

**Summary:** one or two sentences — overall risk of this PR.

### 🔴 Action needed
A table with columns: Issue | Where | Tools | Why it matters | Suggested fix.
Only genuinely actionable issues. If none, write "None.".

### 🟡 Worth a look
Lower-confidence or lower-severity items, same table shape. If none, omit this \
section.

### ⚪ Likely false positives
Bullet list: each item one line — the finding and why you think it's noise.

Be concise and specific. Reference file:line. Do not invent findings that are \
not in the input. If the input contains no findings, say the scanners reported \
nothing and there is nothing to triage."""


def extract_findings(sarif_dir: str) -> list[dict]:
    """Flatten every SARIF file under ``sarif_dir`` into a list of findings."""
    findings: list[dict] = []
    for path in glob.glob(os.path.join(sarif_dir, "**", "*.sarif"), recursive=True):
        try:
            with open(path, encoding="utf-8") as fh:
                doc = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"::warning::could not parse {path}: {exc}", file=sys.stderr)
            continue

        for run in doc.get("runs", []):
            tool = (
                run.get("tool", {}).get("driver", {}).get("name")
                or os.path.basename(path)
            )
            # Map ruleId -> human description from the rule metadata, when present.
            rule_help = {}
            for rule in run.get("tool", {}).get("driver", {}).get("rules", []):
                rid = rule.get("id")
                text = (
                    rule.get("shortDescription", {}).get("text")
                    or rule.get("fullDescription", {}).get("text")
                    or rule.get("name")
                )
                if rid and text:
                    rule_help[rid] = text

            for result in run.get("results", []):
                loc = (result.get("locations") or [{}])[0]
                phys = loc.get("physicalLocation", {})
                artifact = phys.get("artifactLocation", {}).get("uri", "")
                line = phys.get("region", {}).get("startLine")
                rid = result.get("ruleId", "")
                findings.append(
                    {
                        "tool": tool,
                        "rule_id": rid,
                        "level": result.get("level", "warning"),
                        "message": result.get("message", {}).get("text", "").strip(),
                        "rule_description": rule_help.get(rid, ""),
                        "file": artifact,
                        "line": line,
                    }
                )
    return findings


def build_user_content(findings: list[dict], diff: str) -> str:
    """Compose the volatile part of the prompt (findings + diff)."""
    by_tool: dict[str, list[dict]] = defaultdict(list)
    for f in findings:
        by_tool[f["tool"]].append(f)

    counts = ", ".join(f"{tool}: {len(items)}" for tool, items in sorted(by_tool.items()))

    # Cap the diff so a huge PR can't blow the context window; note when truncated.
    max_diff_chars = 60_000
    truncated = len(diff) > max_diff_chars
    diff_slice = diff[:max_diff_chars]

    parts = [
        f"## Scanner findings ({len(findings)} total — {counts or 'none'})",
        "```json",
        json.dumps(findings, indent=2),
        "```",
        "",
        "## Pull-request diff" + (" (truncated)" if truncated else ""),
        "```diff",
        diff_slice if diff_slice.strip() else "(no diff available)",
        "```",
    ]
    return "\n".join(parts)


def triage(findings: list[dict], diff: str) -> str:
    import anthropic  # imported here so the no-key path needs no dependency

    client = anthropic.Anthropic()
    user_content = build_user_content(findings, diff)

    # Stream because the report can be long; get_final_message() gives timeout
    # protection without hand-handling events.
    with client.messages.stream(
        model=MODEL,
        max_tokens=8000,
        thinking={"type": "adaptive"},
        output_config={"effort": "high"},
        # The system prompt is byte-stable across every PR -> cache it. The
        # findings + diff vary per request and sit after the cached prefix.
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_content}],
    ) as stream:
        message = stream.get_final_message()

    return "".join(block.text for block in message.content if block.type == "text").strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sarif-dir", default="sarif", help="directory of *.sarif reports")
    parser.add_argument("--diff-file", default="pr.diff", help="file containing the PR diff")
    parser.add_argument("--output", default="triage.md", help="Markdown report to write")
    args = parser.parse_args()

    def write(text: str) -> None:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(text.rstrip() + "\n")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        write(
            "## 🤖 AI Security Triage\n\n"
            "_Skipped: `ANTHROPIC_API_KEY` is not available to this run "
            "(this is expected for pull requests from forks). The rule-based "
            "security gates still ran and remain authoritative._"
        )
        print("ANTHROPIC_API_KEY not set — wrote skip notice.", file=sys.stderr)
        return 0

    findings = extract_findings(args.sarif_dir)

    if not findings:
        write(
            "## 🤖 AI Security Triage\n\n"
            "**Summary:** the SAST/SCA/IaC scanners reported no findings on this "
            "change. Nothing to triage. ✅"
        )
        print("No findings — wrote clean report.", file=sys.stderr)
        return 0

    diff = ""
    try:
        with open(args.diff_file, encoding="utf-8") as fh:
            diff = fh.read()
    except OSError:
        print(f"::warning::diff file {args.diff_file} not found; triaging without diff",
              file=sys.stderr)

    try:
        report = triage(findings, diff)
    except Exception as exc:  # never fail the pipeline on a triage hiccup
        print(f"::warning::AI triage failed: {exc}", file=sys.stderr)
        write(
            "## 🤖 AI Security Triage\n\n"
            f"_Triage could not run this time ({type(exc).__name__}). "
            f"{len(findings)} raw finding(s) are in the workflow artifacts and the "
            "GitHub Security tab._"
        )
        return 0

    write(report)
    print(f"Triaged {len(findings)} findings -> {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
