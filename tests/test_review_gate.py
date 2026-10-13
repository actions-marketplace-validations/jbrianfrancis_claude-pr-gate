import io
import json
import urllib.error

import pytest

from pr_gate.config import load_config
from pr_gate.gate import decide, estimate_cost, render_summary
from pr_gate.review import Finding, Usage, call_anthropic, parse_findings, review_chunks
from helpers import RecordingCaller, fake_response


def test_parse_findings_tolerates_prose_and_bad_values():
    txt = 'Sure!\n{"findings":[{"severity":"HIGH","title":"t","detail":"d","path":"a.py","line":"7"},' \
          '{"severity":"weird","title":"x"}]}'
    fs = parse_findings(txt)
    assert fs[0].severity == "high" and fs[0].line == 7
    assert fs[1].severity == "info" and fs[1].line is None


def test_parse_findings_no_json():
    with pytest.raises(ValueError):
        parse_findings("I could not review this")


def test_review_sums_usage_and_applies_rule_severity():
    cfg = load_config(None, {"custom_rules": [{"id": "sql-params", "description": "bind", "severity": "critical"}]})
    caller = RecordingCaller(fake_response([{"severity": "low", "rule": "sql-params", "title": "x"}], 100, 10),
                             fake_response([], 50, 5))
    fs, usage = review_chunks(cfg, ["a", "b"], "k", caller=caller)
    assert fs[0].severity == "critical"
    assert (usage.input_tokens, usage.output_tokens) == (150, 15)
    assert "[sql-params]" in caller.prompts[0] and "<diff>\na\n</diff>" in caller.prompts[0]


@pytest.mark.parametrize("fail_on,sevs,passed", [
    ("high", ["medium", "low"], True), ("high", ["high"], False), ("medium", ["medium"], False),
    ("none", ["critical"], True), ("critical", ["high"], True)])
def test_decide_thresholds(fail_on, sevs, passed):
    cfg = load_config(None, {"fail_on": fail_on})
    assert decide(cfg, [Finding(s, "security", "t", "d") for s in sevs])[0] is passed


def test_decide_max_findings():
    cfg = load_config(None, {"fail_on": "none", "max_findings": {"low": 2}})
    ok, reasons = decide(cfg, [Finding("low", "quality", "t", "d")] * 3)
    assert not ok and "limit 2" in reasons[0]


def test_cost():
    assert estimate_cost("claude-sonnet-4-5", Usage(1_000_000, 100_000)) == pytest.approx(4.5)
    assert estimate_cost("claude-haiku-4-5", Usage(1_000_000, 0)) == pytest.approx(1.0)


def test_summary_escapes_pipes():
    cfg = load_config(None)
    body = render_summary(cfg, False, ["r"], [Finding("high", "security", "a|b", "x\ny", "f.py", 3)], {}, [], Usage())
    assert "a\\|b" in body and "`f.py:3`" in body and "FAIL" in body


class _Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False


def test_call_anthropic_request_shape(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    seen = {}

    def opener(req, timeout):
        seen["headers"] = dict(req.header_items())
        seen["body"] = json.loads(req.data)
        if "n" not in seen:
            seen["n"] = 1
            raise urllib.error.HTTPError(req.full_url, 529, "overloaded", {}, None)
        return _Resp(json.dumps(fake_response([])).encode())

    out = call_anthropic("sk-test", "claude-sonnet-4-5", 100, "sys", "user", opener=opener)
    assert out["usage"]["input_tokens"] == 1000
    assert seen["headers"]["X-api-key"] == "sk-test"
    assert seen["headers"]["Anthropic-version"] == "2023-06-01"
    assert seen["body"]["model"] == "claude-sonnet-4-5" and seen["body"]["system"] == "sys"


def test_call_anthropic_no_retry_on_401():
    calls = []

    def opener(req, timeout):
        calls.append(1)
        raise urllib.error.HTTPError(req.full_url, 401, "unauthorized", {}, None)

    with pytest.raises(urllib.error.HTTPError):
        call_anthropic("bad", "m", 1, "s", "u", opener=opener)
    assert len(calls) == 1
