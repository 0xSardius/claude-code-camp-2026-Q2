"""Port of week1_baseline/ruby/04_api_client/lib/boukensha/client.rb.

Ruby's Net::HTTP#request always returns a response object regardless of
status code (2xx or otherwise) -- the caller decides success/failure by
inspecting response.code and response.is_a?(Net::HTTPSuccess). Python's
urllib.request.urlopen instead *raises* urllib.error.HTTPError for any
non-2xx/3xx status. This isn't a fidelity gap: HTTPError is deliberately
designed to double as a response object (.code, .read(), .headers), so
catching it and treating it as "the response, just not a 2xx one" gets
back to the same uniform shape Ruby has. Genuine connection-level failures
(never got a response at all) raise urllib.error.URLError or a handful of
socket/ssl-level exceptions -- the Python-side equivalent of Ruby's
TRANSIENT_ERRORS list.
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

    def __init__(self, builder):
        self._builder = builder

    def call(self, *, max_output_tokens=1024):
        url = self._builder.url()
        body = json.dumps(self._builder.to_api_payload(max_output_tokens=max_output_tokens)).encode("utf-8")
        request = urllib.request.Request(url, data=body, headers=self._builder.headers(), method="POST")

        attempts = 0
        response = None

        while True:
            attempts += 1
            try:
                response = urllib.request.urlopen(request)
            except urllib.error.HTTPError as e:
                # HTTPError IS usable as a response object -- keeps this
                # branch and the success path converging on one uniform
                # "response" shape below, same as Ruby's Net::HTTP.
                response = e
            except self.TRANSIENT_ERRORS as e:
                if attempts > self.MAX_RETRIES:
                    raise ApiError(
                        f"API request failed after {attempts} attempts: {type(e).__name__}: {e}"
                    )
                time.sleep(self._retry_delay(attempts))
                continue

            if self._retryable_response(response) and attempts <= self.MAX_RETRIES:
                response.close()
                time.sleep(self._retry_delay(attempts))
                continue

            break

        if not (200 <= response.code < 300):
            suffix = "" if attempts == 1 else "s"
            raise ApiError(
                f"API request failed after {attempts} attempt{suffix} "
                f"({response.code}): {response.read().decode('utf-8')}"
            )

        return json.loads(response.read())

    def _retryable_response(self, response):
        return response.code in self.RETRYABLE_STATUS_CODES

    def _retry_delay(self, attempt):
        return self.BASE_RETRY_DELAY * (2 ** (attempt - 1))
