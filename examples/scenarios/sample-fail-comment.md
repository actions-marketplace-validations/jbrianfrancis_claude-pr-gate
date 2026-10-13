<!-- claude-pr-gate -->
## Claude PR Gate: ❌ FAIL
- 2 finding(s) at or above 'high'

| Severity | Category | Location | Finding |
|---|---|---|---|
| 🛑 critical | security | `demo-app/app.py:26` | **SQL injection in /search**: User input `q` is interpolated into SQL. Use a bound parameter: `WHERE title LIKE ?` with `(f"%{q}%",)`. |
| 🔴 high | sql-params | `demo-app/app.py:26` | **SQL built with f-string**: Violates team rule sql-params. |
| 🟡 low | no-print-debug | `demo-app/app.py:25` | **Debug print left in handler**: Remove or use logging. |

<sub>model `claude-sonnet-4-5` · 1,412 in / 389 out tokens · ≈$0.010</sub>
