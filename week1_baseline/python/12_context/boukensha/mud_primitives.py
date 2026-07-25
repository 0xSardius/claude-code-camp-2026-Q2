"""Port of the subset of week0_explore/mud_manager/lib/mud_manager/primitives.rb
that week1_baseline/ruby/10_standard_tool_library's Tools::Mud actually
calls -- see docs/plans/python_port/10_standard_tool_library's
placement-decision section for why this isn't the full ~50-method surface
(Ruby's Primitives module defines many command builders no tool in this
project's Tools::Mud ever invokes).

Ruby's check_enum!/require_str! raise ArgumentError; ported here as
ValueError (same ArgumentError -> ValueError mapping used throughout this
codebase, e.g. tasks/base.py's settings validation).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Command:
    # Ruby: Struct.new(:primitive, :raw, :verb, :args, keyword_init: true)
    # -- Struct -> dataclass, same precedent as Tool/Message in
    # 01_struct_skeleton. Ruby's Command#to_s = raw isn't reproduced:
    # nothing in the ported Tools::Mud calls str() on a Command, only
    # .raw directly.
    primitive: str
    verb: str
    raw: str
    args: dict = field(default_factory=dict)


DIRECTIONS = ["north", "east", "south", "west", "up", "down"]
POSITIONS = ["stand", "sit", "rest", "sleep", "wake"]
ATTACK_STYLES = ["hit", "murder", "kill"]
STRIKE_SKILLS = ["backstab", "bash", "kick", "rescue", "assist"]
LOCAL_SAY = ["say", "emote", "reply"]
TARGETED_SAY = ["tell", "whisper", "ask"]
CHANNELS = ["shout", "gossip", "auction", "grats", "holler"]
DROP_MODES = ["drop", "donate", "junk"]
EQUIP_OPS = ["wear", "wield", "grab", "hold", "remove"]
CONSUME_MODES = ["eat", "taste", "drink", "sip"]
LOOK_MODES = ["look", "read"]
LOOK_PREPS = ["in", "at", "north", "east", "south", "west", "up", "down"]
INFO_SELF = [
    "score", "inventory", "equipment", "gold", "exits", "time",
    "weather", "levels", "wimpy", "toggle", "where",
]
SPELL_ITEM = ["use", "quaff", "recite"]
SHOP_OPS = ["buy", "sell", "list", "value", "offer"]


def _check_enum(value, allowed, name):
    v = str(value).lower()
    if v not in allowed:
        raise ValueError(f"invalid {name}: {value!r} (expected one of {', '.join(allowed)})")
    return v


def _require_str(value, name):
    if value is None or str(value).strip() == "":
        raise ValueError(f"{name} is required")


# ---------- Movement & posture ----------

def move(direction):
    verb = _check_enum(direction, DIRECTIONS, "direction")
    return Command("move", verb, verb)


def flee():
    return Command("flee", "flee", "flee")


def set_position(pos):
    verb = _check_enum(pos, POSITIONS, "pos")
    return Command("set_position", verb, verb)


def track(victim):
    _require_str(victim, "victim")
    return Command("track", "track", f"track {victim}", {"victim": victim})


# ---------- Combat ----------

def attack(style, target):
    verb = _check_enum(style, ATTACK_STYLES, "style")
    _require_str(target, "target")
    return Command("attack", verb, f"{verb} {target}", {"target": target})


def skill_strike(skill, target):
    verb = _check_enum(skill, STRIKE_SKILLS, "skill")
    _require_str(target, "target")
    return Command("skill_strike", verb, f"{verb} {target}", {"target": target})


def consider(target):
    _require_str(target, "target")
    return Command("consider", "consider", f"consider {target}", {"target": target})


# ---------- Communication ----------

def say_local(mode, text):
    verb = _check_enum(mode, LOCAL_SAY, "mode")
    _require_str(text, "text")
    return Command("say_local", verb, f"{verb} {text}", {"text": text})


def say_targeted(mode, target, text):
    verb = _check_enum(mode, TARGETED_SAY, "mode")
    _require_str(target, "target")
    _require_str(text, "text")
    return Command("say_targeted", verb, f"{verb} {target} {text}", {"target": target, "text": text})


def say_channel(channel, text):
    verb = _check_enum(channel, CHANNELS, "channel")
    _require_str(text, "text")
    return Command("say_channel", verb, f"{verb} {text}", {"text": text})


# ---------- Inventory & objects ----------

def get(obj, container=None, count=None):
    _require_str(obj, "obj")
    parts = ["get"]
    if count:
        parts.append(str(count))
    parts.append(obj)
    if container:
        parts.append(container)
    return Command("get", "get", " ".join(parts), {"obj": obj, "container": container, "count": count})


def drop(mode, obj, count=None):
    verb = _check_enum(mode, DROP_MODES, "mode")
    _require_str(obj, "obj")
    parts = [verb]
    if count:
        parts.append(str(count))
    parts.append(obj)
    return Command("drop", verb, " ".join(parts), {"obj": obj, "count": count})


def put(obj, container, count=None):
    _require_str(obj, "obj")
    _require_str(container, "container")
    parts = ["put"]
    if count:
        parts.append(str(count))
    parts += [obj, container]
    return Command("put", "put", " ".join(parts), {"obj": obj, "container": container, "count": count})


def equip(slot_op, obj, body_loc=None):
    verb = _check_enum(slot_op, EQUIP_OPS, "slot_op")
    _require_str(obj, "obj")
    raw = f"{verb} {obj} {body_loc}" if body_loc else f"{verb} {obj}"
    return Command("equip", verb, raw, {"obj": obj, "body_loc": body_loc})


def consume(mode, obj):
    verb = _check_enum(mode, CONSUME_MODES, "mode")
    _require_str(obj, "obj")
    return Command("consume", verb, f"{verb} {obj}", {"obj": obj})


# ---------- Perception & info ----------

def look(mode="look", target=None, preposition=None):
    # Normalize blank strings -> None, same "" vs None distinction as
    # everywhere else in this codebase (Ruby: target.to_s.strip.empty?).
    target = None if target is not None and str(target).strip() == "" else target
    preposition = None if preposition is not None and str(preposition).strip() == "" else preposition
    verb = _check_enum(mode, LOOK_MODES, "mode")
    if preposition:
        _check_enum(preposition, LOOK_PREPS, "preposition")
    parts = [verb]
    if preposition:
        parts.append(preposition)
    if target:
        parts.append(target)
    return Command("look", verb, " ".join(parts), {"target": target, "preposition": preposition})


def examine(target):
    _require_str(target, "target")
    return Command("examine", "examine", f"examine {target}", {"target": target})


def info_self(kind):
    verb = _check_enum(kind, INFO_SELF, "kind")
    return Command("info_self", verb, verb)


# ---------- Character / lifecycle ----------

def practice(skill=None):
    raw = f"practice {skill}" if skill else "practice"
    return Command("practice", "practice", raw, {"skill": skill})


def save_char():
    return Command("save_char", "save", "save")


# ---------- Magic ----------

def cast(spell, target=None):
    _require_str(spell, "spell")
    raw = f"cast '{spell}' {target}" if target else f"cast '{spell}'"
    return Command("cast", "cast", raw, {"spell": spell, "target": target})


def use_magic_item(mode, item, target_args=None):
    verb = _check_enum(mode, SPELL_ITEM, "mode")
    _require_str(item, "item")
    raw = f"{verb} {item} {target_args}" if target_args else f"{verb} {item}"
    return Command("use_magic_item", verb, raw, {"item": item, "target_args": target_args})


# ---------- Room-procedural (SPEC_PROC-mediated) ----------

def shop(op, args=None):
    verb = _check_enum(op, SHOP_OPS, "op")
    raw = f"{verb} {args}" if args else verb
    return Command("shop", verb, raw, {"args": args})
