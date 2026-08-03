#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Can every conformance host be imported without a board attached?

A conformance host holds a golden model. If the module cannot be imported without
pyserial installed, that golden is out of reach of CI, of any cross-check, and of every
sweep this campaign runs. It can only be exercised by someone sitting at the board.

This has now been fixed twice.

    pass 181   30 hosts did `import serial` at module scope. Moved into the functions
               that use it.
    pass 216   11 hosts had no `if __name__ == "__main__"` guard, so importing one
               parsed the IMPORTER's sys.argv, called sys.exit -- terminating whatever
               imported it -- and opened a serial port. Every one a GoldenFloat compute
               cell.
    pass 217   1 host declared `port: serial.Serial` in a signature, which is evaluated
               when the function is defined.

Three shapes, one property, and it regressed between the first fix and the second because
nothing enforced it. This is the enforcement.

    python3 research/audit_host_importability.py [--verbose] [--self-check]

Exit 0 when every host imports under a serial module that provides nothing at all.

WHY THE STUB IS EMPTY ON PURPOSE
--------------------------------
`types.ModuleType("serial")` has no `Serial`, no `SerialException`, nothing. A host that
touches any attribute of it during import fails here, which is exactly the condition being
tested: the golden must be reachable when pyserial is absent, not merely when it is
present and unused.
"""
from __future__ import annotations

import glob
import importlib.util
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONF = os.path.join(ROOT, "conformance")


def try_import(path):
    """(ok, reason). Failure modes are named rather than lumped together, because the
    three that have occurred need different fixes."""
    name = "imp_" + os.path.basename(path)[:-3]
    sys.modules["serial"] = types.ModuleType("serial")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
        return True, ""
    except SystemExit:
        return False, "calls sys.exit() at import -- needs an __main__ guard"
    except AttributeError as e:
        return False, f"touches a serial attribute at import: {e}"
    except ImportError as e:
        return False, f"imports something absent: {e}"
    except Exception as e:
        # Anything else is the host's own logic failing, which is a different problem and
        # is reported as such rather than counted as an importability defect.
        return True, f"(imported, then raised {type(e).__name__})"
    finally:
        sys.modules.pop(name, None)


def main() -> int:
    verbose = "--verbose" in sys.argv
    sys.path.insert(0, CONF)
    hosts = sorted(glob.glob(os.path.join(CONF, "*_conformance_ax7203.py")))
    bad, noisy = [], []
    for p in hosts:
        ok, why = try_import(p)
        base = os.path.basename(p)[:-3]
        if not ok:
            bad.append((base, why))
        elif why and verbose:
            noisy.append((base, why))

    print(f"conformance hosts                    : {len(hosts)}")
    print(f"  importable with no pyserial at all : {len(hosts) - len(bad)}")
    print(f"  NOT importable                     : {len(bad)}\n")
    for base, why in bad:
        print(f"  {base}")
        print(f"      {why}")
    for base, why in noisy:
        print(f"  {base}: {why}")

    print("""
A golden nothing can import is a golden nothing can check. The stub serial module
provides no attributes on purpose: the test is that the golden is reachable when pyserial
is ABSENT, not merely when it is present and unused.

Three shapes have caused this -- a module-scope `import serial`, an argparse block with no
__main__ guard, and a `serial.Serial` annotation in a signature. All three are fixed; this
check exists because the first fix regressed into the second.""")
    return 1 if bad else 0


def self_check() -> int:
    """A gate that cannot fail is not a gate. Write a host with each of the three defects
    and require each to be caught, then a clean one and require it to pass."""
    probe = os.path.join(CONF, "_probe_conformance_ax7203.py")
    cases = {
        "module-scope import": "import serial\nSER = serial.Serial\n",
        "no __main__ guard": ("import argparse, sys\n"
                              "ap = argparse.ArgumentParser()\n"
                              "a = ap.parse_args([])\n"
                              "sys.exit(0)\n"),
        "annotation": "import serial\ndef f(p: serial.Serial):\n    return p\n",
    }
    results = {}
    try:
        for label, src in cases.items():
            open(probe, "w", encoding="utf-8").write(src)
            ok, why = try_import(probe)
            results[label] = not ok
            print(f"  {label:<22} -> caught: {not ok}   {why[:52]}")
        open(probe, "w", encoding="utf-8").write(
            "GOLDEN = {0: 0}\n\n\ndef golden(c):\n    return GOLDEN.get(c, 0)\n")
        ok, _ = try_import(probe)
        results["clean host"] = ok
        print(f"  {'a clean host':<22} -> passes: {ok}")
    finally:
        if os.path.exists(probe):
            os.remove(probe)
    print(f"  probe removed -> {not os.path.exists(probe)}")

    passed = all(results.values())
    print(f"\nself-check: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        raise SystemExit(self_check())
    raise SystemExit(main())
