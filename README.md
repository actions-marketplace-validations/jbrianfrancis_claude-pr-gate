# claude-pr-gate

**An AI reviewer that blocks risky pull requests before a human has to.**
Every PR gets a quality and security review from Claude, one summary comment, inline notes on the exact lines, and a PASS/FAIL status you can make a required check. Works on **GitHub Actions** and **Bitbucket Pipelines** with the same core script.

## The problem

Small teams merge fast. Human reviewers skim large diffs, miss the SQL built with an f-string on line 412, and nobody has time to set up and tune a SAST suite. Generic linters don't know your team's rules ("all SQL uses bound parameters", "no `print` debugging").
`claude-pr-gate` reads the diff like a senior reviewer, enforces the rules you write in plain English, and fails the build only at the severity you choose.

## What it does

- Fetches the PR diff and reviews only changed lines for **security** and **quality** issues, plus your **custom rules**
- Posts **one** summary comment (updated in place on each push, not spammed) and optional **inline comments** on added lines
- Sets a **PASS/FAIL** commit status (`claude-pr-gate`) that you can make a required check
- Handles **large diffs**: groups files into chunks, truncates oversized files, and enforces a total budget. Anything not fully reviewed is listed in the comment
- **Skips binaries**, never sends `.env`, keys, certs or credential files, and **redacts secret-looking strings** (AWS, GitHub, Slack, Anthropic keys, private keys) before anything leaves the runner
- **Fail-open or fail-closed** when the API is down or the key is missing, your choice
- No SDK dependencies: Python stdlib plus PyYAML

## 2-minute setup (GitHub)

1. Add a repo secret `ANTHROPIC_API_KEY` (Settings → Secrets and variables → Actions).
2. Create `.github/workflows/pr-gate.yml`:

```yaml
name: pr-gate
on:
  pull_request:
    types: [opened, synchronize, reopened]
permissions:
  contents: read
  pull-requests: write
  statuses: write
jobs:
  gate:
    if: github.event.pull_request.head.repo.full_name == github.repository  # forks get no secrets
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: jbrianfrancis/claude-pr-gate@v1
        with:
          anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
```

3. Optional: copy [`.pr-gate.yml`](.pr-gate.yml) into your repo and edit the rules.
4. Optional: in branch protection, make `claude-pr-gate` a required status check.

### Bitbucket

Copy [`examples/bitbucket-pipelines.yml`](examples/bitbucket-pipelines.yml). Add secured repository variables `ANTHROPIC_API_KEY` and `BITBUCKET_ACCESS_TOKEN` (a repository access token with pull request and repository write scopes). It runs the same `python -m pr_gate`, with `--platform bitbucket`.

### Try it locally

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...
python -m pr_gate --platform local --diff-file examples/scenarios/01-sql-injection.diff
python -m pr_gate --platform local --base origin/main   # review your current branch
```

## Config reference (`.pr-gate.yml`)

All keys are optional.

| Key | Default | Meaning |
|---|---|---|
| `model` | `claude-sonnet-5-5` | Anthropic model id. The action input `model` or env `PR_GATE_MODEL` overrides it |
| `fail_on` | `high` | Lowest severity that fails the gate: `info` `low` `medium` `high` `critical`, or `none` |
| `max_findings` | `{}` | Per-severity count limits, e.g. `{medium: 5}` fails on the 6th medium |
| `on_error` | `open` | If the gate itself errors: `open` passes (and says so), `closed` fails |
| `categories` | `[security, quality]` | What the reviewer looks for |
| `custom_rules` | `[]` | List of `{id, description, severity}`. Violations are reported under the rule id at your severity |
| `ignore_paths` | lockfiles, `dist/`, `vendor/`, `*.min.js` | Globs **added** to the defaults; matched files are not reviewed |
| `secret_paths` | `.env*`, `*.pem`, `*.key`, `id_rsa*`, `*.p12`, `*.pfx`, `credentials*`, `secrets*.yml` | Globs **added** to the defaults; matched files are never sent |
| `max_diff_chars` | `120000` | Total diff budget per PR (≈30K tokens). Files beyond it are listed as not reviewed |
| `chunk_chars` | `40000` | Max characters per API request. Bigger files are truncated |
| `inline_comments` | `true` | Post inline review comments on added lines |
| `max_inline_comments` | `15` | Cap on inline comments |
| `max_tokens` | `4096` | Max output tokens per request |

## What it catches

[`demo-app/`](demo-app/) is a tiny, intentionally vulnerable notes service. [`examples/scenarios/`](examples/scenarios/) has three PRs against it:

| PR | Result |
|---|---|
| SQL injection in a new `/search` endpoint, plus a debug `print` | ❌ FAIL (critical SQL injection; custom rules `sql-params` and `no-print-debug`) |
| Adds `.env`, a hardcoded AWS key, `subprocess(..., shell=True)` with user input, and a PNG | ❌ FAIL (command injection). `.env` and the PNG are not sent, and the AWS key is redacted |
| Small safe refactor | ✅ PASS |

See [sample-fail-comment.md](examples/scenarios/sample-fail-comment.md) for what the PR comment looks like.

## Cost per PR

You pay Anthropic directly at standard API prices. Each PR comment shows its token count and estimated cost.
Estimate for Sonnet ($3 per million input tokens, $15 per million output):

| PR size | Diff tokens (≈4 chars/token) + ~700 prompt | Output | ≈ Cost |
|---|---|---|---|
| Small (~100 changed lines, ~5 KB) | ~2K in | ~400 | **~$0.01** |
| Typical (~300 lines, ~15 KB) | ~5K in | ~800 | **~$0.03** |
| Large, hits the 120 KB cap (3 chunks) | ~32K in | ~3K | **~$0.15 max** |

A team opening 200 PRs a month with about 3 pushes each spends roughly **$10–20 a month**. Set `model: claude-haiku-4-5` for about a third of that. These are estimates, so check current pricing.

## Data handling

- Only the **diff** of the PR is sent to the Anthropic API, not the whole repository.
- Binary files, files matching `secret_paths`, and ignored paths are dropped **before** sending. Secret-looking strings are replaced with `[REDACTED-SECRET]`. The PR comment lists everything that was skipped.
- Under Anthropic's commercial terms, API inputs and outputs aren't used to train models by default. Check their current policy and your own compliance needs.
- The action runs on your own runner with your own key. Nothing goes to any third party except Anthropic.
- Diff content is treated as untrusted data in the prompt, so instructions hidden in code comments are ignored.
- Regulated code (health or payment data, and so on): review whether sending diffs to an external API is allowed before enabling.

## Development

```bash
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest -q
```

Tests mock the Anthropic API and the GitHub and Bitbucket HTTP calls, so they need no keys and no network.

## Hire me

I set this up for teams as a fixed-price package: **installed, tuned to your codebase and rules, and running on your GitHub or Bitbucket in 3 days.**

- Price: `[PRICE]`
- Includes: `[SCOPE — e.g. setup on N repos, custom rules workshop, 2 weeks of tuning]`
- Contact: `[CONTACT LINK]`
- Profiles: `[UPWORK / CONTRA LINK]`

## License

MIT © Brian Francis
