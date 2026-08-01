#!/usr/bin/env python3
"""The single list of bibliography defects. Data only -- no output, no fetching.

BIBLIOGRAPHY_FIXES.md (the table an author reads) and CORRECTED_BIBITEMS.tex (the
LaTeX an author pastes) were built from two independently maintained lists. They
drifted: the table reached 20 entries while the .tex still covered 11, so anyone
working from the .tex would have silently skipped nine defects, including two
outright misattributions.

Both generators now import from here. Adding a defect in one place updates both.

Fields:
  paper   "A" (arXiv:2606.05017v3), "B" (arXiv:2606.09686v2), or
          "RU" (trinity-papers-ru/paper1-goldenfloat/main_ru.tex, the VAK submission)
  ref     the bibliography number as printed
  ident   ("arxiv", id) | ("doi", id) | ("hal", id) | ("url", url) | ("none", "")
  defect  short class, for the table's last column
  note    longer explanation, for entries a generator cannot describe from metadata
  fix     what to do, where the fix is not simply "use the resolved title"
  key     LaTeX citation key
"""

DEFECTS = [
    # ---- Paper B ---------------------------------------------------------------
    dict(paper="B", ref="[1]", ident=("arxiv", "2606.05017"), key="goldenfloat2026",
         defect="wrong title — the companion paper"),
    dict(paper="B", ref="[2]", ident=("arxiv", "2412.20273"), key="hunhold2024integer",
         defect="wrong title — different work"),
    dict(paper="B", ref="[3]", ident=("arxiv", "2511.12294"), key="proofwright2025",
         defect="wrong title AND wrong subject"),
    dict(paper="B", ref="[4]", ident=("arxiv", "2602.15965"), key="flops2026",
         defect="paraphrased title"),
    dict(paper="B", ref="[8]", ident=("arxiv", "2601.19213"), key="m2xfp2026",
         defect="wrong title — subtitle invented"),
    dict(paper="B", ref="[10]", ident=("arxiv", "2504.07835"), key="pychop2025",
         defect="paraphrased title"),
    dict(paper="B", ref="[13]", ident=("arxiv", "2412.20268"), key="hunhold2024solvers",
         defect="wrong title — different work"),
    dict(paper="B", ref="[19]", ident=("arxiv", "2606.04028"), key="sarnoff2026p3109",
         defect="no title given at all"),
    dict(paper="B", ref="[20]", ident=("arxiv", "2601.19026"), key="fasoli2026finer",
         defect="no title given at all"),
    dict(paper="B", ref="[11]", ident=("url",
         "https://arith2025.org/proceedings/215900a157.pdf"), key="wintersteiger2025",
         defect="wrong title — different work",
         note="cites *“Floating-point conformance testing in industrial practice”*. "
              "The PDF at the entry's own URL is *“Formal Verification of the IEEE "
              "P3109 Standard for Binary Floating-point Formats for Machine "
              "Learning”*, Wintersteiger, Imandra Inc. Right author, different work.",
         fix="Replace the title with the one at the cited URL.",
         latex="\\bibitem{wintersteiger2025} C. M. Wintersteiger, ``Formal "
               "Verification of the IEEE P3109 Standard for Binary Floating-point "
               "Formats for Machine Learning,''\n  Proc. IEEE ARITH 2025.\n  "
               "\\url{https://arith2025.org/proceedings/215900a157.pdf}."),
    dict(paper="B", ref="[12]", ident=("none", ""), key="libtakum",
         defect="wrong author initial",
         note="credits *C.* Hunhold for libtakum.",
         fix="The author is **Laslo** Hunhold — confirmed from the arXiv record "
             "for 2404.18603.",
         latex="\\bibitem{libtakum} L. Hunhold, ``libtakum: A reference C library "
               "for takum\n  arithmetic,'' "
               "\\url{https://github.com/takum-arithmetic/libtakum}, 2024--2025."),
    dict(paper="B", ref="[18]", ident=("none", ""), key="p3109interim",
         defect="version string on a document that has none",
         note="cites *IEEE SA P3109 Interim Report **v3.2.0***.",
         fix="That document carries no version number anywhere in its text. Cite "
             "it by retrieval date.",
         latex="\\bibitem{p3109interim} IEEE P3109 Working Group, ``IEEE P3109 "
               "Interim Report,''\n  IEEE Standards Association, retrieved "
               "2026-08-01.\n  \\url{https://github.com/P3109/Public}."),

    # ---- Paper A ---------------------------------------------------------------
    dict(paper="A", ref="[7]", ident=("arxiv", "2404.18603"), key="hunhold2024takum",
         defect="shortened title"),
    dict(paper="A", ref="[8]", ident=("arxiv", "2412.20273"), key="hunhold2024integerA",
         defect="paraphrased — scope changed"),
    dict(paper="A", ref="[9]", ident=("arxiv", "2408.10594"), key="hunhold2024codec",
         defect="paraphrased — invents 'VHDL'"),
    dict(paper="A", ref="[10]", ident=("arxiv", "2412.20268"), key="hunhold2024solversA",
         defect="paraphrased title"),
    dict(paper="A", ref="[22]", ident=("arxiv", "2402.17764"), key="bitnet2024",
         defect="shortened title"),
    dict(paper="A", ref="[26]", ident=("arxiv", "2511.01921"), key="fibbinary2025",
         defect="paraphrased — domain changed"),
    dict(paper="A", ref="[6]", ident=("hal", "hal-03195756"), key="dinechin2019posits",
         defect="wrong title AND wrong author list",
         note="cites *“Posits: the good, the bad and the ugly”* by de Dinechin, "
              "Forget, **Muller** and Uguen at `hal-03195756v3`. The HAL record for "
              "that id is *“Comparing posit and IEEE-754 hardware cost”* by "
              "**Forget, Uguen and de Dinechin** — different title, and Muller is "
              "not among its authors.",
         fix="Either correct the title and author list to the HAL record, or supply "
             "the HAL id of the paper actually meant — both works exist.",
         latex="% Two works exist; decide which was meant before pasting either.\n"
               "\\bibitem{dinechin2019posits} L. Forget, Y. Uguen, and F. de "
               "Dinechin, ``Comparing posit and\n  IEEE-754 hardware cost,'' 2021. "
               "\\texttt{hal-03195756}."),
    # ---- main_ru.tex (the Russian VAK submission, 56 bibitems) -----------------
    # Audited in pass 84. Four of its defects are inherited verbatim from Paper A,
    # which is what bibliographies maintained by copying do.
    dict(paper="RU", ref="[24]", ident=("arxiv", "2103.15940"), key="popescu2021",
         defect="wrong work — its own, not inherited"),
    dict(paper="RU", ref="[7]", ident=("arxiv", "2404.18603"), key="ru_hunhold_takum",
         defect="shortened title (same as Paper A [7])"),
    dict(paper="RU", ref="[8]", ident=("arxiv", "2412.20273"), key="ru_hunhold_integer",
         defect="paraphrased — scope changed (same as Paper A [8])"),
    dict(paper="RU", ref="[9]", ident=("arxiv", "2408.10594"), key="ru_hunhold_codec",
         defect="paraphrased — invents 'VHDL' (same as Paper A [9])"),
    dict(paper="RU", ref="[10]", ident=("arxiv", "2412.20268"), key="ru_hunhold_solvers",
         defect="paraphrased title (same as Paper A [10])"),
    dict(paper="RU", ref="[6]", ident=("hal", "hal-03195756"), key="ru_dedinechin",
         defect="wrong title AND wrong author list (same as Paper A [6])",
         note="carries Paper A [6] verbatim: *“Posits: the good, the bad and the "
              "ugly”* attributed to de Dinechin, Forget, **Muller** and Uguen at "
              "`hal-03195756`, whose record is *“Comparing posit and IEEE-754 "
              "hardware cost”* by Forget, Uguen and de Dinechin.",
         fix="Same correction as Paper A [6]."),
    dict(paper="RU", ref="[11]", ident=("doi", "10.1109/ARITH64983.2025.00019"),
         key="ru_hunhold_arith",
         defect="wrong work (same as Paper A [11])",
         note="carries Paper A [11] verbatim, including the DOI that resolves to "
              "*Evaluation of Bfloat16, Posit, and Takum Arithmetics in Sparse "
              "Linear Solvers* rather than to the ARITH hardware-evaluation paper.",
         fix="Same correction as Paper A [11]. Note this manuscript also cites that "
             "solvers paper at [10], so the duplication is present here too."),

    dict(paper="A", ref="[11]", ident=("doi", "10.1109/ARITH64983.2025.00019"),
         key="hunhold2025arith", defect="wrong work, and a duplicate of [10]",
         note="DOI 10.1109/ARITH64983.2025.00019 resolves to *Evaluation of "
              "Bfloat16, Posit, and Takum Arithmetics in Sparse Linear Solvers* "
              "(Hunhold and Quinlan) — **the same work [10] already cites**.",
         fix="Delete as a duplicate of [10]. If the ARITH 2025 hardware-evaluation "
             "paper was intended, it needs its own DOI — this one is not it.",
         latex="% [11] should be DELETED as a duplicate of [10]. No replacement is\n"
               "% supplied: the DOI given does not identify the intended work."),
]


def by_paper(p):
    return [d for d in DEFECTS if d["paper"] == p]


def arxiv_ids():
    return [d["ident"][1] for d in DEFECTS if d["ident"][0] == "arxiv"]
