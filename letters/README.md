# Letters

One shared letterhead, three registers. Everything matches the CV's typography so an
application reads as one document set.

```
ssletter.sty            shared preamble, letterhead, FILL macro -- edit contacts HERE
cover-example.tex       advertised PhD/postdoc, PI-facing        1 page, 320-400 words
motivation-example.tex  portal / programme, committee-facing     500-650 words
job-example.tex         research engineer / RA / industry        220-300 words
```

## Making a new letter

```bash
cp cover-example.tex cover-2026-11-maastricht.tex
# edit, then:
pdflatex -interaction=nonstopmode cover-2026-11-maastricht.tex
```

Never edit the `*-example.tex` files themselves — they are the masters.

Red `[FILL: ...]` markers show what is unreplaced. Once every one is gone, switch
`\usepackage{ssletter}` to `\usepackage[final]{ssletter}` and recompile for the version you
actually send.

## Which one

- **Cover letter** — a named PI, a described project. Argues *project fit*. Paragraph 2 is the
  whole letter; the rest is packaging.
- **Motivation letter** — a portal or committee, often no single PI. Narrative is wanted here,
  and so is a *specific* "why this group": their method line, their cohort, a paper you read.
  Never the city.
- **Job cover letter** — requirements in, evidence out, every claim carrying a number. No
  research narrative.

## The test

Read the finished letter and ask: *could I send this to a different advertisement unchanged?*
If yes, paragraph 2 has failed. That is the only quality gate that matters.

Full reasoning, a worked example and the failure-mode list: `../strategy/application-letter-template.md`.
