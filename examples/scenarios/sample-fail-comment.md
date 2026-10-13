<!-- Real comment posted by the gate on https://github.com/jbrianfrancis/claude-pr-gate/pull/1 (claude-sonnet-5-5, Oct 13 2026) -->
<!-- claude-pr-gate -->
## Claude PR Gate: ❌ FAIL
- 1 finding(s) at or above 'high'

| Severity | Category | Location | Finding |
|---|---|---|---|
| 🔴 high | sql-params | `demo-app/app.py:26` | **SQL injection via f-string in search query**: User-controlled `q` from request.args is interpolated directly into the SQL string. An attacker can inject arbitrary SQL (e.g. `' UNION SELECT ...`) to read or manipulate data. Use bound parameters instead: `db().execute("SELECT id, title FROM notes WHERE title LIKE ?", (f"%{q}%",))` (use the placeholder style of your driver). Escape `%` and `_` in `q` if literal matching is needed. |
| 🟠 medium | quality | `demo-app/app.py:24` | **Possible missing `request` import**: The new route uses `request.args`, but the diff context does not show `request` being imported from flask. If it is not already imported, this raises NameError at runtime. Verify `from flask import request` exists at the top of the file. |
| 🟡 low | no-print-debug | `demo-app/app.py:25` | **Debug print() left in non-test code**: `print("searching", q)` is leftover debug output. It also writes unsanitized user input to stdout/logs. Remove it or use the `logging` module at an appropriate level. |

<sub>model `claude-sonnet-5-5` · 669 in / 483 out tokens · ≈$0.006</sub>
