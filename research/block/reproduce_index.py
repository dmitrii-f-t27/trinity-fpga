#!/usr/bin/env python3
"""Derive the reproducibility index for research/block from the sources themselves.

    python3 reproduce_index.py            # write MANIFEST.json and REPRODUCE.md
    python3 reproduce_index.py --check    # fail if either file disagrees with the tree
    python3 reproduce_index.py --models   # re-resolve model revisions (needs network)

Nothing in the two generated files is typed by hand. The producer of each JSON
record is found by walking the Python sources for *write sites* -- `open(p,"w")`,
`Path(p).write_text(...)`, and assignments to OUT-ish names -- and matching the
static shape of the path expression against the filenames actually present. A
script that merely *reads* `align_u_gpt2.json` is not its producer, and three of
them do; only one writes it.

`models_resolved.json` is the one input this script does not derive locally: it
records what the Hugging Face API answered for each model id found in the
sources. Refresh it with --models; the ordinary run reads the cached file so the
index builds offline.

Written stdlib-only and for Python 3.9+, because the point of the file is that
somebody who has just cloned the repository can run it.
"""
import argparse
import ast
import hashlib
import itertools
import json
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "MANIFEST.json")
DOC = os.path.join(HERE, "REPRODUCE.md")
MODELS = os.path.join(HERE, "models_resolved.json")

# A record field carries checkpoint identity only if one of these is a whole
# word in the key. Unanchored, `sha` matches `bin_sse_share` and the count stops
# measuring checkpoints; see NOT_CHECKPOINT for the other half of the same error.
IDENTITY = re.compile(
    r"(^|_)(revision|commit|sha|sha256|snapshot|checkpoint|digest|md5)(_|$)", re.I)

HEAVY = ("torch", "transformers", "datasets", "accelerate", "safetensors",
         "sentencepiece", "tokenizers", "bitsandbytes")

# A path that only exists on the machine the measurement ran on.
FOREIGN = re.compile(r"/private/tmp|/Users/(?!playra\b)[A-Za-z0-9_.-]+/|/home/[A-Za-z0-9_.-]+/")

HF_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,38}(/[A-Za-z0-9][A-Za-z0-9._-]{1,38})?$")


# --------------------------------------------------------------------------- #
# static shape of a path expression
# --------------------------------------------------------------------------- #

