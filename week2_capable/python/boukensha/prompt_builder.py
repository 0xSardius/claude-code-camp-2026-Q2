"""Port of week1_baseline/ruby/06_the_logger/lib/boukensha/prompt_builder.rb --
adds a `backend` reader (Ruby: attr_reader :backend), needed by
Agent#log_response's @builder.backend call (see
docs/plans/python_port/06_the_logger)."""


class PromptBuilder:
    def __init__(self, context, backend):
        self._context = context
        self._backend = backend

    @property
    def backend(self):
        return self._backend

    def to_messages(self):
        return self._backend.to_messages(self._context.system, self._context.messages)

    def to_tools(self):
        return self._backend.to_tools(self._context.tools)

    def to_api_payload(self, *, max_output_tokens=1024, tools=None):
        return self._backend.to_payload(self._context, max_output_tokens=max_output_tokens, tools=tools)

    def parse_response(self, response):
        return self._backend.parse_response(response)

    def headers(self):
        return self._backend.headers()

    def url(self):
        return self._backend.url()
