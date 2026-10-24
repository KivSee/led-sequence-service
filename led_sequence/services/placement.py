"""
Ring placement: which physical ring hangs at which position, and which position
each pendant imitates.

A placement has two parts, both using thing names:
    {"rings":    {"ring1": "ring7", "ring2": "ring13"},
     "pendants": {"lilum4": "ring3"}}
- rings: position -> physical ring. The ring whose thing_info says "ring7" plays
  the "ring1" part of every sequence, "ring13" plays the "ring2" part. A ring
  that is not placed plays under its own name, as before placements existed.
- pendants: physical pendant -> position it imitates. "lilum4" plays exactly
  the part of position ring3 (the same copy mirrorToLilum makes when a song is
  sent; pendants know all the ring segment names). A pendant that is not set
  plays its own lilum<N> part, if the sequence has one.
Positions are ring1, ring2, ... (no ring0); other things are never remapped.

The guid handed out for a trigger is combined with a hash of the placement, so
changing it changes every guid and the rings and pendants re-fetch their part the
next time a trigger is sent. An empty placement leaves guids unchanged.
"""

import json
import re
import zlib

RING_NAME = re.compile(r"^ring[1-9]\d*$")
PENDANT_NAME = re.compile(r"^lilum\d+$")
MAIN_POSITIONS = 12  # the positions on the installation; higher ones are extras


def ring_number(name: str) -> int:
    return int(re.sub(r"^\D+", "", name))


def normalize(stored) -> dict:
    """Stored placement -> {"rings": {...}, "pendants": {...}} (a flat dict is the old rings-only format)."""
    if not isinstance(stored, dict):
        return {"rings": {}, "pendants": {}}
    if "rings" in stored or "pendants" in stored:
        return {"rings": dict(stored.get("rings") or {}), "pendants": dict(stored.get("pendants") or {})}
    return {"rings": dict(stored), "pendants": {}}


def is_empty(placement: dict) -> bool:
    return not placement["rings"] and not placement["pendants"]


def validate(raw) -> tuple:
    """Return (clean placement, errors). Ring identity entries are dropped (no-ops)."""
    if not isinstance(raw, dict):
        return normalize({}), ["placement must be an object with rings and pendants"]
    raw = normalize(raw)
    errors = []
    rings = {}
    for position, physical in raw["rings"].items():
        if not isinstance(position, str) or not RING_NAME.match(position):
            errors.append(f"position '{position}' is not a ring position like ring3")
            continue
        if not isinstance(physical, str) or not RING_NAME.match(physical):
            errors.append(f"physical ring '{physical}' for {position} is not a ring name like ring7")
            continue
        if physical != position:
            rings[position] = physical
    seen = {}
    for position, physical in rings.items():
        if physical in seen:
            errors.append(f"{physical} is placed at both {seen[physical]} and {position}")
        seen[physical] = position
    pendants = {}
    for pendant, position in raw["pendants"].items():
        if not isinstance(pendant, str) or not PENDANT_NAME.match(pendant):
            errors.append(f"pendant '{pendant}' is not a pendant name like lilum4")
            continue
        if not isinstance(position, str) or not RING_NAME.match(position):
            errors.append(f"position '{position}' for {pendant} is not a ring position like ring3")
            continue
        pendants[pendant] = position
    return {"rings": rings, "pendants": pendants}, errors


def placement_hash(placement: dict) -> int:
    if is_empty(placement):
        return 0
    return zlib.crc32(json.dumps(placement, sort_keys=True).encode("utf-8")) & 0xFFFFFFFF


def combine_guid(sequence_guid, placement: dict) -> int:
    try:
        base = int(sequence_guid)
    except (TypeError, ValueError):
        base = 0
    return (base ^ placement_hash(placement)) & 0xFFFFFFFF


def part_for(placement: dict, thing_name: str) -> str:
    """The thing name whose part a physical thing plays."""
    if thing_name in placement["pendants"]:
        return placement["pendants"][thing_name]
    for position, physical in placement["rings"].items():
        if physical == thing_name:
            return position
    return thing_name


def warnings(placement: dict, physical_rings=None) -> list:
    """Ring placements that leave an installation position empty, or have two rings
    play the same part. physical_rings (rings known to exist) avoids warning about
    rings that aren't there; without it, rings 1-12 are assumed to exist."""
    def exists(name):
        if physical_rings is not None:
            return name in physical_rings
        return ring_number(name) <= MAIN_POSITIONS

    rings = placement["rings"]
    out = []
    positions = set(rings)
    placed = set(rings.values())
    for position, physical in sorted(rings.items(), key=lambda kv: ring_number(kv[0])):
        if position not in placed and exists(position):
            out.append(f"{position} is not placed anywhere, so it still plays its own part "
                       f"too: {physical} and {position} both play {position}")
        if physical not in positions and ring_number(physical) <= MAIN_POSITIONS:
            out.append(f"position {physical} has no ring ({physical} hangs at {position})")
    return out
