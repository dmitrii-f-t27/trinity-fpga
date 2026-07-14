#!/usr/bin/env python3
"""
bitstream_provenance.py — Bind source code to flashed bitstreams.

The GF64 wrapper bug (cur_byte wire→reg) proved we can flash a bitstream
without knowing what source produced it. This tool creates a cryptographic
chain of custody:

    source files (SHA256) + git commit + bitstream (SHA256) => manifest

Usage:
    bitstream_provenance.py generate <src.v ...> --design <top> --bit <out.bit>
    bitstream_provenance.py verify  <bitstream.bit>
    bitstream_provenance.py list    [--dir <directory>]

Self-contained: stdlib only. Python 3.7+.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DOCKER_IMAGE = "regymm/openxc7:latest"


def sha256_file(path: Path) -> str:
    """Streaming SHA256 of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def count_lines(path: Path) -> int:
    """Count lines (text-safe; binary files return 0)."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def git_head_info(repo: Path) -> tuple:
    """Return (commit_sha, dirty_bool). Best-effort; ('unknown', False) if not a repo."""
    try:
        commit = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        if not commit or len(commit) < 7:
            return ("unknown", False)
        status = subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        return (commit[:12], len(status) > 0)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return ("unknown", False)


def detect_tool_versions() -> dict:
    """Probe yosys/nextpnr versions. Empty string if unavailable."""
    versions = {"yosys_version": "", "nextpnr_version": ""}
    for tool, key in (("yosys", "yosys_version"), ("nextpnr", "nextpnr_version")):
        try:
            out = subprocess.run(
                [tool, "-V"], capture_output=True, text=True, timeout=10,
            )
            versions[key] = (out.stdout or out.stderr).strip().splitlines()[0] if (out.stdout or out.stderr) else ""
        except (FileNotFoundError, subprocess.TimeoutExpired, IndexError, OSError):
            pass
    return versions


def find_repo_root(start: Path) -> Path:
    """Walk up to find a git toplevel; fall back to start."""
    p = start.resolve()
    for cand in [p, *p.parents]:
        if (cand / ".git").exists():
            return cand
    return start.resolve()


def manifest_path_for(bitstream: Path) -> Path:
    return Path(str(bitstream) + ".provenance.json")


def cmd_generate(args) -> int:
    bit = Path(args.bit).resolve()
    sources = [Path(s).resolve() for s in args.source_files]

    missing = [str(s) for s in sources if not s.is_file()]
    if missing:
        print(f"error: missing source file(s): {missing}", file=sys.stderr)
        return 2
    if not bit.is_file():
        print(f"error: bitstream not found: {bit}", file=sys.stderr)
        return 2

    repo = find_repo_root(sources[0]) if args.repo_root is None else Path(args.repo_root)
    commit, dirty = git_head_info(repo)
    versions = detect_tool_versions()

    source_records = []
    for s in sources:
        source_records.append({
            "file": str(s),
            "sha256": sha256_file(s),
            "lines": count_lines(s),
        })

    manifest = {
        "bitstream": str(bit),
        "bitstream_sha256": sha256_file(bit),
        "design": args.design,
        "git_commit": commit,
        "git_dirty": dirty,
        "sources": source_records,
        "build_timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "openxc7_docker_image": args.docker_image,
        "yosys_version": versions["yosys_version"],
        "nextpnr_version": versions["nextpnr_version"],
    }

    out = manifest_path_for(bit)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
        f.write("\n")

    print(f"[provenance] wrote {out}")
    print(f"  bitstream : {bit.name}  sha={manifest['bitstream_sha256'][:16]}...")
    print(f"  design    : {manifest['design']}")
    print(f"  git       : {commit}{' (dirty)' if dirty else ''}")
    print(f"  sources   : {len(source_records)} file(s)")
    return 0


def cmd_verify(args) -> int:
    bit = Path(args.bitstream).resolve()
    manifest_file = manifest_path_for(bit)
    if not manifest_file.is_file():
        print(f"error: no provenance manifest at {manifest_file}", file=sys.stderr)
        return 2
    if not bit.is_file():
        print(f"error: bitstream missing: {bit}", file=sys.stderr)
        return 2

    with open(manifest_file, "r", encoding="utf-8") as f:
        m = json.load(f)

    problems = []

    # 1. bitstream hash
    actual_bit_hash = sha256_file(bit)
    if actual_bit_hash != m["bitstream_sha256"]:
        problems.append(
            f"BITSTREAM HASH MISMATCH\n"
            f"  manifest : {m['bitstream_sha256']}\n"
            f"  actual   : {actual_bit_hash}"
        )

    # 2. source hashes
    for rec in m["sources"]:
        src = Path(rec["file"])
        if not src.is_file():
            problems.append(f"MISSING SOURCE: {src}")
            continue
        actual = sha256_file(src)
        if actual != rec["sha256"]:
            problems.append(
                f"SOURCE HASH MISMATCH: {src}\n"
                f"  manifest : {rec['sha256']}\n"
                f"  actual   : {actual}"
            )

    # 3. git commit drift (informational) — use the first source's repo
    repo = find_repo_root(Path(m["sources"][0]["file"])) if m.get("sources") else Path.cwd()
    commit, _ = git_head_info(repo)
    if commit != "unknown" and commit != m.get("git_commit", ""):
        problems.append(
            f"NOTE: git HEAD drifted since manifest was written\n"
            f"  manifest : {m.get('git_commit')}\n"
            f"  current  : {commit}"
        )

    design = m.get("design", "?")
    print(f"[verify] {bit.name}  design={design}")
    print(f"  bitstream sha256 : {actual_bit_hash[:16]}...")
    print(f"  sources checked  : {len(m['sources'])}")
    print(f"  git commit       : {m.get('git_commit', '?')}")

    if problems:
        print(f"\n[FAIL] {len(problems)} problem(s):", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    print("[OK] all hashes match")
    return 0


def cmd_list(args) -> int:
    root = Path(args.dir).resolve() if args.dir else Path.cwd().resolve()
    if not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2

    bit_files = sorted(root.rglob("*.bit"))
    if not bit_files:
        print(f"[list] no .bit files under {root}")
        return 0

    header = f"{'BITSTREAM':<48} {'PROV':<6} {'DESIGN':<32} {'COMMIT':<12} {'SOURCES':<7} STATUS"
    print(header)
    print("-" * len(header))

    rc = 0
    for bit in bit_files:
        rel = bit.relative_to(root)
        prov = manifest_path_for(bit)
        if prov.is_file():
            try:
                with open(prov, "r", encoding="utf-8") as f:
                    m = json.load(f)
                design = m.get("design", "?")[:30]
                commit = m.get("git_commit", "?")[:12]
                nsources = str(len(m.get("sources", [])))
                status = "ok"
                provmark = "yes"
            except (OSError, json.JSONDecodeError) as e:
                design, commit, nsources, status = "?", "?", "?", f"bad manifest: {e}"
                provmark = "BAD"
        else:
            design, commit, nsources, status = "-", "-", "-", "NO PROVENANCE"
            provmark = "no"

        name = str(rel)
        if len(name) > 46:
            name = "..." + name[-43:]
        print(f"{name:<48} {provmark:<6} {design:<32} {commit:<12} {nsources:<7} {status}")
        if provmark == "no":
            rc = 1  # signal that some bitstreams lack provenance

    return rc


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bitstream_provenance",
        description="Bind source code to flashed bitstreams (chain of custody).",
    )
    sub = p.add_subparsers(dest="command", required=True)

    g = sub.add_parser("generate", help="Create a .provenance.json manifest for a bitstream.")
    g.add_argument("source_files", nargs="+", help="Source file(s) that produced the bitstream.")
    g.add_argument("--design", required=True, help="Top-module / design name.")
    g.add_argument("--bit", required=True, help="Path to the produced .bit file.")
    g.add_argument("--docker-image", default=DEFAULT_DOCKER_IMAGE,
                   help=f"openXC7 docker image tag (default: {DEFAULT_DOCKER_IMAGE})")
    g.add_argument("--repo-root", default=None, help="Override git repo root for commit lookup.")
    g.set_defaults(func=cmd_generate)

    v = sub.add_parser("verify", help="Re-check a bitstream against its manifest.")
    v.add_argument("bitstream", help="Path to the .bit file to verify.")
    v.set_defaults(func=cmd_verify)

    l = sub.add_parser("list", help="List bitstreams and provenance status under a directory.")
    l.add_argument("--dir", default=None, help="Directory to scan (default: cwd).")
    l.set_defaults(func=cmd_list)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
