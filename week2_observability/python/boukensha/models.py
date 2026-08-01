"""Port of week1_baseline/ruby/12_context/lib/boukensha/models.rb -- a
static model -> capability table. context_window is a known *model* fact,
not a value the user sets; the agent looks it up from its configured
model id. Unknown models fall back to a conservative default.

Every entry's context_window is copied from that model's own backend
MODELS table (backends/anthropic.py's MODELS, etc.) -- this table used to
both disagree with those tables (claude-opus-4-8/claude-sonnet-4-6 listed
at 200_000 here vs the real 1_000_000 in backends/anthropic.py) and omit
every non-Anthropic model entirely, so any OpenAI/Gemini/Ollama model
silently fell back to DEFAULT_CONTEXT_WINDOW (32_000) -- a real, confirmed
bug (found by code review, fixed in Ruby first): compaction fired 5x-30x
too early and destroyed real conversation history well before the actual
window was under any pressure. Fixed by making this table a complete,
accurate mirror of every backend's own MODELS -- not by deriving
context_window from the backend at lookup time (context_window() only
receives a model id, not which backend it belongs to; Boukensha.run/repl
resolve context_window from model alone, before backend is resolved --
reordering that is a bigger change than this bug needs).
"""

TABLE = {
    "claude-opus-4-8": {"context_window": 1_000_000},
    "claude-sonnet-4-6": {"context_window": 1_000_000},
    "claude-haiku-4-5": {"context_window": 200_000},
    "claude-sonnet-5": {"context_window": 1_000_000},
    "gpt-5.5": {"context_window": 1_000_000},
    "gpt-5.4-mini": {"context_window": 400_000},
    "gpt-5.4-nano": {"context_window": 400_000},
    "gemini-3.5-flash": {"context_window": 1_048_576},
    "gemini-3.1-flash-lite": {"context_window": 1_048_576},
    "gemma4:e4b": {"context_window": 128_000},
    "gemma4:31b-cloud": {"context_window": 256_000},
    "kimi-k2.5:cloud": {"context_window": 256_000},
    "minimax-m3:cloud": {"context_window": 512_000},
}

DEFAULT_CONTEXT_WINDOW = 32_000


def context_window(model):
    entry = TABLE.get(str(model))
    return entry["context_window"] if entry is not None else DEFAULT_CONTEXT_WINDOW
