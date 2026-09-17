# Target labs — evidence-based shortlist

Built from a literature search on 2026-09-17, not from memory. Every lab below is here because
of a specific recent paper, cited so you can read it before writing to anyone.

**What I verified:** the papers exist, the author lists are as quoted, and the affiliations are
as stated in the sources.
**What I did NOT verify:** whether anyone is currently recruiting, whether funding exists, or
application deadlines. Lab pages change weekly — check each one yourself before writing.

---

## The finding: you have two warm paths into the best lab for you, and you are using neither

### Bridge A — through your own referee

> Fallahi, A., Hoseini-Tabatabaei, N., Eivazi, F., Mohammadi Mobarakeh, N., Dehghani-Siahaki, H.,
> Alibiglou, L., Rostami, R., Mehvari Habibabadi, J., Hashemi-Fesharaki, S., Joghataei, M. T., &
> **Nazem-Zadeh, M.** (2023). *Dynamic causal modeling of reorganization of memory and language
> networks in temporal lobe epilepsy.* Annals of Clinical and Translational Neurology, 10(12),
> 2238–2254. doi:10.1002/acn3.51908

Your referee is **senior author** on a dynamic causal modelling study of effective connectivity
in temporal lobe epilepsy — 22 left-TLE, 13 right-TLE patients, task fMRI across four memory and
four language paradigms. He is now at Monash. That is not a reference letter; that is a
collaborator with an established TLE cohort, an established effective-connectivity method line,
and a position inside a Western institution.

### Bridge B — through your own department

> Zarghami, T. S., **Zeidman, P.**, **Razi, A.**, **Bahrami, F.**, & **Hossein-Zadeh, G.** (2023).
> *Dysconnection and cognition in schizophrenia: A spectral dynamic causal modeling study.*
> Human Brain Mapping. doi:10.1002/hbm.26251

Read the author list again. **Gholam-Ali Hossein-Zadeh** and **Fariba Bahrami** are at the
University of Tehran — the same School of Electrical and Computer Engineering where you did your
MSc under Araabi. They publish spectral DCM on **schizophrenia** with **Peter Zeidman** (UCL
Functional Imaging Laboratory, a core DCM developer) and **Adeel Razi** (Monash).

Zarghami is the precedent: a University of Tehran researcher who published schizophrenia
effective connectivity with Razi and Zeidman. That path exists. You are in the same building and
working on the same disorder with complementary methods.

**Both bridges lead to the same place.** Adeel Razi is Professor of Computational Neuroscience
and Director of the Computational Neuroscience Laboratory at the Turner Institute, Monash — and
he **developed DCM for resting-state fMRI**, which is the model-based counterpart to exactly
what you do. He is the single best-fit supervisor for you in the world, and you can reach him
through two people who already know your work.

---

## Tier 1 — warm paths. Do these first.

### Adeel Razi — Monash University (Australia)
Computational Neuroscience Laboratory, Turner Institute for Brain and Mental Health.
`research.monash.edu/en/persons/adeel-razi` · `adeelrazi.org`

**Why it fits:** he built spectral DCM for resting state. You do data-driven causal discovery on
resting state. These are the two halves of the same problem — model-based versus
constraint/score/functional-based recovery of directed connectivity — and they are rarely
compared head to head.

**The hook (use this, it is a real open question):** DCM starts from a specified model space and
compares models; PC, GES and LiNGAM search the space without one. *Do they recover the same
directed edges from the same schizophrenia data?* Where they disagree, which is wrong? Nobody has
systematically answered that, you have run one family, his group built the other, and you both
have schizophrenia cohorts. That is a PhD project in one sentence.

**Route in:** ask Nazem-Zadeh for the introduction. Do not cold-email this one.

### Peter Zeidman — UCL, Functional Imaging Laboratory (UK)
**Why it fits:** core DCM developer, co-author on the paper with your own department.
**The hook:** model validation. How do you establish that a winning DCM is right rather than
merely best among those compared — and does agreement with an assumption-free causal discovery
result count as evidence?
**Route in:** Hossein-Zadeh at UT can introduce you. Note the UK requires ATAS clearance for
Iranian nationals in most ML/engineering subjects; start that early.

---

## Tier 2 — strong topical fit, cold approach

### Kathryn Davis — University of Pennsylvania (USA)
> Lucas, A., Cornblath, E. J., Sinha, N., Caciagli, L., Hadar, P., Tranquille, A., Stein, J. M.,
> Das, S., & Davis, K. A. (2025). *Seizure-onset zone lateralization in temporal lobe epilepsy
> using 7T rs-fMRI: Direct comparison with 3T rs-fMRI.* Epilepsia.

**The hook:** they lateralise the seizure-onset zone from *undirected* resting-state connectivity
and quantify what 7T buys over 3T. You lateralise from *directed* connectivity. The question that
follows: does direction recover at 3T what field strength otherwise buys you? That matters
clinically, because most epilepsy centres do not have 7T.

