# Example PR scenarios

Each `.diff` is a PR against `demo-app/`. Run any of them locally (needs `ANTHROPIC_API_KEY`):

```bash
python -m pr_gate --platform local --diff-file examples/scenarios/01-sql-injection.diff
```

| Scenario | What's in it | Expected gate result |
|---|---|---|
| `01-sql-injection.diff` | New `/search` endpoint building SQL with an f-string, plus a debug `print` | **FAIL**: high/critical SQL injection; custom rules `sql-params` (high) and `no-print-debug` (low) |
| `02-secrets-and-shell.diff` | Adds `.env`, a hardcoded AWS key, `shell=True` with user-controlled filename, and a PNG | **FAIL**: command injection. `.env` and the PNG are never sent to the model; the AWS key is redacted to `[REDACTED-SECRET]` before sending, and the summary reports both |
| `03-clean-refactor.diff` | Small, safe refactor of `db()` | **PASS** |

`sample-fail-comment.md` shows what the PR summary comment looks like for scenario 01.
The tests in `tests/test_scenarios.py` replay these diffs against a mocked model to verify filtering, redaction, and PASS/FAIL logic.
