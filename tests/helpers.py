import json


def fake_response(findings, input_tokens=1000, output_tokens=200):
    return {"content": [{"type": "text", "text": json.dumps({"findings": findings})}],
            "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens}}


class RecordingCaller:
    """Stands in for the Anthropic API."""
    def __init__(self, *responses):
        self.responses = list(responses)
        self.prompts = []

    def __call__(self, api_key, model, max_tokens, system, user):
        self.prompts.append(user)
        r = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(r, Exception):
            raise r
        return r


class FakePlatform:
    def __init__(self, diff):
        self.diff, self.summary, self.inline, self.status = diff, None, None, None

    def get_diff(self):
        if isinstance(self.diff, Exception):
            raise self.diff
        return self.diff

    def post_summary(self, body):
        self.summary = body

    def post_inline(self, findings):
        self.inline = findings

    def set_status(self, passed, desc):
        self.status = (passed, desc)