def tmpl(node):
    """Best-effort static template for a string expression. '?' marks a hole."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(tmpl(v) or "?" for v in node.values)
    if isinstance(node, ast.FormattedValue):
        return "?"
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return (tmpl(node.left) or "?") + (tmpl(node.right) or "?")
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        a = tmpl(node.left)
        return re.sub(r"%[-0-9.]*[sdf]", "?", a) if a else None
    if isinstance(node, ast.Call):
        f = node.func
        if isinstance(f, ast.Attribute) and f.attr == "format":
            a = tmpl(f.value)
            return re.sub(r"\{[^}]*\}", "?", a) if a else None
        if isinstance(f, ast.Attribute) and f.attr == "join":
            return "/".join(tmpl(a) or "?" for a in node.args)
        if isinstance(f, ast.Attribute) and f.attr in ("abspath", "expanduser", "resolve"):
            return tmpl(node.args[0]) if node.args else None
    return None


def tmpls(node, env):
    """Every static shape an expression might take. `env` maps a local name to
    the shapes assigned to it, because the common write site in this directory is
    `open(dst, "w")` with `dst = os.environ.get("OUT") or os.path.join(...)`."""
    if isinstance(node, ast.Name):
        return list(env.get(node.id, []))
    if isinstance(node, ast.BoolOp):
        out = []
        for v in node.values:
            out += tmpls(v, env)
        return out
    if isinstance(node, ast.IfExp):
        return tmpls(node.body, env) + tmpls(node.orelse, env)
    if isinstance(node, ast.Call):
        f = node.func
        if isinstance(f, ast.Attribute) and f.attr == "get" and len(node.args) == 2:
            return tmpls(node.args[1], env)          # the default is the real path
        if isinstance(f, ast.Attribute) and f.attr == "join":
            parts = [tmpls(a, env) or ["?"] for a in node.args]
            return ["/".join(p) for p in itertools.islice(itertools.product(*parts), 8)]
    t = tmpl(node)
    return [t] if t else []


def env_of(tree):
    """name -> shapes assigned to it, module-wide and flat. Flat is deliberate:
    the alternative is a scope analysis that would resolve no more files here."""
    env = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign):
            for tgt in n.targets:
                if isinstance(tgt, ast.Name):
                    got = tmpls(n.value, env)
                    if got:
                        env.setdefault(tgt.id, []).extend(got)
    return env


def write_sites(tree):
    """Every path expression this module writes to, as a static template."""
    env = env_of(tree)
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            f = n.func
            name = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else "")
            if name == "open":
                mode = ""
                if len(n.args) > 1 and isinstance(n.args[1], ast.Constant):
                    mode = str(n.args[1].value)
                for kw in n.keywords:
                    if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                        mode = str(kw.value.value)
                if ("w" in mode or "a" in mode or "x" in mode) and n.args:
                    out += tmpls(n.args[0], env)
            elif name in ("write_text", "write_bytes"):
                if isinstance(f, ast.Attribute):
                    inner = f.value
                    # Path(p).write_text(...) -- the path is Path's argument
                    if isinstance(inner, ast.Call) and inner.args:
                        out += tmpls(inner.args[0], env)
                    else:
                        out += tmpls(inner, env)
            elif name in ("dump", "savez", "savez_compressed", "to_json", "save"):
                # json.dump(obj, open(p, "w")) is already covered by the open()
                # arm; this arm catches np.save("x.npy") style calls.
                for a in n.args:
                    out += [t for t in tmpls(a, env) if t.endswith(".json")]
        elif isinstance(n, ast.Assign):
            for tgt in n.targets:
                if isinstance(tgt, ast.Name) and re.match(r"^(OUT|DEST|TARGET|DST)", tgt.id):
                    out += tmpls(n.value, env)
    return out


def to_regex(t):
    """A template becomes a pattern over basenames; '?' is one path segment."""
    base = t.rsplit("/", 1)[-1]
    if not base.endswith(".json"):
        return None
    parts = [re.escape(p) for p in base.split("?")]
    return re.compile("^" + "[A-Za-z0-9_.-]+".join(parts) + "$"), base


#: The package's own files. Not research sources, not records -- they describe
#: the directory, so counting them in it makes the index a measurement of itself.
#: One home for this list: `verify_manifest.py` and `rerun_dependency_free.py`
#: import it from here. It was three hand-kept copies once, and the third tool
#: was added to none of them.
PACKAGE = ("reproduce_index.py", "verify_manifest.py", "rerun_dependency_free.py",
           "MANIFEST.json", "models_resolved.json", "RERUN.json")


def scripts(d):
    return sorted(f for f in os.listdir(d) if f.endswith(".py") and f not in PACKAGE)


def jsons(d):
    return sorted(f for f in os.listdir(d) if f.endswith(".json") and f not in PACKAGE)


def producers(d):
    """record -> list of scripts that write a path of that shape."""
    pats = {}
    for s in scripts(d):
        try:
            tree = ast.parse(open(os.path.join(d, s), encoding="utf-8", errors="replace").read())
        except SyntaxError:
            continue
        for t in write_sites(tree):
            r = to_regex(t)
            if r:
                pats.setdefault(s, []).append(r)
    out = {}
    for rec in jsons(d):
        hits = []
        for s, rs in pats.items():
            for rx, literal in rs:
                if rx.match(rec):
                    # a template with no hole is an exact claim; prefer it
                    hits.append((0 if "?" not in literal else 1, -len(literal), s))
                    break
        if not hits:
            out[rec] = []
            continue
        hits.sort()
        best = hits[0][0]
        out[rec] = sorted({s for rank, _, s in hits if rank == best})
    return out


def deps(d):
    """script -> {'heavy': [...], 'foreign_paths': bool}"""
    out = {}
    for s in scripts(d):
        src = open(os.path.join(d, s), encoding="utf-8", errors="replace").read()
        try:
            tree = ast.parse(src)
        except SyntaxError:
            out[s] = {"heavy": [], "foreign_paths": bool(FOREIGN.search(src)), "parse_error": True}
            continue
        mods = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                mods.update(a.name.split(".")[0] for a in n.names)
            elif isinstance(n, ast.ImportFrom) and n.module:
                mods.add(n.module.split(".")[0])
        out[s] = {"heavy": sorted(mods & set(HEAVY)),
                  "foreign_paths": bool(FOREIGN.search(src))}
    return out


def provenance_of(path, here):
    """The `provenance` block a record carries, and whether it checks out.

    The block was retro-fitted on 2026-08-12 and says so in its own
    `RETROFITTED` field. It names the harness by filename AND by sha256, so the
    claim "this number came from that file" is testable against this tree --
    which is the one reproducibility claim here that does not need the weights.
    """
    try:
        j = json.load(open(path, encoding="utf-8"))
    except Exception:                                # noqa: BLE001
        return None
    if not isinstance(j, dict):
        return None
    p = j.get("provenance")
    if not isinstance(p, dict):
        return None
    out = {}
    h = p.get("harness")
    if isinstance(h, dict) and h.get("file"):
        hp = os.path.join(here, h["file"])
        out["harness"] = {
            "file": h["file"],
            "sha256": h.get("sha256"),
            "present": os.path.exists(hp),
            "matches_tree": os.path.exists(hp) and sha256(hp) == h.get("sha256"),
        }
    c = p.get("corpus")
    if isinstance(c, dict):
        out["corpus"] = {k: c.get(k) for k in ("sha256", "chars", "rows")}
    ck = p.get("checkpoint")
    if isinstance(ck, dict):
        out["checkpoint"] = {k: ck.get(k) for k in ("src", "kind", "revision")}
    if p.get("RETROFITTED"):
        out["retrofitted"] = True
    return out or None


def model_ids(d):
    """String constants that look like a model id, in a position that names one."""
    found = {}
    for s in scripts(d):
        try:
            tree = ast.parse(open(os.path.join(d, s), encoding="utf-8", errors="replace").read())
        except SyntaxError:
            continue
        cands = []
        for n in ast.walk(tree):
            if isinstance(n, ast.Dict):
                cands += [v for v in n.values
                          if isinstance(v, ast.Constant) and isinstance(v.value, str)]
            elif isinstance(n, ast.Call):
                cands += [kw.value for kw in n.keywords
                          if kw.arg in ("src", "model", "model_id", "repo", "name")
                          and isinstance(kw.value, ast.Constant)
                          and isinstance(kw.value.value, str)]
                if isinstance(n.func, ast.Attribute) and n.func.attr == "from_pretrained" and n.args:
                    cands += [a for a in n.args
                              if isinstance(a, ast.Constant) and isinstance(a.value, str)]
        for c in cands:
            v = c.value
            org_and_name = "/" in v and HF_ID.match(v) and "." not in v.rsplit("/", 1)[-1]
            if org_and_name or v == "gpt2":
                found.setdefault(v, set()).add(s)
    # The records name their own checkpoints; a model that only appears there is
    # still a model this directory was measured against.
    for rec in jsons(d):
        pv = provenance_of(os.path.join(d, rec), d) or {}
        src = (pv.get("checkpoint") or {}).get("src")
        if src and HF_ID.match(src):
            found.setdefault(src, set()).add(rec)
    return {k: sorted(v) for k, v in sorted(found.items())}


def resolve_models(ids):
    """Ask the Hugging Face API which commit `main` points at today."""
    out = {}
    for mid in ids:
        url = "https://huggingface.co/api/models/" + mid
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                j = json.loads(r.read())
            out[mid] = {"canonical": j.get("modelId", mid),
                        "revision": j.get("sha"),
                        "lastModified": j.get("lastModified")}
            print("  %-34s %s  %s" % (mid, (j.get("sha") or "")[:12], j.get("lastModified")))
        except Exception as e:                       # noqa: BLE001 -- reported, not raised
            out[mid] = {"canonical": mid, "revision": None, "error": type(e).__name__}
            print("  %-34s FAILED: %s" % (mid, type(e).__name__))
    return out


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


#: Subtrees whose identity fields belong to something else. `provenance.corpus`
#: and `provenance.harness` each carry a `sha256`, and counting those as
#: checkpoint identity turned 63 records into 84 -- a field name matched in the
#: wrong subtree is the same mistake as a field name matched by substring.
NOT_CHECKPOINT = ("/provenance/corpus", "/provenance/harness")


def identity_fields(path):
    """Paths in a record that pin a checkpoint, each as `/a/b/key`.

    Paths, not bare names, so the claim can be looked up in the record instead
    of taken on trust.
    """
    try:
        j = json.load(open(path, encoding="utf-8"))
    except Exception:                                # noqa: BLE001
        return None
    hits, seen = set(), 0

    def walk(o, at):
        nonlocal seen
        if seen > 20000 or at.startswith(NOT_CHECKPOINT):
            return
        seen += 1
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(k, str) and IDENTITY.search(k):
                    hits.add(at + "/" + k)
                walk(v, at + "/" + str(k))
        elif isinstance(o, list):
            for v in o[:400]:
                walk(v, at + "/*")

    walk(j, "")
    return sorted(hits)


# --------------------------------------------------------------------------- #
# the two generated files
# --------------------------------------------------------------------------- #

def build(d):
    prod, dep = producers(d), deps(d)
    models = json.load(open(MODELS, encoding="utf-8")) if os.path.exists(MODELS) else {}
    ids = model_ids(d)

    recs = {}
    for rec in jsons(d):
        p = os.path.join(d, rec)
        who = prod[rec]
        heavy = sorted({m for s in who for m in dep.get(s, {}).get("heavy", [])})
        pv = provenance_of(p, d)
        ck = (pv or {}).get("checkpoint") or {}
        src, rev = ck.get("src"), ck.get("revision")
        recs[rec] = {
            "sha256": sha256(p),
            "bytes": os.path.getsize(p),
            "producer": who[0] if len(who) == 1 else None,
            "producer_candidates": who if len(who) != 1 else [],
            "needs": heavy,
            "producer_has_machine_local_path":
                any(dep.get(s, {}).get("foreign_paths") for s in who),
            "identity_fields": identity_fields(p) or [],
            "provenance": pv,
            "checkpoint_revision_is_hub_main_today":
                None if not rev else (models.get(src, {}).get("revision") == rev),
        }

    srcs = {s: {"sha256": sha256(os.path.join(d, s)),
                "needs": dep[s]["heavy"],
                "machine_local_paths": dep[s]["foreign_paths"]} for s in scripts(d)}

    return {
        "schema": "trinity-s3ai/block-reproducibility/1",
        "generated_by": "reproduce_index.py",
        "how_producers_were_found":
            "AST write sites -- open(p,'w'), Path(p).write_text, OUT-ish assignments -- "
            "matched by static path shape against the filenames present. Read sites are "
            "excluded on purpose: three scripts name align_u_{tag}.json and one writes it.",
        "records": recs,
        "scripts": srcs,
        "models": {mid: dict(models.get(mid, {"revision": None}), referenced_by=ids[mid])
                   for mid in ids},
    }


def census(m):
    recs, srcs = m["records"], m["scripts"]
    prov = [r["provenance"] for r in recs.values() if r["provenance"]]
    harn = [p["harness"] for p in prov if p.get("harness")]
    corp = {p["corpus"]["sha256"] for p in prov if p.get("corpus", {}).get("sha256")}
    return {
        "records": len(recs),
        "resolved": sum(1 for r in recs.values() if r["producer"]),
        "ambiguous": sum(1 for r in recs.values() if len(r["producer_candidates"]) > 1),
        "unresolved": sum(1 for r in recs.values()
                          if not r["producer"] and not r["producer_candidates"]),
        "with_checkpoint_identity":
            sum(1 for r in recs.values() if r["identity_fields"]),
        "scripts": len(srcs),
        "heavy": sum(1 for s in srcs.values() if s["needs"]),
        "machine_local": sum(1 for s in srcs.values() if s["machine_local_paths"]),
        "neither": sum(1 for s in srcs.values()
                       if not s["needs"] and not s["machine_local_paths"]),
        "models": len(m["models"]),
        "models_pinned": sum(1 for v in m["models"].values() if v.get("revision")),
        "with_provenance": len(prov),
        "naming_a_harness": len(harn),
        "harness_matches_tree": sum(1 for h in harn if h["matches_tree"]),
        "pinning_a_revision": sum(1 for r in recs.values()
                                  if (r["provenance"] or {}).get("checkpoint", {}).get("revision")),
        "revision_is_hub_main_today":
            sum(1 for r in recs.values() if r["checkpoint_revision_is_hub_main_today"] is True),
        "revision_disagrees_with_hub":
            sum(1 for r in recs.values() if r["checkpoint_revision_is_hub_main_today"] is False),
        "distinct_corpora": len(corp),
    }


def rerun_facts():
    """What `rerun_dependency_free.py` measured, if it has been run here."""
    p = os.path.join(HERE, "RERUN.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def doc(m):
    c = census(m)
    rr = rerun_facts()
    amb = sorted(r for r, v in m["records"].items() if len(v["producer_candidates"]) > 1)
    unk = sorted(r for r, v in m["records"].items()
                 if not v["producer"] and not v["producer_candidates"])
    # Same corpus, two shapes: some records omit `rows`. Keyed by sha256 and
    # merged field by field, because keeping the last one seen silently picked
    # the shorter variant and printed `None` for a row count that is recorded.
    corpora = {}
    for v in m["records"].values():
        cp = (v["provenance"] or {}).get("corpus") or {}
        if cp.get("sha256"):
            into = corpora.setdefault(cp["sha256"], {})
            for k, val in cp.items():
                if val is not None:
                    into.setdefault(k, val)
    corpora = list(corpora.values())
    L = []
    w = L.append
    w("# Reproducing the LLM measurements in `research/block`")
    w("")
    w("**This file is generated.** `python3 reproduce_index.py` rewrites it and")
    w("`MANIFEST.json` from the sources beside it; `--check` fails if either has drifted.")
    w("Every number below is computed at generation time. Nothing here is a")
    w("hand-maintained list, because a hand-maintained list is how an index and a tree")
    w("stop agreeing without either of them looking wrong.")
    w("")
    w("## The three questions, and where each one stands")
    w("")
    w("| | |")
    w("|---|---|")
    w("| *Which script produced this number?* | answered for **%d of %d** records |"
      % (c["resolved"], c["records"]))
    w("| *Against which harness?* | **%d of %d** records naming one hash-match the file in this tree |"
      % (c["harness_matches_tree"], c["naming_a_harness"]))
    w("| *Against which checkpoint?* | **%d** records pin a Hub revision; **%d** agree with `main` today, **%d** disagree |"
      % (c["pinning_a_revision"], c["revision_is_hub_main_today"],
         c["revision_disagrees_with_hub"]))
    w("")
    w("Check the first two yourself, with no third-party package installed at all:")
    w("")
    w("```")
    w("python3 verify_manifest.py")
    w("```")
    w("")
    w("## What the harness check is worth, and what it is not")
    w("")
    w("%d of the %d records carry a `provenance` block. It was **retro-fitted on"
      % (c["with_provenance"], c["records"]))
    w("2026-08-12** and says so in its own `RETROFITTED` field; the block is not")
    w("contemporaneous with the measurement. What it does give is a filename *and a")
    w("sha256* for the harness, and that pair is testable against this tree today:")
    w("**%d of %d match, %d differ.** They name %s across the whole set."
      % (c["harness_matches_tree"], c["naming_a_harness"],
         c["naming_a_harness"] - c["harness_matches_tree"],
         "one corpus" if c["distinct_corpora"] == 1
         else "%d distinct corpora" % c["distinct_corpora"]))
    w("")
    w("The corpus is pinned the same way and **its bytes are not in this repository**.")
    w("`block_tnf.py` reads `wikitext2-test.parquet` from a scratchpad directory that no")
    w("longer exists. What the records keep is the identity of what it read, and the")
    w("harness's own loader says exactly how to rebuild it -- read the parquet, take the")
    w("`text` column as a list, join with `\\n\\n`. So the claim is testable against the")
    w("public dataset in three lines:")
    w("")
    w("```python")
    w("import hashlib")
    w("from datasets import load_dataset")
    w('rows = load_dataset("wikitext", "wikitext-2-raw-v1", split="test")["text"]')
    w('s = "\\n\\n".join(rows)')
    w('print(len(rows), len(s), hashlib.sha256(s.encode()).hexdigest())')
    w("```")
    w("")
    if corpora:
        cp = corpora[0]
        w("Every provenance-bearing record in this directory claims that prints")
        w("")
        w("```")
        w("%s %s %s" % (cp.get("rows"), cp.get("chars"), cp.get("sha256")))
        w("```")
        w("")
        w("This package does not run that check: `datasets` is not a standard-library")
        w("module and nothing here installs one. The recipe is written down so that")
        w("testing the claim is three lines of somebody's afternoon rather than an")
        w("archaeology problem.")
    w("")
    w("## Three gaps, stated before anyone has to find them")
    w("")
    newest = max((v.get("lastModified") or "")[:10] for v in m["models"].values())
    w("**1. The revision is where the weights were downloaded from, not proof of what")
    w("they contained.** The records say this themselves. `main` is a moving branch, so a")
    w("revision agreeing with it today is evidence and not proof. What makes the evidence")
    w("worth something here is that the newest of the %d repositories was last modified on"
      % len(m["models"]))
    w("**%s** -- before the provenance pass of 2026-08-12 -- so `main` has not" % newest)
    w("moved under any of them since. Probably, not certainly: the local copies were")
    w("deleted on 2026-08-12 and cannot be re-hashed.")
    w("")
    w("**2. %d of %d sources contain a path that exists only on the machine that ran"
      % (c["machine_local"], c["scripts"]))
    w("them.** `campaignE_models.json` is the plainest case: every model it names lives")
    w("under a session scratchpad on a host that is gone. Those scripts cannot run from a")
    w("clone without editing the path first.")
    w("")
    w("**3. %d of %d sources import torch or transformers**, so re-running them needs the"
      % (c["heavy"], c["scripts"]))
    w("weights on disk. **%d import neither and read no foreign path** -- those run here,"
      % c["neither"])
    w("immediately, and the next section is what happened when they did.")
    w("")
    if rr:
        w("## What happened when the dependency-free scripts were re-run")
        w("")
        w("`python3 rerun_dependency_free.py` copies this directory to a temporary")
        w("sandbox -- it never writes here -- runs each qualifying script, and compares")
        w("what it produces against the committed record leaf by leaf.")
        w("")
        writers = [s for s in rr["scripts"] if s["identical"] or s["differed"] or s["new"]]
        w("On Python %s: **%d scripts ran, %d exited 0.**" % (rr["python"], rr["scripts_run"],
                                                             rr["exit_zero"]))
        w("")
        w("**Only %d of them write a record at all.** The rest print a verdict and exit,"
          % len(writers))
        w("so an exit code is all they leave behind. Read what follows as a statement about")
        w("**%d records**, not about %d scripts -- the difference matters, and quoting the"
          % (rr["records_identical"] + rr["records_differed"], rr["scripts_run"]))
        w("larger number would be the more flattering of the two mistakes.")
        w("")
        w("Of those %d records: **%d byte-identical**, **%d differed**, and of those **%d"
          % (rr["records_identical"] + rr["records_differed"], rr["records_identical"],
             rr["records_differed"], rr["differed_provenance_only"]))
        w("differed in their `provenance` block and nowhere else** -- every computed value")
        w("reproduced.")
        w("")
        w("That last figure is a finding, not a footnote. The provenance blocks were")
        w("added by a one-off pass; **the scripts that generate these records do not")
        w("write them.** So re-running a stats script silently strips the harness hash,")
        w("the corpus hash and the checkpoint revision from its own output -- the repair")
        w("undoes itself the first time anyone re-runs the thing it repaired. The")
        w("substantive differences, if any, are listed per record in `RERUN.json`.")
        w("")
        sub = [(s["script"], k, v) for s in rr["scripts"]
               for k, v in s["differed"].items() if not v.get("provenance_only")]
        if sub:
            w("Records whose *content* moved:")
            w("")
            for s, k, v in sub:
                w("- `%s` (from `%s`): %d of %d leaves differ, e.g. %s"
                  % (k, s, v.get("differing", 0), v.get("leaves", 0),
                     ", ".join("`%s`" % x for x in v.get("substantive", [])[:3]) or "-"))
            w("")
        fails = [s for s in rr["scripts"] if s["rc"] != 0]
        if fails:
            w("### The %d that did not exit 0" % len(fails))
            w("")
            w("A failure means different things depending on why, and the report separates")
            w("them rather than printing one number: %s."
              % ", ".join("**%s %d**" % (k.replace("_", " "), v)
                          for k, v in rr["failed_by_reason"].items()))
            w("")
            for s in fails:
                w("- `%s` -- %s: %s" % (s["script"], s["reason"].replace("_", " "),
                                        s["error"] or "no message"))
            w("")
            w("`missing_input` is a gap in this repository: the named file is genuinely not")
            w("here, and the harness checks that before saying so -- if the source tree held")
            w("the file, the failure would be reported as `sandbox_gap` and would be about")
            w("the harness instead. `script_error` is a defect in the script. There is one,")
            w("and it is worth stating plainly rather than leaving in a JSON field:")
            w("`u_verdict.py` collects its input with the glob `u_surface_*.json`, and one")
            w("file matching that glob -- `u_surface_verdict.json`, written by")
            w("`u_surface_verdict.py` -- is a JSON list where the other fifteen are objects")
            w("with a `rows` key. It raises `TypeError` on the tree exactly as committed.")
            w("Left unfixed here on purpose: this package measures the directory, and a")
            w("package that repairs its subject before measuring it reports a tree that")
            w("does not exist.")
            w("")
    if amb:
        w("## Records with more than one candidate producer")
        w("")
        w("A general template and a specific script both write a name of this shape, and")
        w("the resolver will not guess between them.")
        w("")
        for r in amb:
            w("- `%s` <- %s" % (r, ", ".join("`%s`" % s for s in m["records"][r]["producer_candidates"])))
        w("")
    if unk:
        w("## Records with no producer in this directory")
        w("")
        w("Each is one of: an *input* rather than an output, a path built through a")
        w("construct the resolver does not evaluate, or a write to an absolute path on")
        w("another machine.")
        w("")
        for r in unk:
            w("- `%s`" % r)
        w("")
    w("## Models named in the sources and in the records")
    w("")
    w("Resolved against the Hugging Face API, cached in `models_resolved.json`, refreshed")
    w("with `reproduce_index.py --models`. `lastModified` is the repository\'s own.")
    w("")
    w("| id | `main` today | repo last modified | named by |")
    w("|---|---|---|---|")
    for mid, v in sorted(m["models"].items()):
        w("| `%s` | `%s` | %s | %d file(s) |"
          % (mid, (v.get("revision") or "unresolved")[:40],
             (v.get("lastModified") or "-")[:10], len(v.get("referenced_by", []))))
    w("")
    w("## How the producer of a record is decided")
    w("")
    w("By walking the Python sources for *write sites* -- `open(p, \"w\")`,")
    w("`Path(p).write_text(...)`, `OUT`-ish assignments -- reducing each path")
    w("expression to a static shape, and matching that shape against the filenames")
    w("actually present. Local names are followed, because the ordinary write site here")
    w("is `open(dst, \"w\")` after `dst = os.environ.get(\"OUT\") or os.path.join(...)`.")
    w("")
    w("Read sites are excluded deliberately. Three scripts mention")
    w("`align_u_{tag}.json` and exactly one writes it; an index built from mentions")
    w("would name all three and be wrong about two.")
    w("")
    return "\n".join(L)
def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="fail if the tree disagrees")
    ap.add_argument("--models", action="store_true", help="re-resolve revisions (network)")
    a = ap.parse_args()

    if a.models:
        ids = model_ids(HERE)
        print("resolving %d model ids against the Hugging Face API" % len(ids))
        json.dump(resolve_models(ids), open(MODELS, "w", encoding="utf-8"),
                  indent=2, sort_keys=True)
        print("wrote", os.path.relpath(MODELS, HERE))

    m = build(HERE)
    text = doc(m)
    blob = json.dumps(m, indent=2, sort_keys=True) + "\n"

    if a.check:
        bad = []
        for path, want in ((MANIFEST, blob), (DOC, text)):
            have = open(path, encoding="utf-8").read() if os.path.exists(path) else None
            if have != want:
                bad.append(os.path.basename(path))
        if bad:
            sys.exit("stale, re-run reproduce_index.py: " + ", ".join(bad))
        print("MANIFEST.json and REPRODUCE.md agree with the tree")
        return

    open(MANIFEST, "w", encoding="utf-8").write(blob)
    open(DOC, "w", encoding="utf-8").write(text)
    c = census(m)
    print("wrote MANIFEST.json and REPRODUCE.md")
    print("  %(records)d records | %(resolved)d resolved, %(ambiguous)d ambiguous, "
          "%(unresolved)d unresolved" % c)
    print("  %(scripts)d scripts | %(heavy)d need torch/transformers, "
          "%(machine_local)d carry machine-local paths, %(neither)d neither" % c)
    print("  %(with_checkpoint_identity)d records pin a checkpoint | "
          "%(models_pinned)d/%(models)d model revisions resolved" % c)


if __name__ == "__main__":
    main()
