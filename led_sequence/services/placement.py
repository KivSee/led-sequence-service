"""
Ring placement: which physical ring hangs at which position.

A placement maps positions to physical rings, both as thing names:
    {"ring1": "ring7", "ring2": "ring13"}
means the ring whose thing_info says "ring7" plays the "ring1" part of every
sequence, and "ring13" plays the "ring2" part. A ring that is not placed plays
under its own name, exactly as before placements existed. Only ring<N> names
take part; other things (pendants etc.) are never remapped.

The guid handed out for a trigger is combined with a hash of the placement, so
changing the placement changes every guid and the rings re-fetch their part the
next time a trigger is sent. An empty placement leaves guids unchanged.
"""

import json
import re
import zlib

RING_NAME = re.compile(r"^ring\d+$")


def ring_number(name: str) -> int:
    return int(name[4:])


def validate(raw) -> tuple:
    """Return (clean placement, errors). Identity entries are dropped (no-ops)."""
    errors = []
    if not isinstance(raw, dict):
        return {}, ["placement must be an object of position -> physical ring"]
    clean = {}
    for position, physical in raw.items():
        if not isinstance(position, str) or not RING_NAME.match(position):
            errors.append(f"position '{position}' is not a ring name like ring3")
            continue
        if not isinstance(physical, str) or not RING_NAME.match(physical):
            errors.append(f"physical ring '{physical}' for {position} is not a ring name like ring7")
            continue
        if physical != position:
            clean[position] = physical
    seen = {}
    for position, physical in clean.items():
        if physical in seen:
            errors.append(f"{physical} is placed at both {seen[physical]} and {position}")
        seen[physical] = position
    return clean, errors


def placement_hash(placement: dict) -> int:
    if not placement:
        return 0
    return zlib.crc32(json.dumps(placement, sort_keys=True).encode("utf-8")) & 0xFFFFFFFF


def combine_guid(sequence_guid, placement: dict) -> int:
    try:
        base = int(sequence_guid)
    except (TypeError, ValueError):
        base = 0
    return (base ^ placement_hash(placement)) & 0xFFFFFFFF


def position_for(placement: dict, thing_name: str) -> str:
    """The position (thing name in the sequence) a physical thing plays."""
    for position, physical in placement.items():
        if physical == thing_name:
            return position
    return thing_name


MAIN_POSITIONS = 12  # the positions on the installation; higher ones are extras


def warnings(placement: dict, physical_rings=None) -> list:
    """Placements that leave an installation position empty, or have two rings
    play the same part. physical_rings (rings known to exist) avoids warning
    about rings that aren't there; without it, rings 1-12 are assumed to exist."""
    def exists(name):
        if physical_rings is not None:
            return name in physical_rings
        return ring_number(name) <= MAIN_POSITIONS

    out = []
    positions = set(placement)
    placed = set(placement.values())
    for position, physical in sorted(placement.items(), key=lambda kv: ring_number(kv[0])):
        if position not in placed and exists(position):
            out.append(f"{position} is not placed anywhere, so it still plays its own part "
                       f"too: {physical} and {position} both play {position}")
        if physical not in positions and ring_number(physical) <= MAIN_POSITIONS:
            out.append(f"position {physical} has no ring ({physical} hangs at {position})")
    return out
