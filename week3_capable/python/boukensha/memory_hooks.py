"""Wire the memory store into the agent's lifecycle (week2 memory M3).

This is where "the agent maintains its own knowledge" stops being a promise and
becomes a guarantee. Without these handlers, recording a room means the model
has to *choose* to call a tool — which it will do most of the time, and the
times it forgets are exactly the long chaotic turns where the map matters most.
With them, walking into a room records the room whether the model thought about
it or not.

    before_turn   load memory into the conversation; mark position as stale
    before_model  refresh position ONLY when the belief is stale (track, don't poll)
    after_tool    extract rooms, routes and vitals from whatever came back
    after_turn    re-render the human-readable player file

APPEND-ONLY. Everything these handlers add goes on the END of the message list.
Splicing into the middle would invalidate the cached prefix on every turn and
make the memory and token pillars cancel each other out exactly.
"""
from __future__ import annotations

from .hooks import Hook
from .memory import Memory
from .mud_parse import parse_practice, parse_room, parse_score, parse_status

# Tools whose replies can contain a room description.
ROOM_TOOLS = ("look", "move", "mud_connect", "flee", "track")
# Tools after which we cannot trust our idea of where we are.
POSITION_LOST_AFTER = ("flee", "mud_connect", "mud_disconnect")


class MemoryHooks:
    def __init__(self, memory, *, registry=None):
        self.memory = memory
        self.registry = registry
        # Position belief is per-process, deliberately: on a fresh start we do
        # not trust a stored position, because anything could have happened to
        # the character while we were not running.
        self._position = None
        self._moves = None
        self._needs_look = True
        self._injected_this_turn = False
        # Apply that rule to the STORE too, not just to _position. Otherwise
        # context_block, render_journal and find_route all keep serving the
        # stale stored position while this object correctly considers it
        # unknown -- and find_route would hand back a route computed from where
        # the character was last session. Found by code review.
        self.memory.clear_position()

    # ---- install ---------------------------------------------------------

    def install(self, hooks):
        hooks.on(Hook.BEFORE_TURN, self.on_before_turn)
        hooks.on(Hook.BEFORE_MODEL, self.on_before_model)
        hooks.on(Hook.AFTER_TOOL, self.on_after_tool)
        hooks.on(Hook.AFTER_TURN, self.on_after_turn)
        return self

    # ---- before_turn -----------------------------------------------------

    def on_before_turn(self, payload):
        """Load what we know into the conversation, as a message.

        NOT into the system prompt: that is the cached prefix, and this content
        changes every turn. Putting it there would invalidate the cache on
        every single turn.

        One block per turn does accumulate across a long session. Accepted:
        each block is truncated (see Memory.context_block), it is written once
        and then read from cache across that turn's several iterations, and
        compaction ages the stale ones out.
        """
        block = self.memory.context_block()
        if block:
            payload.context.add_message("user", f"<memory>\n{block}\n</memory>")
        self._needs_look = True   # anything could have happened between turns
        self._injected_this_turn = False

    # ---- before_model ----------------------------------------------------

    def on_before_model(self, payload):
        """Make sure we know where we are — which is usually free.

        Track, don't poll. Position is a belief updated from move/look replies
        in on_after_tool; a real `look` is issued only when that belief is
        stale or absent. Polling every iteration would mean ~119 extra round
        trips in a session the size of week1's longest, to a connection that
        drops every few minutes.
        """
        if not self._needs_look or self.registry is None:
            return
        self._needs_look = False          # clear first: a failure must not spin
        try:
            result = self.registry.dispatch("look", {})
        except Exception:                 # noqa: BLE001 -- disconnected, mid-combat, etc.
            return
        room = self._record_room(result)
        if room and not self._injected_this_turn:
            # Tell the model where it is, once per turn, only when we actually
            # learned something. Appended, never spliced.
            payload.context.add_message(
                "user",
                f"<position>You are in: {room['name']} "
                f"(exits: {', '.join(room['exits']) or 'none'})</position>",
            )
            self._injected_this_turn = True

    # ---- after_tool ------------------------------------------------------

    def on_after_tool(self, payload):
        """Extract everything durable from whatever the tool returned.

        Runs on the ORIGINAL result, before any trimming handler shortens it —
        which is the whole reason trimming is safe: memory keeps what the model
        stops seeing.
        """
        if not payload.ok:
            if payload.name in POSITION_LOST_AFTER:
                self._needs_look = True
            return

        text = str(payload.result or "")

        # Vitals are nearly free: the status prompt rides on almost every reply.
        status = parse_status(text)
        moves_before = self._moves
        if status:
            self.memory.update_state(hp_now=status["hp"], moves_now=status["moves"])
            self._moves = status["moves"]

        if payload.name == "check":
            score = parse_score(text)
            if score:
                self.memory.update_state(**score)

        # Read off ANY reply, not just the practice tool's: practising a skill
        # prints the remaining count too, so the number stays current without a
        # extra round trip after each one.
        sessions = parse_practice(text)
        if sessions is not None:
            self.memory.update_state(practice_sessions=sessions)

        if payload.name in ROOM_TOOLS:
            previous = self._position
            room = self._record_room(text)
            if payload.name == "move":
                direction = (payload.args or {}).get("direction")
                if room:
                    # Only record an edge we actually observed. No reverse is
                    # inferred -- CircleMUD has one-way exits.
                    #
                    # ...and only if we actually WALKED. Dying teleports you to
                    # the temple, and that reply carries a perfectly valid room
                    # description, so the parse succeeds and we would record
                    # "south from here leads to the Temple" -- an edge that does
                    # not exist, written permanently, which then sends every
                    # later route through it the wrong way. Found by the offline
                    # harness on its first run; not reachable on demand against
                    # a live server.
                    #
                    # The signal is structural rather than a phrase match: a
                    # walk always costs at least one movement point, and being
                    # relocated does not. Movement is already read off the
                    # status prompt that rides on nearly every reply.
                    #
                    # Known hole: movement regenerates on a timer, so a tick
                    # landing in the same moment as a move can mask the
                    # decrement. That fails SAFE -- we skip a real edge, which
                    # costs one re-walk, rather than recording a false one,
                    # which is permanent. Same trade as an unparsable move.
                    walked = (
                        moves_before is None
                        or self._moves is None
                        or self._moves < moves_before
                    )
                    if previous and direction and self._position and walked:
                        self.memory.record_move(previous, direction, self._position)
                else:
                    # A move whose reply we could not parse. We do NOT know
                    # whether the character moved -- a dark room ("It is pitch
                    # black...") has no exits line and neither does a refusal
                    # ("Alas, you cannot go that way."). Keeping the old
                    # position would let the NEXT successful move record an
                    # edge between two rooms that are not adjacent, and that
                    # bogus edge is persisted, survives the session, and makes
                    # find_route confidently hand back a wrong direction
                    # forever after. Found by code review.
                    #
                    # Deliberate trade: forgetting the position also loses the
                    # (correct) edge we could have recorded after a merely
                    # FAILED move. Losing a real edge costs one re-walk;
                    # recording a false one corrupts the map permanently.
                    # Clearing _position -- not just setting _needs_look -- is
                    # what makes this safe when several moves happen in a
                    # single tool batch, since record_move rejects an empty
                    # from-key and before_model only runs once per iteration.
                    self._position = None
                    self._needs_look = True

        if payload.name in POSITION_LOST_AFTER:
            # flee goes in a RANDOM direction; a (re)connect could land anywhere.
            self._needs_look = True

    # ---- after_turn ------------------------------------------------------

    def on_after_turn(self, payload):
        """Refresh the human-readable player file. Local write, no tokens."""
        self.memory.render_journal()

    # ---- internals -------------------------------------------------------

    def _record_room(self, text):
        room = parse_room(text)
        if not room:
            return None
        key = self.memory.remember_room(room["name"], room["exits"], room["description"])
        if key:
            self._position = key
            self.memory.set_position(key)
        return room


def install(hooks, memory=None, *, character=None, registry=None, dir=None):
    """Convenience: build the store if needed, install the handlers, return the
    MemoryHooks so a caller can inspect it."""
    if memory is None:
        if not character:
            raise ValueError("memory hooks need either memory= or character=")
        memory = Memory(character, dir=dir)
    return MemoryHooks(memory, registry=registry).install(hooks)
