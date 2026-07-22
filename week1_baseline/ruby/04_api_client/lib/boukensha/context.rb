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
      # Normalize to a string key regardless of caller. Registry#tool always
      # passes a string (name.to_s), but register_tool is still public and
      # callable directly (see this step's README Considerations) -- a Tool
      # built with a symbol name (e.g. Tool.new(:look, ...)) registered that
      # way would otherwise land in @tools under a symbol key, silently
      # breaking Registry#dispatch's string-keyed lookup for that tool even
      # though tool_count reports it as present. Same fix as 02_the_registry
      # (and its 01_struct_skeleton/03_prompt_builder backports) -- reapplied
      # here since this file's copy had regressed to the unfixed version
      # (4th occurrence -- see docs/plans/python_port/04_api_client).
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
