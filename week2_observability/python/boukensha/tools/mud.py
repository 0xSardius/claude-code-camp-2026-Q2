"""Port of week1_baseline/ruby/10_standard_tool_library/lib/boukensha/tools/mud.rb --
registers MUD-gameplay tools against a registry. A single
mud_session.Session is created when the tools are registered and shared by
every tool via closure -- the agent logs in once and reuses the connection
for all subsequent tool calls.
"""
from __future__ import annotations

import sys

from .. import mud_primitives as p
from ..mud_session import Session, SessionError


def register(registry, *, host="localhost", port=4000, name, password):
    session = Session(host=host, port=port)

    # Send a primitive command and return the MUD's response text. We
    # drain any stale buffered bytes (leftover login output, async ticks,
    # etc.) before sending so read_until_prompt sees only fresh data
    # produced by this command, then wait for CircleMUD's "> " prompt.
    def send_cmd(command):
        session.drain()
        session.send_command(command)
        return session.read_until_prompt()

    # Returns an error string if the session is not open so the agent can
    # decide whether to call mud_connect first, else None.
    def guard():
        return None if session.is_open() else "error: not connected — call mud_connect first"

    # ── Connection ─────────────────────────────────────────────────────

    def mud_connect():
        if session.is_open():
            return f"already connected to {session.host}:{session.port}"
        try:
            session.open()
            welcome = session.login(name, password)
            return f"connected to {session.host}:{session.port}\n{welcome or ''}"
        except SessionError as e:
            return f"error: {e}"

    def mud_disconnect():
        if session.is_open():
            session.close()
            return "disconnected"
        return "already disconnected"

    def mud_status():
        return f"connected to {session.host}:{session.port}" if session.is_open() else "disconnected"

    # ── Perception ──────────────────────────────────────────────────────

    def look(target=None, preposition=None):
        g = guard()
        if g:
            return g
        try:
            return send_cmd(p.look(target=target, preposition=preposition))
        except ValueError as e:
            return f"error: {e}"

    def examine(target):
        g = guard()
        if g:
            return g
        try:
            return send_cmd(p.examine(target))
        except ValueError as e:
            return f"error: {e}"

    def check(kind):
        g = guard()
        if g:
            return g
        try:
            return send_cmd(p.info_self(kind))
        except ValueError as e:
            return f"error: {e}"

    # ── Movement ────────────────────────────────────────────────────────

    def move(direction):
        g = guard()
        if g:
            return g
        try:
            return send_cmd(p.move(direction))
        except ValueError as e:
            return f"error: {e}"

    def flee():
        g = guard()
        if g:
            return g
        return send_cmd(p.flee())

    def set_position(position):
        g = guard()
        if g:
            return g
        try:
            return send_cmd(p.set_position(position))
        except ValueError as e:
            return f"error: {e}"

    def track(target):
        g = guard()
        if g:
            return g
        try:
            return send_cmd(p.track(target))
        except ValueError as e:
            return f"error: {e}"

    # ── Combat ──────────────────────────────────────────────────────────

    def attack(target, style="kill"):
        g = guard()
        if g:
            return g
        try:
            return send_cmd(p.attack(style, target))
        except ValueError as e:
            return f"error: {e}"

    def skill_strike(skill, target):
        g = guard()
        if g:
            return g
        try:
            return send_cmd(p.skill_strike(skill, target))
        except ValueError as e:
            return f"error: {e}"

    def consider(target):
        g = guard()
        if g:
            return g
        try:
            return send_cmd(p.consider(target))
        except ValueError as e:
            return f"error: {e}"

    # ── Communication ───────────────────────────────────────────────────

    def say(text, mode="say"):
        g = guard()
        if g:
            return g
        try:
            return send_cmd(p.say_local(mode, text))
        except ValueError as e:
            return f"error: {e}"

    def tell(target, text, mode="tell"):
        g = guard()
        if g:
            return g
        try:
            return send_cmd(p.say_targeted(mode, target, text))
        except ValueError as e:
            return f"error: {e}"

    def channel_say(channel, text):
        g = guard()
        if g:
            return g
        try:
            return send_cmd(p.say_channel(channel, text))
        except ValueError as e:
            return f"error: {e}"

    # ── Inventory & equipment ────────────────────────────────────────────

    def get_item(item, container=None, count=None):
        g = guard()
        if g:
            return g
        try:
            return send_cmd(p.get(item, container=container, count=count))
        except ValueError as e:
            return f"error: {e}"

    def drop_item(item, mode="drop", count=None):
        g = guard()
        if g:
            return g
        try:
            return send_cmd(p.drop(mode, item, count=count))
        except ValueError as e:
            return f"error: {e}"

    def put_item(item, container, count=None):
        g = guard()
        if g:
            return g
        try:
            return send_cmd(p.put(item, container, count=count))
        except ValueError as e:
            return f"error: {e}"

    def equip_item(item, action, body_loc=None):
        g = guard()
        if g:
            return g
        try:
            return send_cmd(p.equip(action, item, body_loc=body_loc))
        except ValueError as e:
            return f"error: {e}"

    def consume_item(item, mode="eat"):
        g = guard()
        if g:
            return g
        try:
            return send_cmd(p.consume(mode, item))
        except ValueError as e:
            return f"error: {e}"

    # ── Magic ────────────────────────────────────────────────────────────

    def cast_spell(spell, target=None):
        g = guard()
        if g:
            return g
        try:
            return send_cmd(p.cast(spell, target=target))
        except ValueError as e:
            return f"error: {e}"

    def use_magic_item(item, mode, target_args=None):
        g = guard()
        if g:
            return g
        try:
            return send_cmd(p.use_magic_item(mode, item, target_args=target_args))
        except ValueError as e:
            return f"error: {e}"

    # ── Utility ──────────────────────────────────────────────────────────

    def shop(action, args=None):
        g = guard()
        if g:
            return g
        try:
            return send_cmd(p.shop(action, args=args))
        except ValueError as e:
            return f"error: {e}"

    def practice(skill=None):
        g = guard()
        if g:
            return g
        return send_cmd(p.practice(skill))

    def save_character():
        g = guard()
        if g:
            return g
        return send_cmd(p.save_char())

    def send_raw(command):
        g = guard()
        if g:
            return g
        session.send_command(command)
        return session.read_until_quiet()

    registry.tool("mud_connect", description="Open the connection to the MUD server and log in with the configured character name and password. Safe to call when already connected (returns current status instead of reconnecting).", parameters={}, block=mud_connect)
    registry.tool("mud_disconnect", description="Close the connection to the MUD server gracefully.", parameters={}, block=mud_disconnect)
    registry.tool("mud_status", description="Return whether the MUD session is currently connected.", parameters={}, block=mud_status)
    registry.tool(
        "look",
        description="Look at the current room or at a specific target. Call with NO arguments to describe the current room (do NOT pass target: 'room'). Pass a target to inspect a specific item, mob, or player (e.g. target: 'sword'). Use preposition 'in' to look inside a container, 'at' to inspect something, or a direction (north/east/south/west/up/down) to peek into an adjacent room.",
        parameters={
            "target": {"type": "string", "description": "Item, mob, or player name to inspect. Omit entirely to describe the current room."},
            "preposition": {"type": "string", "description": "Preposition: in, at, north, east, south, west, up, down (optional)"},
        },
        block=look,
    )
    registry.tool("examine", description="Examine a target in detail (more verbose than look).", parameters={"target": {"type": "string", "description": "The item, mob, or player to examine"}}, block=examine)
    registry.tool(
        "check",
        description="Query information about your character or surroundings. Kinds: score, inventory, equipment, gold, exits, time, weather, levels, wimpy, toggle, where.",
        parameters={"kind": {"type": "string", "description": "What to check: score | inventory | equipment | gold | exits | time | weather | levels | wimpy | toggle | where"}},
        block=check,
    )
    registry.tool("move", description="Move in a compass direction or up/down.", parameters={"direction": {"type": "string", "description": "Direction: north | east | south | west | up | down"}}, block=move)
    registry.tool("flee", description="Attempt to flee from combat in a random available direction.", parameters={}, block=flee)
    registry.tool("set_position", description="Change body position. Use 'rest' or 'sleep' between fights to recover HP and mana. Must be standing to move or fight.", parameters={"position": {"type": "string", "description": "Position: stand | sit | rest | sleep | wake"}}, block=set_position)
    registry.tool("track", description="Attempt to track a mob or player by name, revealing which direction they are in. Requires the Track skill.", parameters={"target": {"type": "string", "description": "Name of the mob or player to track"}}, block=track)
    registry.tool(
        "attack",
        description="Attack a target. Style 'kill' is the standard approach; 'murder' bypasses the mercy check; 'hit' is a one-off strike.",
        parameters={
            "target": {"type": "string", "description": "Name of the mob or player to attack"},
            "style": {"type": "string", "description": "Attack style: kill | hit | murder (default: kill)"},
        },
        block=attack,
    )
    registry.tool(
        "skill_strike",
        description="Use a combat skill against a target.",
        parameters={
            "skill": {"type": "string", "description": "Skill: bash | kick | backstab | rescue | assist"},
            "target": {"type": "string", "description": "Name of the mob or player"},
        },
        block=skill_strike,
    )
    registry.tool(
        "consider",
        description="Assess a mob's relative strength before engaging in combat. Returns a phrase such as 'You could kill it easily' or 'Death awaits you'. Always consider before attacking an unknown mob.",
        parameters={"target": {"type": "string", "description": "Name of the mob to consider"}},
        block=consider,
    )
    registry.tool(
        "say",
        description="Speak or emote in the current room.",
        parameters={
            "text": {"type": "string", "description": "What to say or emote"},
            "mode": {"type": "string", "description": "Mode: say | emote | reply (default: say)"},
        },
        block=say,
    )
    registry.tool(
        "tell",
        description="Send a private message to a specific player.",
        parameters={
            "target": {"type": "string", "description": "Player name to message"},
            "text": {"type": "string", "description": "The message"},
            "mode": {"type": "string", "description": "Mode: tell | whisper | ask (default: tell)"},
        },
        block=tell,
    )
    registry.tool(
        "channel_say",
        description="Broadcast a message over a global channel.",
        parameters={
            "channel": {"type": "string", "description": "Channel: shout | gossip | auction | grats | holler"},
            "text": {"type": "string", "description": "The message to broadcast"},
        },
        block=channel_say,
    )
    registry.tool(
        "get_item",
        description="Pick up an item from the room or from a container.",
        parameters={
            "item": {"type": "string", "description": "Name of the item to get"},
            "container": {"type": "string", "description": "Container to get it from (optional)"},
            "count": {"type": "integer", "description": "Number of items to get (optional)"},
        },
        block=get_item,
    )
    registry.tool(
        "drop_item",
        description="Drop, donate, or junk an item.",
        parameters={
            "item": {"type": "string", "description": "Name of the item"},
            "mode": {"type": "string", "description": "Mode: drop | donate | junk (default: drop)"},
            "count": {"type": "integer", "description": "Number of items (optional)"},
        },
        block=drop_item,
    )
    registry.tool(
        "put_item",
        description="Put an item into a container.",
        parameters={
            "item": {"type": "string", "description": "Name of the item to put"},
            "container": {"type": "string", "description": "Name of the container"},
            "count": {"type": "integer", "description": "Number of items (optional)"},
        },
        block=put_item,
    )
    registry.tool(
        "equip_item",
        description="Wear, wield, hold, grab, or remove an item.",
        parameters={
            "item": {"type": "string", "description": "Name of the item"},
            "action": {"type": "string", "description": "Action: wear | wield | hold | grab | remove"},
            "body_loc": {"type": "string", "description": "Body location to wear on (optional, e.g. 'head', 'finger')"},
        },
        block=equip_item,
    )
    registry.tool(
        "consume_item",
        description="Eat, drink, taste, or sip a consumable item.",
        parameters={
            "item": {"type": "string", "description": "Name of the item to consume"},
            "mode": {"type": "string", "description": "Mode: eat | drink | taste | sip (default: eat)"},
        },
        block=consume_item,
    )
    registry.tool(
        "cast_spell",
        description="Cast a spell, optionally at a target.",
        parameters={
            "spell": {"type": "string", "description": "Full spell name (e.g. 'cure light wounds', 'magic missile')"},
            "target": {"type": "string", "description": "Target mob, player, or object (optional)"},
        },
        block=cast_spell,
    )
    registry.tool(
        "use_magic_item",
        description="Activate a magic item: quaff a potion, recite a scroll, or use a wand/staff.",
        parameters={
            "item": {"type": "string", "description": "Name of the item to activate"},
            "mode": {"type": "string", "description": "Mode: quaff | recite | use"},
            "target_args": {"type": "string", "description": "Optional target arguments (e.g. mob name for a wand)"},
        },
        block=use_magic_item,
    )
    registry.tool(
        "shop",
        description="Interact with a shop NPC: list stock, buy, sell, or get the value of an item.",
        parameters={
            "action": {"type": "string", "description": "Action: list | buy | sell | value | offer"},
            "args": {"type": "string", "description": "Item name or number (optional)"},
        },
        block=shop,
    )
    registry.tool("practice", description="List your known skills at a guildmaster, or practice a specific skill.", parameters={"skill": {"type": "string", "description": "Skill name to practice (omit to list all)"}}, block=practice)
    registry.tool("save_character", description="Save your character to disk so progress is not lost on disconnect.", parameters={}, block=save_character)
    registry.tool("send_raw", description="Send an arbitrary command string to the MUD and return the response. Use this as an escape hatch when no structured tool fits.", parameters={"command": {"type": "string", "description": "The raw command to send (e.g. 'who', 'help backstab')"}}, block=send_raw)

    # Auto-connect at startup so the session is ready immediately and the
    # agent doesn't need to waste a turn calling mud_connect first.
    try:
        session.open()
        session.login(name, password)
    except SessionError as e:
        print(f"[boukensha] MUD auto-connect failed: {e} — call mud_connect manually", file=sys.stderr)
