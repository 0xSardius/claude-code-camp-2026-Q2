"""Port of week1_baseline/ruby/08_the_repl_loop/lib/boukensha/client.rb --
adds a friendlier message for 401 responses specifically (see
docs/plans/python_port/08_the_repl_loop), otherwise unchanged since
05_agent_loop.

Ruby's Net::HTTP#request always returns a response object regardless of
status code (2xx or otherwise) -- the caller decides success/failure by
inspecting response.code and response.is_a?(Net::HTTPSuccess). It also
reads status, headers, AND body as one atomic call, all inside the single
begin/rescue that catches transient failures.

Python's urllib.request.urlopen instead *raises* urllib.error.HTTPError for
any non-2xx/3xx status, and separates "get the response" from "read the
body" into two steps. This isn't a fidelity gap: HTTPError is deliberately
designed to double as a response object (.code, .read(), .close()), so
catching it and treating it as "the response, just not a 2xx one" gets back
to the same uniform shape Ruby has -- but status AND body must both be
pulled out inside the same try/except that catches TRANSIENT_ERRORS (not
after it), or a connection reset mid-body-read would escape unretried and
unwrapped, unlike Ruby's atomic read. The response is also explicitly
closed on every path (success, terminal error, and before each retry) via
`finally` -- Ruby's Net::HTTP doesn't need this because a one-off
`http.request(...)` call closes its connection when it returns; an
unclosed urllib response leaks the underlying socket.
"""
import json
import ssl
import time
import urllib.error
import urllib.request

from .errors import ApiError


class Client:
    RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}

    # Ruby's TRANSIENT_ERRORS is connection/protocol-level failures that
    # never produced an HTTP response at all (EOFError, ECONNRESET,
    # ECONNREFUSED, open/read timeouts, SSL errors, SocketError,
    # Timeout::Error) -- deliberately NOT overlapping with HTTPError below,
    # which represents a real (if unsuccessful) response.
    TRANSIENT_ERRORS = (
        EOFError,
        ConnectionResetError,
        ConnectionRefusedError,
        TimeoutError,
        ssl.SSLError,
        urllib.error.URLError,
    )
    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 0.5

    # Seconds to wait on one HTTP request before giving up on it.
    #
    # urlopen() without this argument blocks FOREVER -- Python has no default
    # socket timeout. That is what hung a run on 2026-08-05: the process sat on
    # a stalled connection for 22 hours, used zero CPU, wrote nothing to the log
    # and never crashed. Every MUD read in this codebase already carries a
    # deadline; the API call was the one blocking operation without one.
    #
    # A hang is worse than a crash for an unattended loop. A crash is visible
    # and the retry logic below already handles it: a socket timeout raises
    # TimeoutError, which is in TRANSIENT_ERRORS, so a stalled request now
    # becomes an ordinary retry instead of a silent stop.
    #
    # 120s is deliberately generous. A long turn with a big prompt can take
    # tens of seconds, and this is a backstop against hanging, not a latency
    # target.
    REQUEST_TIMEOUT = 120.0

    def __init__(self, builder, *, request_timeout=None):
        self._builder = builder
        self._request_timeout = (
            request_timeout if request_timeout is not None else self.REQUEST_TIMEOUT
        )

    def call(self, *, max_output_tokens=1024, tools=None):
        url = self._builder.url()
        body = json.dumps(
            self._builder.to_api_payload(max_output_tokens=max_output_tokens, tools=tools)
        ).encode("utf-8")
        request = urllib.request.Request(url, data=body, headers=self._builder.headers(), method="POST")

        attempts = 0
        status = None
        response_body = None

        while True:
            attempts += 1
            response = None
            try:
                response = urllib.request.urlopen(request, timeout=self._request_timeout)
                status = response.code
                response_body = response.read()
            except urllib.error.HTTPError as e:
                # HTTPError IS usable as a response object -- keeps this
                # branch and the success path converging on one uniform
                # "status + body" shape below, same as Ruby's Net::HTTP.
                response = e
                status = e.code
                response_body = e.read()
            except self.TRANSIENT_ERRORS as e:
                if attempts > self.MAX_RETRIES:
                    raise ApiError(
                        f"API request failed after {attempts} attempts: {type(e).__name__}: {e}"
                    )
                time.sleep(self._retry_delay(attempts))
                continue
            finally:
                if response is not None:
                    response.close()

            if self._is_retryable_status(status) and attempts <= self.MAX_RETRIES:
                time.sleep(self._retry_delay(attempts))
                continue

            break

        if not (200 <= status < 300):
            if status == 401:
                raise ApiError("authentication failed (401) — check your API key")
            suffix = "" if attempts == 1 else "s"
            raise ApiError(
                f"API request failed after {attempts} attempt{suffix} "
                f"({status}): {response_body.decode('utf-8')}"
            )

        return json.loads(response_body)

    def _is_retryable_status(self, status):
        return status in self.RETRYABLE_STATUS_CODES

    def _retry_delay(self, attempt):
        return self.BASE_RETRY_DELAY * (2 ** (attempt - 1))
