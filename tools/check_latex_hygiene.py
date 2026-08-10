#!/usr/bin/env python3
"""Defects LaTeX resolves silently, which a build check cannot see.

The paper carried four duplicate \\label definitions. LaTeX resolves a duplicate
in favour of the LAST one and emits no error, so twelve \\ref commands pointed at
theorems and tables other than the ones their sentences described -- nine of them
at a theorem about normalisation cascades where the text said 'logarithmic is the
floor'. The build reported zero errors and zero undefined references throughout.

It also carried markdown emphasis (**like this**) inside LaTeX, which renders as
literal asterisks.

Neither is an error to the compiler. Both are errors to a reader.
"""
import re, pathlib, sys, collections

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEX = sorted(ROOT.glob("research/**/*.tex"))
fails = []

for f in TEX:
    src = f.read_text(errors="ignore")
    rel = f.relative_to(ROOT)

    labels = re.findall(r"\\label\{([^}]+)\}", src)
    for name, n in collections.Counter(labels).items():
        if n > 1:
            fails.append(f"{rel}: \\label{{{name}}} defined {n} times -- "
                         f"every \\ref to it resolves to the last one, silently")

    # markdown emphasis inside LaTeX
    for m in re.finditer(r"\*\*[^*\n]{2,120}\*\*", src):
        line = src[:m.start()].count("\n") + 1
        fails.append(f"{rel}:{line}: markdown emphasis `{m.group(0)[:44]}` -- "
                     f"renders as literal asterisks")

    # a \ref to a label that is not defined anywhere in the same file
    refs = set(re.findall(r"\\(?:ref|eqref|autoref)\{([^}]+)\}", src))
    for r in sorted(refs - set(labels)):
        fails.append(f"{rel}: \\ref{{{r}}} has no \\label in this file")

print(f"tex files scanned: {len(TEX)}")
if fails:
    print(f"\nFAIL: {len(fails)} silent-defect(s)\n")
    for x in fails: print(f"  {x}")
    sys.exit(1)
print("OK: no duplicate labels, no markdown emphasis, every ref defined")
