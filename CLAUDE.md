# Working instructions for this repository

## Who this is for

Sina Sabzevar. MSc Electrical Engineering (University of Tehran). Works on causal discovery
and effective connectivity in resting-state fMRI — schizophrenia and epilepsy. Currently a
data scientist at Hamrah-e Aval (MCI). Applying for funded PhD positions, with a chosen
strategy of **advertised, salaried positions in continental Europe, applied to continuously**
(see `strategy/target-labs.md` and `strategy/application-letter-template.md`).

---

## Standing task: turn a job advertisement into a letter

**When Sina pastes a job advertisement, a position description, or a link, produce a finished
letter without being asked again.** This is a standing arrangement, not a one-off request.

### Step 1 — pick the template

| Posting | Template | Register | Length |
|---|---|---|---|
| Advertised PhD/postdoc, PI named, project described | `letters/cover-example.tex` | direct, technical | 320–400 w, 1 page |
| University portal, graduate programme, committee-facing, asks for a "motivation letter" | `letters/motivation-example.tex` | narrative permitted | 500–650 w |
| Research engineer, research assistant, industry ML role | `letters/job-example.tex` | business-formal | 220–300 w |

If the advertisement states a word limit or asks specific questions, those override the table.

### Step 2 — read `strategy/facts.md` before writing

That file holds his real figures — cohort sizes, metrics, dates, links. **Use those values.**

### Step 3 — the rule that overrides everything else

**Never invent a fact about him.** Not a sample size, a metric, a publication, a venue, a
score, a date, an employer, a skill, or a degree. This is a real application to real people
and a fabricated claim is checkable, disqualifying, and his problem rather than yours.

If a fact is not in `strategy/facts.md` and he has not given it in conversation, leave the
`\fillme{...}` marker in place and **tell him in the reply exactly which ones are still
unfilled**. A letter delivered with three honest gaps is correct. A letter delivered with
three plausible inventions is a serious failure.

The same applies to the advertisement: do not claim he has experience the ad asks for unless
`facts.md` supports it. Where he does not match a requirement, say so to him and let him
decide — do not paper over it.

### Step 4 — write, compile, deliver

1. Copy the chosen template to `letters/<type>-<yyyy-mm>-<institution>.tex`
   (e.g. `letters/cover-2026-11-maastricht.tex`). Never overwrite the `*-example.tex` files.
2. Fill it from the advertisement and `facts.md`.
3. `cd letters && pdflatex -interaction=nonstopmode <file>.tex`
4. Verify: exit 0, **one page** for cover and job letters, no `Overfull` boxes, no `! ` errors.
   If it runs to two pages, cut from paragraph 3 — never from paragraph 2.
5. Send the PDF with `SendUserFile`, and in the reply list any remaining `FILL` markers.
6. Commit to the working branch and push.

### Step 5 — quality gates, applied before delivering

- **The reuse test.** Could this letter be sent to a different advertisement unchanged? If yes,
  paragraph 2 has failed. Rewrite it around the specific technical content of *this* project.
- Paragraph 2 must name what the project's work actually is, in plain words, and connect it to
  something he has done with a number attached.
- No "I am writing to express my interest". No paragraph admiring the university, the city or
  the country — except in a motivation letter, where "why this group" is expected and must be
  specific (their method line, their cohort, a named paper), never scenic.
- No chronological retelling of the CV; it is attached.
- State availability and relocation readiness in one plain sentence. Do not over-explain visas.

`strategy/application-letter-template.md` has the full reasoning, a worked example, and the
failure-mode list. Read it if any of the above is unclear.

---

## Other contents

- `cv/sina_sabzevar_cv.tex` — the CV. Two pages. Same typography as the letters.
- `letters/ssletter.sty` — shared letterhead. Edit the contact macros here, not per letter.
- `strategy/target-labs.md` — evidence-based lab shortlist with per-lab hooks.
- `prompts/` — build briefs for autonomous local agent runs.

## Conventions

- Letters and CV use `pdflatex`. `ssletter.sty` takes `[final]` to hide the red FILL markers;
  draft mode is the default and shows them.
- Red `[FILL: ...]` markers are unreplaced placeholders. Never deliver a document as finished
  while any remain — say which are left.
- Commit per logical change and push to the working branch.
