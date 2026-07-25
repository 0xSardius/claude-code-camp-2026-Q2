module Boukensha
  Tool = Struct.new(:name, :description, :parameters, :block) do
    def to_s
      "#<Tool name=#{name} description=#{description.to_s[0..40]} params=#{parameters.keys}>"
    end

    # Which of `parameters`'s keys are actually required, determined by
    # introspecting the registered block's own keyword-argument defaults
    # (:keyreq = no default = required; :key = has a default = optional).
    # Backends use this for to_tools' JSON-schema `required:` list instead
    # of listing every declared property as required regardless of the
    # block's actual signature -- a real bug found by code review (e.g.
    # look's `|target: nil, preposition: nil|` block makes both optional,
    # but every backend's to_tools previously marked both required
    # unconditionally). Fixed in 10_standard_tool_library/11_tui/12_context
    # only -- not backported further into 03-09, which carry the same
    # long-standing bug undisturbed (see docs/plans/python_port/12_context).
    def required_params
      return [] unless block

      block.parameters.select { |type, _name| type == :keyreq }.map { |_type, name| name.to_s }
    end
  end
end
