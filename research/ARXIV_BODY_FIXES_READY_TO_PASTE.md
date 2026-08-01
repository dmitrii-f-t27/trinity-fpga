# Ready-to-paste body fixes — bibliography and one new subsection

> Produced 2026-07-31, pass 29. Companion to
> `ARXIV_ABSTRACTS_READY_TO_PASTE.md`: that file makes the abstract replacement
> mechanical, this one does the same for the body.
>
> **Every author list and title below was fetched from the arXiv API and is
> verbatim.** None is reconstructed from memory or from the papers' own prose —
> which is how four of Paper B's references went wrong in the first place.
>
> **Apply together with the abstract fixes.** An abstract-only replacement would
> ship these citation defects into a third public version.

---

## 1. Paper A — corrected bibitem

### 1.1 `flops2026` — placeholder author and paraphrased title

Current entry has **"Authors of FLoPS"** as the author and a paraphrased title, so
the work cannot be found by title search.

```latex
\bibitem{flops2026} T.-C. Chang, S. Park, J. P. Lim, and S. Nagarakatte,
``FLoPS: Semantics, Operations, and Properties of P3109 Floating-Point
Representations in Lean,'' \texttt{arXiv:2602.15965}, 2026.
\url{https://arxiv.org/abs/2602.15965}.
```

## 2. Paper A — three titles restored verbatim

All three were restructured from `Name: Subtitle` into `Subtitle (Name)`. The IDs
are right and the works are identifiable, but they are not findable by title
search. Titles below are exact.

```latex
\bibitem{seal2026} P. Pathania, R. Mehra, V. S. Sharma, V. Kaulgud, T. Nevels,
S. Podder, and A. P. Burden, ``SEALing the Gap: A Reference Framework for LLM
Inference Carbon Estimation via Multi-Benchmark Driven Embodiment,''
\texttt{arXiv:2603.02949}, 2026.

\bibitem{nanozk2026} Z. Wang, ``NanoZK: Privacy-Preserving Verifiable Inference
for Large Language Models via Layerwise Zero-Knowledge Proofs,''
\texttt{arXiv:2603.18046}, 2026.

\bibitem{zkcomposer2026} P. K. Sanjaya, C. Giannoula, V. Oktavian, M. Saeedi,
G. Sines, G. Saileshwar, and N. Vijaykumar, ``zkComposer: Decomposing Proof
Construction to Scale zkML,'' \texttt{arXiv:2607.08095}, 2026.
```

## 3. Paper A — three citations to add

### 3.1 The nearest FPGA neighbour (§5.1)

Published 2026-07-15, six weeks after Paper A, and not cited. It is also
independent external corroboration of the DSP limitation in §4 below.

```latex
\bibitem{jackofallscales2026} M. Mekhemer, A. Elsousy, B. Venkatesh, R. Rowley,
V. Betz, N. Kapre, and A. Boutros, ``Jack of All Scales: A Versatile FPGA Tensor
Block for MXFP Precisions,'' \texttt{arXiv:2607.13898}, 2026.
```

### 3.2 IEEE 754 — the base standard, currently uncited

A paper proposing a floating-point family, positioned against posit, takum,
OCP-MX and P3109, cites neither the base standard nor the tool its own experiment
depends on.

Verified against the **published** text on 2026-08-01: arXiv:2606.05017v3 carries
**33** references, and a search of all of them for "754", "TestFloat" and
"SoftFloat" returns nothing. Paper B already cites IEEE 754 as its ref [15];
mirroring that form keeps the two consistent.

> The count in an earlier draft of this section was **56**, taken from the local
> `main_ru.tex`. The published v3 has 33. The two artefacts differ, and every
> line-number reference below points at the manuscript, not at the preprint —
> check each against whichever you are editing.

```latex
\bibitem{ieee754_2019} IEEE Std 754-2019, ``IEEE Standard for Floating-Point
Arithmetic,'' IEEE, New York, NY, 2019.
\url{https://standards.ieee.org/ieee/754/6210/}.
```

### 3.3 TestFloat — an uncited tool dependency, not a related-work nicety

`main_ru.tex` line 1728 places **TestFloat-3** as the *correctness gate of the
pre-registered experiment*: an exhaustive run with 0 errors required over 1M
random samples before any area/timing result is accepted. A protocol that gates
its acceptance criterion on a tool must cite that tool (§7.2a).