### Victoria Morgan, Dario Englot, Catie Chang — Vanderbilt (USA)
> Sainburg, L. E., Roche, A., Makhoul, G. S., Rogers, B. P., Roberson, S. W., Meletti, S.,
> Vaudano, A. E., Chang, C., Englot, D. J., & Morgan, V. L. (2026). *The dynamic functional
> connectivity peak index: Detection of interictal epileptic activity with fMRI.* Epilepsia.

**The hook:** their index detects interictal activity from dynamic *functional* connectivity. A
directed version — does influence flow outward from the focus during those peaks? — is the
obvious next question and it is your method.

### John Duncan, Matthias Koepp (UCL Queen Square) with Georg Langs (Vienna)
> Nenning, K., Trimmel, K., Bartha-Doering, L., Berger, M., Koepp, M. J., Langs, G., Kasprian, G.,
> Duncan, J. S., & Bonelli, S. B. (2026). *Contralateral language network integration predicts and
> protects against naming decline after temporal lobe resection.* Epilepsia.

**The hook:** they predict post-surgical language decline from network reorganisation — which is
precisely the phenomenon Nazem-Zadeh's DCM paper models causally. Ask whether directed
reorganisation predicts outcome better than undirected integration. Strongest clinical-impact
framing on this list.

### Svitlana Zinger, Albert Aldenkamp, Jacobus Jansen — TU Eindhoven / Maastricht (Netherlands)
> Cîrstian, R., Pilmeyer, J., Bernas, A., Jansen, J. F., Breeuwer, M., Aldenkamp, A. P., &
> Zinger, S. (2023). *Objective biomarkers of depression: A study of Granger causality and wavelet
> coherence in resting-state fMRI.* Journal of Neuroimaging.

**The hook:** they use Granger causality for psychiatric biomarkers and Aldenkamp is an
epilepsy clinician — your exact two domains under one roof. Granger causality on BOLD is
vulnerable to regionally varying haemodynamic lag; ask how they handle it, and note that
LiNGAM-type methods trade that problem for a non-Gaussianity assumption instead.

### Shohei Shimizu — Shiga University / Osaka (Japan)
> Suzuki, K., Yamamichi, M., Osada, Y., Ushio, M., Nakajima, K., Masuya, H., & **Shimizu, S.**
> (2026). *Advances in causal discovery methods for ecological time series.* Biological Reviews.

**The hook:** Shimizu invented LiNGAM, which you use. The methods question you already have on
your website — LiNGAM assumes acyclicity, brain networks are cyclic — is one to put directly to
its author. A methods-side supervisor is an unusual and strong choice if you want to work on the
cycles problem rather than on applications.

### Yasumasa Okada, Saori Tanaka, Yuki Nakamura — ATR / Hiroshima (Japan)
> Nakamura, Y., Ishida, T., Tanaka, S. C., Mitsuyama, Y., Yokoyama, S., Shinzato, H., Itai, E.,
> Okada, G., Kobayashi, … (2026). *Distinctive alterations in the mesocorticolimbic circuits in
> various psychiatric disorders.* Psychiatry and Clinical Neurosciences.

**The hook:** this is cross-disorder circuit comparison — the third PhD direction listed on your
own website. They have the multi-disorder cohorts; you have the directed-connectivity method.
Japan is also among the more workable visa routes for Iranian nationals.

### Mark Woolrich — OHBA, University of Oxford (UK)
> Csaky, R., Es, M. W., Jones, O. P., & **Woolrich, M.** (2023). *Group-level brain decoding with
> deep learning.* Human Brain Mapping.
**The hook:** group-level versus individual-level inference — the second open question on your
site. Weaker topical fit on causality, but a methodologically serious group.

---

## What to do, in order

1. **Email Nazem-Zadeh this week.** Not for a letter — for an introduction to Razi, and to ask
   whether there is a project at Monash where your causal-discovery work complements his DCM
   line. He is your co-author and his own 2023 paper is the bridge. Reference it.
2. **Go and see Hossein-Zadeh at UT.** Same faculty as Araabi. Ask about the Razi and Zeidman
   collaboration and whether he would introduce you. A walk down a corridor beats fifty emails.
3. **Read the two bridge papers properly** (acn3.51908 and hbm.26251) before either conversation.
   You will be asked what you thought of them.
4. **Then, and only then**, cold-email Tier 2 — twenty letters with a real third paragraph each,
   not a hundred templated ones.
5. **Book the TOEFL retake regardless.** Monash requires roughly 79+ with 21+ in each band; your
   Writing 20 and Speaking 20 currently fail that, and it is the cheapest blocker on this list to
   clear. UCL wants considerably more.

## Caveats you must check yourself

- **Recruiting status and funding** for every lab above. Not verified.
- **Deadlines.** Monash graduate research scholarships run in rounds; UCL and US programmes have
  fixed annual deadlines (US: December for the following September).
- **Visa friction** varies sharply by country for Iranian nationals: Australia and Japan are
  generally more workable than the US; the UK additionally requires ATAS clearance for most
  ML and engineering subjects. Verify current requirements — mine is background knowledge, not
  a checked source.
