module Boukensha
  # Static model → capability table.
  #
  # `context_window` is a known *model* fact — the physical input ceiling — not a
  # value the user sets. The agent looks it up from its configured model id; the
  # user never configures it in settings.yaml. Unknown models fall back to a
  # conservative default so an unrecognised id can't silently assume a huge window.
  module Models
    # Every entry's context_window is copied from that model's own backend
    # MODELS table (Backends::Anthropic::MODELS etc.) -- this table used to
    # both disagree with those tables (claude-opus-4-8/claude-sonnet-4-6
    # listed at 200_000 here vs the real 1_000_000 in backends/anthropic.rb)
    # and omit every non-Anthropic model entirely, so any OpenAI/Gemini/
    # Ollama model silently fell back to DEFAULT_CONTEXT_WINDOW (32_000) --
    # a real, confirmed bug (found by code review): compaction fired 5x-30x
    # too early and destroyed real conversation history well before the
    # actual window was under any pressure. Fixed by making this table a
    # complete, accurate mirror of every backend's own MODELS -- not by
    # deriving context_window from the backend at lookup time (this
    # method only receives a model id, not which backend it belongs to;
    # Boukensha.run/repl resolve context_window from model alone, before
    # backend is resolved -- reordering that is a bigger change than this
    # bug needs).
    TABLE = {
      "claude-opus-4-8"       => { context_window: 1_000_000 },
      "claude-sonnet-4-6"     => { context_window: 1_000_000 },
      "claude-haiku-4-5"      => { context_window: 200_000 },
      "claude-sonnet-5"       => { context_window: 1_000_000 },
      "gpt-5.5"               => { context_window: 1_000_000 },
      "gpt-5.4-mini"          => { context_window: 400_000 },
      "gpt-5.4-nano"          => { context_window: 400_000 },
      "gemini-3.5-flash"      => { context_window: 1_048_576 },
      "gemini-3.1-flash-lite" => { context_window: 1_048_576 },
      "gemma4:e4b"            => { context_window: 128_000 },
      "gemma4:31b-cloud"      => { context_window: 256_000 },
      "kimi-k2.5:cloud"       => { context_window: 256_000 },
      "minimax-m3:cloud"      => { context_window: 512_000 },
    }.freeze

    DEFAULT_CONTEXT_WINDOW = 32_000

    def self.context_window(model)
      TABLE.dig(model.to_s, :context_window) || DEFAULT_CONTEXT_WINDOW
    end
  end
end
