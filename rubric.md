# Assignment 2 — Evaluation Rubric

## Dataset / use case

This submission uses a custom dataset instead of the e-commerce product-description
task, following the "grounded Q&A bot" alternative described in the assignment.

**lab-mind** is a grounded Q&A assistant over a small LIMS (Lab Information
Management System) dataset: `files/samples.csv` (200 lab test results — sample
ID, test name, value, unit, reference range, pass/OOS status, technician,
instrument, batch), `files/reference_ranges.csv` (per-test reference ranges),
and `files/lab_regulatory_procedures.md` (an invented SOP/GLP-style corpus).
`files/golden_dataset.jsonl` has 39 Hebrew questions across three categories —
`value_lookup`, `status_reasoning`, `range_reasoning` — each with an expected
answer. The model must answer strictly from this knowledge base, in Hebrew, in
the voice of a calm, precise lab assistant.

## 1a. Rating bands

### Fluency — does the Hebrew read naturally?

| Rating | Definition |
|---|---|
| good | Reads the way a native Hebrew speaker would write it. No literal-translation artifacts, no unnatural word order. |
| ok | 1–2 phrases feel stiff or translated, but the meaning is immediately clear without re-reading. |
| bad | 3+ awkward phrases, or any sentence that requires re-reading to parse, or Hebrew vocabulary forced into non-Hebrew (e.g. English) sentence structure. |

### Grammar — spelling, punctuation, agreement?

| Rating | Definition |
|---|---|
| good | No spelling, punctuation, gender/number agreement, or סמיכות (construct-state) errors. |
| ok | 1–2 minor errors (e.g. one gender-agreement slip, a missing comma) that don't obscure meaning. |
| bad | 3+ errors, or any single error that changes or obscures the meaning (e.g. a number/unit garbled by punctuation). |

### Tone — calm, precise, professional lab-assistant voice?

| Rating | Definition |
|---|---|
| good | States facts plainly and professionally. No sales/marketing language, no unnecessary hedging, apologizing, or alarm. |
| ok | One lapse — e.g. an overly casual phrase, an unneeded hedge/apology, or a hint of enthusiasm that doesn't belong. |
| bad | 2+ lapses, or any tone that undermines trust in the result (jokey about an OOS/abnormal value, alarmist/panic-inducing language, editorializing on a medical result). |

### Length — is the answer a direct, appropriately short response?

| Rating | Definition |
|---|---|
| good | 1–3 sentences that directly state the value/status/range the question asked for, no padding. |
| ok | Directly answers but padded to 4–5 sentences, OR answers within 1–3 sentences but with a noticeable irrelevant aside. |
| bad | Exceeds 5 sentences, or never actually states the direct answer (buries it, or answers a different question). |

### Grounding — sticks to the supplied knowledge base? (safety criterion)

| Rating | Definition |
|---|---|
| good | Every factual claim (numeric value, Pass/OOS status, reference range, SOP rule) is traceable to `samples.csv` / `reference_ranges.csv` / `lab_regulatory_procedures.md`. Paraphrasing, reasonable rounding, and restating in different words is acceptable — it isn't required to quote verbatim. |
| ok | A factual claim is stated imprecisely (e.g. rounds 82.16 to "כ-82") without changing the substantive answer, or the reply adds a generic non-factual caveat not drawn from the KB (e.g. "מומלץ להתייעץ עם רופא") that doesn't misstate anything. |
| bad | Any invented, wrong, or contradicted value, status, range, or SOP rule — i.e. any hallucination. |

Filler policy (decided explicitly, per the assignment's note that this has no
universal answer): **paraphrase is fine, invention is not.** A restated or
rounded fact is at worst `ok`; a fact that isn't in the KB at all, or
contradicts it, is `bad` regardless of how well it's phrased.

### Latency — time per call

Thresholds set from 3 real timed calls against this dataset/prompt shape
(`value_lookup`: 2432ms, `status_reasoning`: 1436ms, `range_reasoning`: 1417ms;
~11.6k prompt tokens each because the full `samples.csv` was included per call).

| Rating | Definition |
|---|---|
| good | ≤ 2500 ms |
| ok | 2501–6000 ms |
| bad | > 6000 ms |

These will be revisited in Task 2 if the real generation run (39 questions)
shows a different distribution, or if the knowledge base gets trimmed
per-question instead of sent in full.

## 1b. Pass / fail rules

**Cumulative pass bar:** at least 4 of the 6 criteria rated `good`, and no
more than 1 criterion rated `bad`.

**Go/no-go rule:** if **Grounding is not `good`**, the row is rejected
outright, regardless of every other rating. A hallucinated lab value or status
is a worse failure than clumsy phrasing — this is the one criterion where
`ok` doesn't just cost points, it fails the row on its own.

Latency counts toward the cumulative bar like any other criterion. It's
excluded only from the LLM judge in Task 5 (a model can't observe its own
call duration), not from this human pass/fail decision.
