"""Parse unified diffs, filter what is safe/useful to send, and chunk."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from fnmatch import fnmatch

SECRET_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),                                   # AWS access key id
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),                     # GitHub tokens
    re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b"),                     # Anthropic keys
    re.compile(r"\bsk-[A-Za-z0-9]{32,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),                   # Slack tokens
]


@dataclass
class FileDiff:
    path: str
    text: str
    binary: bool = False
    added_lines: set[int] = field(default_factory=set)   # new-file line numbers that were added


@dataclass
class FilterResult:
    files: list[FileDiff]
    skipped: dict[str, str]   # path -> reason
    redactions: int = 0


def _match(path: str, patterns: list[str]) -> bool:
    name = path.rsplit("/", 1)[-1]
    for p in patterns:
        if fnmatch(path, p) or fnmatch(name, p) or (p.startswith("**/") and fnmatch(path, p[3:])):
            return True
    return False


def parse_diff(diff: str) -> list[FileDiff]:
    files: list[FileDiff] = []
    cur: FileDiff | None = None
    new_line = 0
    for line in diff.splitlines(keepends=True):
        if line.startswith("diff --git "):
            m = re.match(r"diff --git a/(.+?) b/(.+)$", line.rstrip("\n"))
            cur = FileDiff(path=m.group(2) if m else line.split()[-1], text="")
            files.append(cur)
        if cur is None:
            continue
        cur.text += line
        if line.startswith("Binary files ") or line.startswith("GIT binary patch"):
            cur.binary = True
        elif line.startswith("+++ "):
            p = line[4:].strip()
            if p != "/dev/null":
                cur.path = p[2:] if p.startswith("b/") else p
        elif line.startswith("@@"):
            m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)", line)
            new_line = int(m.group(1)) if m else 0
        elif line.startswith("+") and not line.startswith("+++"):
            cur.added_lines.add(new_line)
            new_line += 1
        elif line.startswith(" "):
            new_line += 1
    return files


def redact(text: str) -> tuple[str, int]:
    n = 0
    for pat in SECRET_PATTERNS:
        text, k = pat.subn("[REDACTED-SECRET]", text)
        n += k
    return text, n


def filter_files(files: list[FileDiff], ignore_paths: list[str], secret_paths: list[str]) -> FilterResult:
    kept, skipped, redactions = [], {}, 0
    for f in files:
        if f.binary:
            skipped[f.path] = "binary"
        elif _match(f.path, secret_paths):
            skipped[f.path] = "secret-looking file (never sent)"
        elif _match(f.path, ignore_paths):
            skipped[f.path] = "ignored by config"
        else:
            f.text, n = redact(f.text)
            redactions += n
            kept.append(f)
    return FilterResult(kept, skipped, redactions)


def chunk(files: list[FileDiff], chunk_chars: int, max_total: int) -> tuple[list[str], list[str]]:
    """Group file diffs into chunks. Returns (chunks, truncated_paths).

    Files are never split mid-hunk unless a single file exceeds chunk_chars, in which
    case it is truncated. Once max_total is reached, remaining files are dropped and listed.
    """
    chunks: list[str] = []
    truncated: list[str] = []
    cur, total = "", 0
    for f in files:
        text = f.text
        if len(text) > chunk_chars:
            text = text[:chunk_chars] + "\n[... file diff truncated ...]\n"
            truncated.append(f.path)
        if total + len(text) > max_total:
            truncated.append(f.path)
            continue
        if cur and len(cur) + len(text) > chunk_chars:
            chunks.append(cur)
            cur = ""
        cur += text
        total += len(text)
    if cur:
        chunks.append(cur)
    return chunks, truncated
