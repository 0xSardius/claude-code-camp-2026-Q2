require_relative "tool"
require_relative "message"

module Boukensha
  class Context
    attr_reader :system, :messages, :tools, :context_window, :working_dir,
                :turn_tokens, :compaction_threshold
    attr_accessor :current_tokens

    def initialize(system:, context_window: 200_000, working_dir: nil, compaction_threshold: 0.85)
      @system               = system
      @context_window       = context_window
      @working_dir          = working_dir ? File.expand_path(working_dir) : nil
      @compaction_threshold = compaction_threshold
      @messages             = []
      @tools                = {}
      @current_tokens       = 0
      @turn_tokens          = 0
    end

    # Normalize to a string key regardless of caller -- see docs/plans/python_port
    # for the full history (13th occurrence of this regression).
    def register_tool(tool)
      @tools[tool.name.to_s] = tool
    end

    def add_message(role, content, tool_use_id: nil)
      @messages << Message.new(role, content, tool_use_id)
    end

    # Update the known context size from the last API response's input_tokens.
    def update_tokens(n)
      @current_tokens = n.to_i
    end

    # Reset the cumulative per-turn spend counter. Called at the top of a turn.
    def reset_turn_tokens
      @turn_tokens = 0
    end

    # Add one API call's input+output tokens to the cumulative per-turn total.
    # This is the spend budget — distinct from current_tokens (window pressure).
    def add_turn_tokens(input, output)
      @turn_tokens += input.to_i + output.to_i
    end

    # Fraction of the context window currently in use (0.0–1.0).
    def usage_fraction
      @context_window > 0 ? @current_tokens.to_f / @context_window : 0.0
    end

    # Integer percentage (0–100).
    def usage_pct
      (usage_fraction * 100).round
    end

    # True when we should compact before the next API call. Defaults to the
    # configured compaction_threshold (a fraction of context_window).
    def needs_compaction?(threshold: compaction_threshold)
      usage_fraction >= threshold
    end

    # Drop the oldest 40% of messages to free space, keeping at least 2.
    # Resets current_tokens to 0 (will be updated by the next API response).
    # Returns the number of messages dropped.
    def compact_messages!(target_fraction: 0.60)
      drop_count = [(@messages.size * 0.40).ceil, @messages.size - 2].min
      drop_count = [drop_count, 0].max
      # Never leave an orphaned tool_result as the first retained message.
      # A plain count-based cut has no idea whether it lands between a
      # tool_use and its tool_result -- if it does, the retained history
      # starts with a tool_result that has no matching tool_use anywhere
      # in the (now-truncated) conversation, which the API rejects
      # outright (400: tool_result.tool_use_id invalid / no matching
      # tool_use). Since compaction only ever trims the front and nothing
      # ever repairs the middle, one bad cut permanently poisons every
      # future call in the session -- found live (not by review or a
      # short playtest): a real multi-turn grind session hit this exactly
      # once and every turn after it failed instantly, forever, until the
      # session was restarted. Advance past any leading tool_result(s) --
      # they're orphaned by definition once their preceding tool_use is
      # dropped.
      drop_count += 1 while drop_count < @messages.size && @messages[drop_count].role == :tool_result
      @messages = @messages.drop(drop_count)
      @current_tokens = 0
      drop_count
    end

    # Drop all conversation history, keeping tools and system prompt intact.
    def clear_messages!
      @messages = []
      @current_tokens = 0
    end

    def tool_count = @tools.size
    def turn_count = @messages.size

    def to_s
      "#<Context turns=#{turn_count} tools=#{tool_count} window=#{context_window} current=#{current_tokens}>"
    end
  end
end
