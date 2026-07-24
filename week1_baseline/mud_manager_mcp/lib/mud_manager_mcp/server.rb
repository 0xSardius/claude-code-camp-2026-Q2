require "mcp"
require "mud_manager"

# MCP server wrapping week0_explore/mud_manager's Session/Primitives,
# exposing MUD gameplay tools over MCP. See
# docs/plans/mud_manager_mcp -- additive only: this is a NEW piece,
# not a replacement for week1_baseline/ruby|python/10_standard_tool_library's
# Tools::Mud, which stay exactly as they are.
#
# One MudManager::Session is opened at server startup (connect!) and
# shared by every tool call -- the same "log in once, reuse the connection"
# design as Tools::Mud, just now living in a process that outlives any
# single client's lifetime (the actual point of this exercise).
module MudManagerMcp
  HOST = ENV.fetch("MUD_HOST", "localhost")
  PORT = ENV.fetch("MUD_PORT", "4000").to_i
  NAME = ENV.fetch("MUD_NAME", "boukensha")
  PASSWORD = ENV.fetch("MUD_PASSWORD") { abort "mud_manager_mcp: MUD_PASSWORD env var is required" }

  SESSION = MudManager::Session.new(host: HOST, port: PORT)
  P = MudManager::Primitives

  # Serializes every command sent to the shared SESSION. Puma runs with
  # its default multi-threaded config, and without this, two concurrent
  # MCP tool calls' drain/send_command/read_until_prompt sequences can
  # interleave on the same socket/buffer -- one thread's command gets
  # another thread's response, silently, with no error raised. Found by
  # code review, not live testing (needs real concurrent callers to
  # trigger). A MUD session can only do one thing at a time anyway, so
  # serializing here matches the actual resource's semantics, not just a
  # workaround.
  SESSION_MUTEX = Mutex.new

  def self.build_server
    # define_tool's block is instance_exec'd against an anonymous Tool
    # subclass (self changes), so module-level `def self.foo` methods are
    # NOT reachable by a bare call from inside the block -- confirmed the
    # hard way (NoMethodError) before switching to this. Local lambdas
    # captured as closures work regardless of self, since Ruby closures
    # capture lexically -- same pattern Tools::Mud.register already uses
    # (send_cmd/guard/oops as local lambdas, not module methods).
    send_cmd = lambda do |command|
      SESSION_MUTEX.synchronize do
        SESSION.drain
        SESSION.send_command(command)
        SESSION.read_until_prompt
      end
    end

    guard = lambda do
      "error: not connected — call mud_connect first" unless SESSION.open?
    end

    text_response = lambda do |str|
      MCP::Tool::Response.new([{ type: "text", text: str.to_s }])
    end

    # Shared shape for every tool that sends one Primitives command and
    # returns the result: guard -> build the command -> send it -> wrap
    # errors. Was copy-pasted across 8 tool bodies (each only rescuing
    # ArgumentError, and `flee` not even that) -- found by code review.
    # Rescuing MudManager::Session::Error here too (not just
    # ArgumentError) matters for real: the MUD connection can drop
    # mid-call (documented as routine, 10s-few min, in this project's
    # CLAUDE.md), which previously surfaced as a raw JSON-RPC "Internal
    # error" instead of this file's normal "error: ..." text response.
    run_primitive = lambda do |&build_command|
      g = guard.call
      next text_response.call(g) if g
      begin
        text_response.call(send_cmd.call(build_command.call))
      rescue ArgumentError, MudManager::Session::Error => e
        text_response.call("error: #{e.message}")
      end
    end

    server = MCP::Server.new(
      name: "mud_manager_mcp",
      title: "MudManager MCP Server",
      version: "0.1.0",
      tools: []
    )

    server.define_tool(
      name: "mud_connect",
      description: "Open the connection to the MUD server and log in with the configured character name and password. Safe to call when already connected (returns current status instead of reconnecting).",
      input_schema: { properties: {}, required: [] }
    ) do |**_args|
      if SESSION.open?
        text_response.call("already connected to #{SESSION.host}:#{SESSION.port}")
      else
        begin
          SESSION.open
          welcome = SESSION.login(NAME, PASSWORD)
          text_response.call("connected to #{SESSION.host}:#{SESSION.port}\n#{welcome}")
        rescue MudManager::Session::Error => e
          # A failed login (e.g. wrong password) leaves the socket open
          # with Session#open? still true -- open? only reflects "socket
          # connected," not "successfully authenticated." Without closing
          # here, every future guard.call/mud_connect check would see
          # open? == true and treat the session as usable, permanently
          # stuck sending game commands into an unauthenticated
          # login/menu prompt with no way to retry short of restarting
          # the process. Closing restores the invariant the rest of this
          # file assumes: open? == true means logged in, not just
          # socket-connected. Found by code review.
          SESSION.close if SESSION.open?
          text_response.call("error: #{e.message}")
        end
      end
    end

    server.define_tool(
      name: "mud_disconnect",
      description: "Close the connection to the MUD server gracefully.",
      input_schema: { properties: {}, required: [] }
    ) do |**_args|
      if SESSION.open?
        SESSION.close
        text_response.call("disconnected")
      else
        text_response.call("already disconnected")
      end
    end

    server.define_tool(
      name: "mud_status",
      description: "Return whether the MUD session is currently connected.",
      input_schema: { properties: {}, required: [] }
    ) do |**_args|
      text_response.call(SESSION.open? ? "connected to #{SESSION.host}:#{SESSION.port}" : "disconnected")
    end

    server.define_tool(
      name: "look",
      description: "Look at the current room or at a specific target. Call with NO arguments to describe the current room (do NOT pass target: 'room'). Pass a target to inspect a specific item, mob, or player (e.g. target: 'sword'). Use preposition 'in' to look inside a container, 'at' to inspect something, or a direction (north/east/south/west/up/down) to peek into an adjacent room.",
      input_schema: {
        properties: {
          target: { type: "string", description: "Item, mob, or player name to inspect. Omit entirely to describe the current room." },
          preposition: { type: "string", description: "Preposition: in, at, north, east, south, west, up, down (optional)" }
        },
        required: []
      }
    ) do |target: nil, preposition: nil, **_args|
      run_primitive.call { P.look(target: target, preposition: preposition) }
    end

    server.define_tool(
      name: "examine",
      description: "Examine a target in detail (more verbose than look).",
      input_schema: { properties: { target: { type: "string", description: "The item, mob, or player to examine" } }, required: ["target"] }
    ) do |target:, **_args|
      run_primitive.call { P.examine(target) }
    end

    server.define_tool(
      name: "check",
      description: "Query information about your character or surroundings. Kinds: score, inventory, equipment, gold, exits, time, weather, levels, wimpy, toggle, where.",
      input_schema: { properties: { kind: { type: "string", description: "What to check: score | inventory | equipment | gold | exits | time | weather | levels | wimpy | toggle | where" } }, required: ["kind"] }
    ) do |kind:, **_args|
      run_primitive.call { P.info_self(kind) }
    end

    server.define_tool(
      name: "consider",
      description: "Assess a mob's relative strength before engaging in combat. Returns a phrase such as 'You could kill it easily' or 'Death awaits you'. Always consider before attacking an unknown mob.",
      input_schema: { properties: { target: { type: "string", description: "Name of the mob to consider" } }, required: ["target"] }
    ) do |target:, **_args|
      run_primitive.call { P.consider(target) }
    end

    server.define_tool(
      name: "move",
      description: "Move in a compass direction or up/down.",
      input_schema: { properties: { direction: { type: "string", description: "Direction: north | east | south | west | up | down" } }, required: ["direction"] }
    ) do |direction:, **_args|
      run_primitive.call { P.move(direction) }
    end

    server.define_tool(
      name: "flee",
      description: "Attempt to flee from combat in a random available direction.",
      input_schema: { properties: {}, required: [] }
    ) do |**_args|
      run_primitive.call { P.flee }
    end

    server.define_tool(
      name: "attack",
      description: "Attack a target. Style 'kill' is the standard approach; 'murder' bypasses the mercy check; 'hit' is a one-off strike.",
      input_schema: {
        properties: {
          target: { type: "string", description: "Name of the mob or player to attack" },
          style: { type: "string", description: "Attack style: kill | hit | murder (default: kill)" }
        },
        required: ["target"]
      }
    ) do |target:, style: "kill", **_args|
      run_primitive.call { P.attack(style, target) }
    end

    server.define_tool(
      name: "get_item",
      description: "Pick up an item from the room or from a container.",
      input_schema: {
        properties: {
          item: { type: "string", description: "Name of the item to get" },
          container: { type: "string", description: "Container to get it from (optional)" },
          count: { type: "integer", description: "Number of items to get (optional)" }
        },
        required: ["item"]
      }
    ) do |item:, container: nil, count: nil, **_args|
      run_primitive.call { P.get(item, container: container, count: count) }
    end

    server.define_tool(
      name: "say",
      description: "Speak or emote in the current room.",
      input_schema: {
        properties: {
          text: { type: "string", description: "What to say or emote" },
          mode: { type: "string", description: "Mode: say | emote | reply (default: say)" }
        },
        required: ["text"]
      }
    ) do |text:, mode: "say", **_args|
      run_primitive.call { P.say_local(mode, text) }
    end

    server
  end

  # Open the shared session and log in once, at server startup -- mirrors
  # Tools::Mud's auto-connect-at-registration behavior.
  def self.connect!
    SESSION.open
    SESSION.login(NAME, PASSWORD)
    warn "[mud_manager_mcp] connected to #{SESSION.host}:#{SESSION.port} as #{NAME}"
  rescue MudManager::Session::Error => e
    # Same close-on-failed-login fix as mud_connect above -- otherwise a
    # bad MUD_PASSWORD at startup leaves the socket open-but-unauthenticated
    # forever, with every tool call's guard.call silently treating it as
    # usable.
    SESSION.close if SESSION.open?
    warn "[mud_manager_mcp] MUD auto-connect failed: #{e.message} — call mud_connect manually"
  end
end
