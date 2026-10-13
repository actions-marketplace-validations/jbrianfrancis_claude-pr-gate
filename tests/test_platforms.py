import json

from pr_gate import platforms
from pr_gate.gate import MARKER
from pr_gate.review import Finding


def _rec(monkeypatch, replies=None):
    calls = []

    def fake(method, url, headers, body=None, raw=False):
        calls.append((method, url, body))
        for key, val in (replies or {}).items():
            if key in url and method == "GET":
                return val
        return {}
    monkeypatch.setattr(platforms, "http", fake)
    return calls


def test_github_updates_existing_comment(monkeypatch):
    calls = _rec(monkeypatch, {"/comments": [{"id": 9, "body": MARKER + " old"}]})
    gh = platforms.GitHub("t", "me/repo", 5, "abc")
    gh.post_summary("new")
    assert calls[-1] == ("PATCH", "https://api.github.com/repos/me/repo/issues/comments/9", {"body": "new"})


def test_github_creates_comment_review_and_status(monkeypatch):
    calls = _rec(monkeypatch, {"/comments": []})
    gh = platforms.GitHub("t", "me/repo", 5, "abc")
    gh.post_summary("x")
    gh.post_inline([Finding("high", "security", "t", "d", "a.py", 3)])
    gh.set_status(False, "FAIL")
    assert calls[1][0] == "POST" and calls[1][1].endswith("/issues/5/comments")
    assert calls[2][2]["comments"][0] == {"path": "a.py", "line": 3, "side": "RIGHT",
                                          "body": "**HIGH** · security: **t**\n\nd"}
    assert calls[3][1].endswith("/statuses/abc") and calls[3][2]["state"] == "failure"


def test_github_from_env(monkeypatch, tmp_path):
    ev = tmp_path / "e.json"
    ev.write_text(json.dumps({"pull_request": {"number": 7, "head": {"sha": "s1"}}}))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(ev))
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    monkeypatch.setenv("GITHUB_REPOSITORY", "me/r")
    gh = platforms.GitHub.from_env()
    assert (gh.pr, gh.sha, gh.repo) == (7, "s1", "me/r")


def test_bitbucket_calls(monkeypatch):
    calls = _rec(monkeypatch)
    bb = platforms.Bitbucket("t", "ws", "repo", "3", "abc", "main")
    bb.post_summary("x")
    bb.post_inline([Finding("low", "quality", "t", "d", "a.py", 4)])
    bb.set_status(True, "PASS")
    assert calls[0][1] == "https://api.bitbucket.org/2.0/repositories/ws/repo/pullrequests/3/comments"
    assert calls[1][2]["inline"] == {"path": "a.py", "to": 4}
    assert calls[2][1].endswith("/commit/abc/statuses/build") and calls[2][2]["state"] == "SUCCESSFUL"
