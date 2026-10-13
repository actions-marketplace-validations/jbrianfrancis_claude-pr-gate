from pathlib import Path

from pr_gate.config import DEFAULTS
from pr_gate.diff import chunk, filter_files, parse_diff, redact

SC = Path(__file__).resolve().parent.parent / "examples" / "scenarios"


def test_parse_added_lines():
    files = parse_diff((SC / "01-sql-injection.diff").read_text())
    assert [f.path for f in files] == ["demo-app/app.py"]
    assert files[0].added_lines == set(range(21, 30))


def test_filter_binary_secret_and_redaction():
    files = parse_diff((SC / "02-secrets-and-shell.diff").read_text())
    res = filter_files(files, DEFAULTS["ignore_paths"], DEFAULTS["secret_paths"])
    assert res.skipped == {".env": "secret-looking file (never sent)", "demo-app/logo.png": "binary"}
    assert [f.path for f in res.files] == ["demo-app/export.py"]
    assert "AKIA" not in res.files[0].text and "[REDACTED-SECRET]" in res.files[0].text
    assert res.redactions == 1


def test_ignore_globs():
    diff = "diff --git a/package-lock.json b/package-lock.json\n+++ b/package-lock.json\n+x\n" \
           "diff --git a/docs/a.md b/docs/a.md\n+++ b/docs/a.md\n+y\n"
    res = filter_files(parse_diff(diff), DEFAULTS["ignore_paths"] + ["docs/**"], DEFAULTS["secret_paths"])
    assert res.files == [] and set(res.skipped) == {"package-lock.json", "docs/a.md"}


def test_redact_patterns():
    text, n = redact("a=ghp_" + "x" * 36 + " b=sk-ant-api03-" + "y" * 30 + "\n-----BEGIN RSA PRIVATE KEY-----")
    assert n == 3 and "ghp_" not in text


def _big(n_files, size):
    return "".join(f"diff --git a/f{i}.py b/f{i}.py\n+++ b/f{i}.py\n@@ -0,0 +1 @@\n+" + "x" * size + "\n"
                   for i in range(n_files))


def test_chunking_groups_files():
    chunks, truncated = chunk(parse_diff(_big(10, 1000)), chunk_chars=3000, max_total=100_000)
    assert len(chunks) == 5 and truncated == []
    assert all(len(c) <= 3000 for c in chunks)


def test_large_file_truncated_and_budget():
    files = parse_diff(_big(5, 5000))
    chunks, truncated = chunk(files, chunk_chars=2000, max_total=4500)
    assert "[... file diff truncated ...]" in chunks[0]
    assert "f4.py" in truncated and len("".join(chunks)) <= 4500
