# Chapter 6: capture-time admission artefact

Revision date: **26 October 2026**. This directory contains the corrected
baseline, complete sensitivity study, and figures supporting Chapter 6 of
Eduardo Ribas Brito's monograph, *Proof-of-Location as Next-Generation Digital
Trust Infrastructure for Evidence-Grade Spatio-Temporal Claims*.

The directory layout preserves the scripts' paths in the thesis workspace.
Only the Chapter 6 supporting material is included; the thesis manuscript and
internal review correspondence are not distributed here.

## What is included

- `internal-review/response/check-capture-simulation.py`: seeded seven-scenario
  driver and RF regression checks.
- `internal-review/response/capture-rf-normalization.patch`: common-offset RF
  correction, applied to an isolated copy of the exact historical source.
- `internal-review/response/capture-simulation-checks.json`: all 7000 corrected
  per-run admission counts, parameters, seeds, dependencies, and source hashes.
- `internal-review/response/capture-simulation-upstream-checks.json`: retained
  unmodified six-scenario evaluation for comparison.
- `internal-review/experiments/capture-sensitivity/`: frozen 278-condition
  design, snapshot driver, raw results, analytical/source-policy checks,
  independent-repeat records, full report, and plotting tools.
- `assets/figures/` and `assets/tables/`: the current analytical proximity map,
  the two sensitivity figures, their data/vector sources, and thesis tables.
  The proximity map has a separate small edge-detail panel and no attacker
  arrow; the availability panels are side by side.
- `artifact-manifest.json`: inventory with SHA-256 digests.
- `verify-artifact.py`: checks the inventory, exported plot/table sources, map,
  and optional reproduced outputs.
- `reproduce.py`: isolated, pinned-source experiment and figure reproduction.

## Verify the package

From the repository root, with Python 3.12.3, Git, and `patch` installed:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r thesis-revision/requirements.txt
python thesis-revision/verify-artifact.py
```

The archived experimental environment used Python 3.12.3, NumPy 2.5.2, and
SimPy 4.1.1, with `PYTHONHASHSEED=0`. The runner sets the hash seed. Exact
reproduction also compares versions, source digests, seeds, and every recorded
baseline field. A different environment may therefore fail exact comparison
even if rates are similar.

## Reproduce the numerical results

```sh
python thesis-revision/reproduce.py --output /tmp/chapter6-reproduction
```

The output directory must be new or empty. The runner:

1. Verifies the packaged files.
2. Creates a temporary detached Git worktree at
   `2a0c66a63e920ed3dbb1cfa3ebf476392da2f98b`.
3. Applies the retained patch in a temporary copy and runs the corrected
   baseline: 1000 runs per scenario, 30 claims per run, seeds 260026–260032.
4. Runs the full snapshot sensitivity grid: 278 conditions, 100,000 trials per
   context, PCG64 seed 2026102601. Random inputs are reused across conditions
   and quorum rules; those comparisons are paired.
5. Compares the baseline JSON fields and the five raw sensitivity files
   (`manifest.json`, `results.csv`, `checks.json`, `paired.json`, and
   `batch-counts.json`) against the archived outputs.
6. Writes `reproduction-checks.json` and removes the temporary worktree.

Use `--experiments baseline` or `--experiments sensitivity` to rerun only one
part. A full clone is needed; shallow clones must fetch the historical
revision. The runner deliberately uses the historical source plus the patch,
rather than applying the patch a second time to the corrected root simulator.

The sensitivity checks include 2780 conditional analytical comparisons,
5760 sampled source-policy/quorum decisions, and 1668 nested-quorum checks.
All raw outputs were independently repeated byte for byte before packaging.

## Rebuild the figures and report

Install `requirements-figures.txt` in the same environment and provide a TeX
Live installation with `latexmk`, pdfLaTeX, `standalone`, `pgfplots`,
`newtxtext`, and `newtxmath` (the original builds used TeX Live 2023).
The proximity-map rendering uses the Liberation Serif system font and STIX
math fonts; install Liberation fonts to retain its typography.

```sh
python -m pip install -r thesis-revision/requirements-figures.txt
python thesis-revision/reproduce.py \
  --experiments none --figures --output /tmp/chapter6-figures
```

To regenerate experiments and figures in one invocation, omit
`--experiments none`. Rendering runs in a temporary package copy. The output
contains the rebuilt map, correlation plot, compact availability plot, and
five-page report. The runner requires exact agreement of the proximity-grid
arrays and exported sensitivity table/plot sources with the archive. PDF byte
identity is not required because the tools embed build timestamps.

`draw-proximity-map.py` checks 107 points against the original analytical
implementation and direct quorum enumeration, plus symmetry and probability
bounds. The main grid is 1201 × 1201 at 0.025 m spacing; a separate 401 × 301
edge grid resolves the 10%, 50%, and 90% contours. The original ranging model
is unchanged, and this map excludes RF and visual gates.

## Interpretation and limitations

- The baseline's visual query is deterministic type/colour matching against a
  shared synthetic scene. Its 100% object-present admission is a policy test,
  not an estimate of camera recognition accuracy.
- Recognition false-positive/missed-detection probabilities in the sensitivity
  study are hypothetical. The shared-error mixture is one specified joint
  distribution; equal pairwise correlations do not determine all quorum rates.
- Four-witness geometric scenarios use placement radius 12 m, quorum 3, and a
  20 m limit. Six witnesses use a 12 m hexagon and quorum 4. Visual scenarios
  use a 20 m square placement radius and a 40 m limit. Prover height is 1.5 m
  and witness height is 3 m.
- Ranging is geometry plus bias and Gaussian noise; the model does not validate
  physical distance bounding or relay resistance. RF uses synthetic expected
  fingerprints, with a shared prover report and uncalibrated threshold.
- Sensor independence, trusted fresh acquisition, feature-to-asset binding,
  scene truth, ledger timing, and full cryptographic evidence verification
  remain separate deployment-validation tasks.
- The historical visual aggregate 0.973 was not reproduced. The corrected
  seeded run admits 30,000/30,000 visual-positive claims; the retained
  unmodified run admits 29,999. The boundary admits 10,844/30,000. Historical
  random states were not recovered.

## Historical records

`design.json` and its copy in the raw manifest retain the pre-integration
status text. They are frozen experimental inputs, so their bytes are not
rewritten after manuscript integration. `integration.json` records their later
inclusion in Section 6.4.4; its manuscript PDF digests describe the local
snapshot at packaging, before adding the final repository citation.

`thesis-guard.json` and `results/verification.json` are historical checks that
the initial experiment did not edit protected manuscript files. The manuscript
files themselves are not part of this package. After authorised integration,
`results/reproduction-verification.json` verifies raw outputs independently of
that old guard. Use `verify-artifact.py` and `reproduce.py` for the current
package; do not interpret the historical guard as a claim that today's
manuscript is byte-identical to the earlier draft.

The source copyright and licence position is inherited from the repository;
this release does not add or infer a licence for the original implementation.
