# The API Client (Python)

Python port of [`week1_baseline/ruby/04_api_client`](../../ruby/04_api_client)
— see [`docs/plans/python_port/04_api_client`](../../../docs/plans/python_port/04_api_client)
for the port plan and decisions. Literal mirror of the Ruby architecture,
running alongside it against the same `.boukensha/` config directory.

The API Client takes the payload assembled by `PromptBuilder` and sends it
to the API. One HTTP POST, one response. No tool loop yet — just proving
the round trip works.

## New Files

| File | Description |
|---|---|
| `boukensha/client.py` | Makes the HTTP request and parses the response |

## How It Works

```
PromptBuilder
      ↓
Client
      ↓
POST to API endpoint
      ↓
Raw JSON response
```

## boukensha.Client

| Method | Description |
|---|---|
| `call(*, max_output_tokens=1024)` | POSTs the payload and returns the parsed JSON response |

Ruby's `Net::HTTP#request` always returns a response object regardless of
status code — the caller decides success/failure by inspecting
`response.code`. Python's `urllib.request.urlopen` instead *raises*
`urllib.error.HTTPError` for any non-2xx/3xx status — but `HTTPError` is
deliberately designed to double as a response object (`.code`, `.read()`),
so `Client.call` catches it and treats it as "the response, just not a
successful one," converging on the same uniform shape Ruby has. Genuine
connection-level failures (never got a response at all — DNS, timeouts,
connection reset) raise `urllib.error.URLError` or a handful of socket/ssl
exceptions, mirroring Ruby's `TRANSIENT_ERRORS` list.

Retry/backoff behavior is unchanged from Ruby: `RETRYABLE_STATUS_CODES =
{408, 409, 429, 500, 502, 503, 504}`, `MAX_RETRIES = 3` (4 total attempts
before giving up), exponential backoff (`BASE_RETRY_DELAY * 2^(attempt-1)`).

## Task Configuration

This step uses the task-based configuration introduced in the earlier
baseline steps:

```yaml
tasks:
  player:
    provider: anthropic
    model: claude-sonnet-5
    prompt_override:
      system: true
```

When `prompt_override.system` is true, Boukensha reads
`.boukensha/prompts/player/system.md`. Otherwise it falls back to this
step's shipped `prompts/system.md`.

Each backend validates the configured model at construction time.
Unsupported model names raise `UnsupportedModelError`, and supported models
expose backend-owned metadata such as `context_window`, `usage_unit`, and
token cost estimates for later logging steps.

## No Dependencies

`Client` uses Python's standard `urllib.request` module. No third-party
HTTP libraries. This is intentional — the HTTP call itself is trivial and
should be visible, not hidden behind a library (matches the Ruby version's
`net/http`-only decision).

## What the Response Looks Like

The raw response shape differs between backends. This is what you get back
from `client.call()` before any processing:

### Anthropic
```json
{
  "id": "msg_01XY",
  "type": "message",
  "role": "assistant",
  "content": [
    { "type": "text", "text": "Sure, let me read that file." }
  ],
  "stop_reason": "end_turn",
  "usage": { "input_tokens": 42, "output_tokens": 18 }
}
```

### Ollama
```json
{
  "model": "llama3.2",
  "message": {
    "role": "assistant",
    "content": "Sure, let me read that file."
  },
  "done_reason": "stop",
  "done": true
}
```

When the model wants to call a tool the response looks different. Anthropic
uses `stop_reason: "tool_use"` and adds a `tool_use` block to `content`.
Ollama adds a `tool_calls` array to `message`. Handling those differences
is the job of step 5 — the Agent Loop.

## Considerations

**The client raises `ApiError` on failure.** A non-2xx response means
something went wrong — bad API key, malformed payload, server error.
BOUKENSHA surfaces this explicitly rather than returning a confusing `None`
or partial response.

**SSL is handled automatically.** Python's `urlopen` picks HTTP vs. HTTPS
from the URL scheme automatically and verifies peer certificates against
the system CA store by default — no equivalent to Ruby's explicit
`verify_mode`/`ca_file` setup is needed.

**This step's acceptance test is not a byte-diff.** Every prior step
compared Ruby and Python launcher output byte-for-byte. A live API response
includes a fresh response ID and freshly-generated model text on every
call, so that's structurally impossible here. Parity was instead verified
with: one real successful round-trip per language (same JSON response key
shape, not identical values), one deliberately-invalid-key round-trip per
language (a real, free 401 — same `ApiError` message shape), and direct
code review against the Ruby source for the retry/backoff logic itself
(not live-network-testable without deliberately flaky infrastructure). See
the port plan's acceptance-test section for the full reasoning.

## Setup

```bash
cd week1_baseline/python/04_api_client
uv sync
```

## Run Example

```sh
./week1_baseline/bin/04_api_client_python
```

Needs a real provider API key in the environment (e.g. `ANTHROPIC_API_KEY`)
— this step makes an actual, billed API call. Verified live against
`./week1_baseline/bin/04_api_client` (the Ruby version): both complete the
round trip and return a JSON response with the same top-level key shape.
