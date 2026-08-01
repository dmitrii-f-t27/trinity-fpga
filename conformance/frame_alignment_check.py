#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""frame_alignment_check.py — does each conformance host still address the
operands of the wrapper it targets?

On 2026-07-17 a commit titled "frame format bug fix" inserted a 0x00 byte
between the AA 55 magic and the payload across the conformance corpus. The gf
compute wrappers have no fmt field, so the extra byte shifted every operand one
position and the cores received op_a[7:0] = 0x00. Thirty-two hosts were
computing 0 + 0 for every input, and nothing noticed for two weeks: the golden
self-tests all passed, because none of them exercises the wire encoding.

This check closes that hole. It reads the request length a host builds and the
request length its wrapper's frame FSM parses, and fails when they disagree.
It is a static check on purpose — it needs no board, so it can run on every
push, which is the only way a regression like that gets caught in minutes
instead of in weeks.

Usage:
    python3 conformance/frame_alignment_check.py
    python3 conformance/frame_alignment_check.py --verbose

Author: Dmitrii Vasilev (@gHashTag)
"""

import argparse
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
CONFORMANCE = REPO / "conformance"

# Where each host's wrapper lives. Only cells whose wrapper can be located are
# checked; anything unmapped is reported as unchecked rather than assumed fine.
RTL_SEARCH_DIRS = [REPO / "fpga" / "vivado", REPO / "fpga" / "openxc7-synth"]


def rtl_request_length(rtl_text: str):
    """Body bytes the frame FSM consumes, plus the two magic bytes.

    The wrappers all share one idiom: a state machine that matches 0xAA then
    0x55, latches one byte per state, and raises frame_valid on a final trigger
    state. Counting the states that latch rx_byte gives the payload width.
    """
    # Find the parser block: from the 0xAA match to the frame_valid assignment.
    start = rtl_text.find("8'hAA")
    if start < 0:
        return None
    end = rtl_text.find("frame_valid<=1", start)
    if end < 0:
        end = rtl_text.find("frame_valid <= 1", start)
    if end < 0:
        return None
    block = rtl_text[start:end]

    # Most wrappers spend one state per byte, so each "<= rx_byte" is one byte.
    # The wide decoders instead latch through a counter,
    #
    #     5'd3: begin code_r[bcnt*8 +: 8]<=rx_byte;
    #            if(bcnt==4'd15) frm<=5'd4; else bcnt<=bcnt+4'd1; end
    #
    # which is one latching statement covering sixteen bytes. Counting
    # statements there understates the frame, so read the terminator bound.
    latches = list(re.finditer(r"<=\s*rx_byte", block))
    if not latches:
        return None

    payload = 0
    for i, m in enumerate(latches):
        tail = block[m.end(): latches[i + 1].start() if i + 1 < len(latches) else len(block)]
        bound = re.search(r"if\s*\(\s*\w+\s*==\s*\d*'d(\d+)\s*\)", tail)
        payload += int(bound.group(1)) + 1 if bound else 1

    # 2 magic + payload bytes + 1 trigger byte
    return 2 + payload + 1


def _split_top_level(text: str, sep: str):
    """Split on `sep` only where bracket depth is zero."""
    depth, parts, cur = 0, [], ""
    for ch in text:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == sep and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        parts.append(cur)
    return parts


def host_request_length(host_text: str):
    """Bytes the host writes per request, or None when it cannot be resolved.

    Hosts build their packet as a concatenation of byte literals and variables,
    e.g. `FRAME + bytes([FMT]) + b + bytes([0x00])` where `b` came from a
    `to_bytes(N, ...)` call. An unresolvable term returns None so the host is
    reported as unchecked — a guard that invents a mismatch is worse than no
    guard, because the next person learns to ignore it.
    """
    m = re.search(r"^FRAME\s*=\s*bytes\(\[([^\]]*)\]\)", host_text, re.MULTILINE)
    if not m:
        return None
    frame_len = len([x for x in _split_top_level(m.group(1), ",") if x.strip()])

    # The expression may wrap across lines when the payload is wide, so read
    # forward until the brackets balance rather than stopping at the newline.
    m2 = re.search(r"^\s*pkt\s*=\s*", host_text, re.MULTILINE)
    if not m2:
        return None
    depth, expr, in_comment = 0, "", False
    for ch in host_text[m2.end():]:
        if ch == "\n":
            in_comment = False
            if depth == 0:
                break
            expr += ch
            continue
        # A trailing comment is not part of the expression. Dropping it matters:
        # without this, `pkt = FRAME + bytes([...])  # trigger` failed to match
        # its final term and the host was silently reported as unchecked —
        # which is how a guard stops guarding without anyone noticing.
        if ch == "#":
            in_comment = True
        if in_comment:
            continue
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        expr += ch

    total = 0
    for term in _split_top_level(expr, "+"):
        term = term.strip()
        if term == "FRAME":
            total += frame_len
            continue
        lit = re.fullmatch(r"bytes\(\[(.*)\]\)", term, re.DOTALL)
        if lit:
            total += len([x for x in _split_top_level(lit.group(1), ",") if x.strip()])
            continue
        if re.fullmatch(r"[A-Za-z_]\w*", term):
            # Resolve a bare name through its to_bytes width.
            width = re.search(rf"\b{re.escape(term)}\s*=\s*[^\n]*?to_bytes\(\s*(\d+)", host_text)
            if width:
                total += int(width.group(1))
                continue
        return None

    return total


def find_rtl_for(host_path: pathlib.Path, host_text: str):
    """Locate the wrapper a host targets.

    Prefer an explicit path written in the host's header — several name their
    RTL — and fall back to the naming convention otherwise.
    """
    cited = re.findall(r"(fpga/[\w/]+\.v)", host_text)
    for c in cited:
        p = REPO / c
        if p.exists():
            return p

    stem = host_path.name.replace("_conformance_ax7203.py", "")
    candidates = [
        f"{stem}_ax7203.v",
        f"{stem.replace('_add', '_clean')}_ax7203.v",
        f"corona_compute_{stem}_ax7203.v",
        f"corona_decode_{stem.replace('_decode', '')}_ax7203.v",
    ]
    for d in RTL_SEARCH_DIRS:
        for name in candidates:
            p = d / name
            if p.exists():
                return p
    return None


def main():
    ap = argparse.ArgumentParser(description="check host request frames against their wrappers")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    hosts = sorted(CONFORMANCE.glob("*_conformance_ax7203.py"))
    aligned, mismatched, unchecked = [], [], []

    for host in hosts:
        text = host.read_text(errors="replace")
        h_len = host_request_length(text)
        if h_len is None:
            unchecked.append((host.name, "no FRAME/pkt pattern"))
            continue
        rtl = find_rtl_for(host, text)
        if rtl is None:
            unchecked.append((host.name, "wrapper not located"))
            continue
        r_len = rtl_request_length(rtl.read_text(errors="replace"))
        if r_len is None:
            unchecked.append((host.name, f"no frame FSM in {rtl.name}"))
            continue

        if h_len == r_len:
            aligned.append((host.name, rtl.name, h_len))
        else:
            mismatched.append((host.name, rtl.name, h_len, r_len))

    print(f"frame alignment: {len(aligned)} aligned, {len(mismatched)} MISMATCHED, "
          f"{len(unchecked)} unchecked, {len(hosts)} hosts total")

    if args.verbose:
        for name, rtl, n in aligned:
            print(f"  ok        {name:<48} {rtl:<38} {n} bytes")

    for name, reason in unchecked:
        print(f"  unchecked {name:<48} {reason}")

    for name, rtl, h, r in mismatched:
        print(f"  MISMATCH  {name:<48} host sends {h} bytes, {rtl} parses {r}")
        if h > r:
            print(f"            -> {h - r} byte(s) too many; operands shift and the core "
                  f"receives zeros")
        else:
            print(f"            -> {r - h} byte(s) too few; the wrapper never triggers")

    if mismatched:
        print("\nA host whose frame does not match its wrapper measures nothing. "
              "Fix the host, or correct the mapping if it targets a different cell.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
