require_relative "tool"
require_relative "message"

module Boukensha
  class Context
    attr_reader :task, :system, :messages, :tools

    def initialize(task:, system: nil)
      @task         = task
      @system       = system
      @messages     = []
      @tools        = {}
    end

    def register_tool(tool)
      # Normalize to a string key regardless of caller -- a Tool built with
      # a symbol name (e.g. Tool.new(:look, ...)) would otherwise land in
      # @tools under a symbol key, silently breaking any string-keyed
      # lookup for that tool even though tool_count reports it as present.
      # Backported 2026-07-21 from the fix in 02_the_registry, where the
      # new Registry class made this reachable/demonstrable; latent here
      # (no Registry yet in this step) but the same underlying bug.
      @tools[tool.name.to_s] = tool
    end

    def add_message(role, content, tool_use_id: nil)
      @messages << Message.new(role, content, tool_use_id)
    end

    def tool_count = @tools.size
    def turn_count = @messages.size

    def to_s
      "#<Context task=#{task&.task_name} turns=#{turn_count} tools=#{tool_count}>"
    end
  end
end