```latex
\bibitem{hauser_testfloat} J. R. Hauser, ``Berkeley TestFloat,'' Release 3e,
2018. \url{http://www.jhauser.us/arithmetic/TestFloat.html}.
```

---

## 4. Paper A — new subsection on DSP versus soft logic

`main_ru.tex` has **zero** occurrences of `nodsp`, `DSP48`, `DSP block` or
`DSP-блок`. The paper reports an FPGA codec without stating that the
implementation is soft-logic-only, or why — while the project's own hardware
record is that GF multiply synthesis requires `-nodsp` because DSP48E1 inference
produces a routing failure (§5.2).

Draft, to sit in the FPGA section. Status tags are deliberate and should survive
editing:

> **Soft-logic implementation.** The GF codec is synthesised in soft logic with
> DSP inference disabled (`-nodsp`). Allowing the tool to infer DSP48E1 blocks for
> the GF multiplier produces a routing failure on the target device, so the
> soft-logic path is not a stylistic choice but a synthesis constraint
> `[measured on our substrate]`.
>
> The same wall has been reported independently from the other side. Mekhemer et
> al. \cite{jackofallscales2026} characterise MXFP dot products on Altera
> Agilex-5 and find that the DSP tensor mode *cannot* implement MXFP6 (E3M2) or
> any MXFP8 precision, forcing designers onto lower-density alternatives; they
> propose DSP tensor-mode modifications costing roughly 36\% additional DSP tile
> area. Their substrate, vendor and format family all differ from ours, so the
> agreement is `[externally corroborated, different substrate]` rather than a
> shared measurement.
>
> We draw no general conclusion about DSP architectures from two data points. The
> narrow claim is that hard DSP blocks fit narrow formats poorly on both devices
> examined, and that the two efforts respond to it differently — they modify the
> block, we avoid it.

---

## 5. Paper B — four corrected references

Audited against the v5 manuscript, so these are present in the current text, not
only on arXiv (§8).

### 5.1 [3] — wholly misattributed, and the intent must be settled first

The current entry credits *"C. Park, J.-H. Lim, S. Nagarakatte, ProofWright:
Towards verified floating-point arithmetic, arXiv:2511.12294v2"*. That ID resolves
to a different paper, by different authors, on a different subject.

**If arXiv:2511.12294 was the intended source:**

```latex
[3] B. Chatterjee, D. Zagieboylo, S. Damani, S. Hari, and C. Kozyrakis,
    "ProofWright: Towards Agentic Formal Verification of CUDA,"
    arXiv:2511.12294, 2025.
```

**If the Rutgers group's work was intended**, the ID is wrong and the correct
paper must be identified first. **Do not patch half of it** — an entry with the
right authors and the wrong ID is no better than the reverse.

### 5.2 [4], [19], [20] — verified verbatim

```latex
[4]  T.-C. Chang, S. Park, J. P. Lim, and S. Nagarakatte, "FLoPS: Semantics,
     Operations, and Properties of P3109 Floating-Point Representations in
     Lean," arXiv:2602.15965, 2026.

[19] F. A. Khattak and M. Mikaitis, "Accurate Models of NVIDIA Tensor Cores,"
     arXiv:2512.07004, 2025.

[20] J. Yao, H. Su, T. Liao, Z. Cheng, H. Zhang, X. Wang, and P. Viswanath,
     "TAO: Tolerance-Aware Optimistic Verification for Floating-Point Neural
     Networks," arXiv:2510.16028, 2025.
```

Note that **[4] and Paper A's `flops2026` are the same work mis-cited in both
papers** — one source of error, not two. Fix them together or the inconsistency
persists across the pair.

---

## 6. Application order

1. Paper B [3] — decide the intent first; it gates the entry.
2. Paper B [4], [19], [20] — mechanical.
3. Paper A `flops2026` — same work as B's [4]; keep them consistent.
4. Paper A — three restored titles (§2), mechanical.
5. Paper A — three added citations (§3).
6. Paper A — the DSP subsection (§4), the only item requiring editorial judgement.
7. Both abstracts, from `ARXIV_ABSTRACTS_READY_TO_PASTE.md`.

Items 1-6 are body edits; item 7 is the abstract. Submit as **one** replacement per
preprint.
