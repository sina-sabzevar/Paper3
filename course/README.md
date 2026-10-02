# Paper 2 — a complete course in one notebook

`paper2_course.ipynb` rebuilds every idea in *Representation Dimension Is a Weak,
Non-Monotone Lever on Memorisation in Small-Sample Tabular Diffusion* from scratch and
tests each one on synthetic data where the true answer is known.

| Module | Topic |
|---|---|
| 0 | Setup |
| 1 | Synthetic tables, subsampling, validation split, deduplication, leakage control |
| 2 | Nearest-neighbour geometry: spacing shrinks as n^(−1/m); distance concentration |
| 3 | ρ, near-copy fraction, authenticity, k-NN precision/recall, energy distance; five generators with known behaviour |
| 4 | Representations (standard, quantile, PCA, random projection); JL scaling; the clamp; reconstruction residual; off-scale failures |
| 5 | DDPM from scratch: cosine schedule, ε-prediction, ancestral sampler with clamp; why a perfect denoiser copies |
| 6 | Claim 1 experiment: sample size, trajectories, minimum-over-checkpoints bias, censoring and Kaplan–Meier |
| 7 | Calibration: reference sampler, fixed-σ copier, σ invariance, log-scale artefact share, Mann–Whitney |
| 8 | Claim 2 experiment: dimension within PCA and random projection; U-shape; dimension copier; clamp test scaffold |
| 9 | Statistics toolkit on simulated result tables: cells, Spearman saturation, bootstrap over cells, partial R², cluster-robust SEs, permutation level, Simpson's paradox, composition, shape tests, bounded nulls, MDE, TOST, effect sizes, Holm |
| 10 | Claim 3: denoiser width and fidelity (underfitting vs generalisation) |
| 11 | Claim 4: downstream augmentation, ΔAUC, ratio confound |
| 12 | The four claims, the evidence, the attack surface; glossary |

## Run it

```bash
pip install numpy pandas scipy statsmodels matplotlib scikit-learn torch jupyter
jupyter notebook paper2_course.ipynb        # then Kernel → Restart & Run All
```

CPU only. The full run takes about 15 minutes; set `FAST = True` in the first code cell
for a shorter version. The notebook is committed with its outputs, so it can also be read
without running it.

## Two findings about the paper itself (Module 12)

1. §3.2 says sampling is deterministic; the released sweep code uses the stochastic
   (ancestral) DDPM sampler. Module 5 shows a noise-free posterior-mean chain collapses.
2. The dimension permutation test shuffles runs within (dataset × n × seed); Module 9.5
   shows that over-rejects when cells carry random effects. Shuffling dimension labels
   among cells is the exchangeable unit.
