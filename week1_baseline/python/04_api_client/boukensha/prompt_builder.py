"""Port of week1_baseline/ruby/03_prompt_builder/lib/boukensha/prompt_builder.rb."""


class PromptBuilder:
    def __init__(self, context, backend):
        self._context = context
        self._backend = backend

    def to_messages(self):
        return self._backend.to_messages(self._context.system, self._context.messages)

    def to_tools(self):
        return self._backend.to_tools(self._context.tools)

    def to_api_payload(self, *, max_output_tokens=1024):
        return self._backend.to_payload(self._context, max_output_tokens=max_output_tokens)

    def headers(self):
        return self._backend.headers()

    def url(self):
        return self._backend.url()
