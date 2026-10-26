# Proof-of-Location witnessing-zone simulation

Python/SimPy admission-model implementation supporting Chapter 6 of Eduardo
Ribas Brito's doctoral monograph. The thesis revision adds a corrected,
seeded baseline and a controlled sensitivity study.

**Start with [the Chapter 6 artefact](thesis-revision/README.md).** It contains
recorded runs, exact parameters and versions, regression checks, the full
sensitivity grid, plotting sources, and one-command reproduction.

## Corrected thesis evaluation

The RF comparison now computes one common offset from both original RSSI
vectors before shifting either vector. The previous implementation modified
the first vector before computing the second offset, making similarity depend
on argument order. The correction is applied in `pol_simulation.py` and retained
as a patch in the artefact so the thesis runs can be reproduced from the exact
historical source revision.

| Baseline scenario | Admitted / 30,000 claims |
| --- | ---: |
| Interior, 4 witnesses / quorum 3 | 30,000 |
| Interior, 6 witnesses / quorum 4 | 30,000 |
| Distance fraud | 0 |
| Boundary position | 10,844 |
| Visual object present | 30,000 |
| Visual object absent | 0 |
| Forged interior coordinate and RF report | 0 |

Each scenario contains 1000 runs of 30 claims with recorded revision-run seeds.
The boundary mean is 0.36147; its per-run population SD is 0.08984. Neither the
corrected nor the retained unmodified check reproduces the historical visual
aggregate 0.973. Original random states for that aggregate are unavailable.

The additional study evaluates 278 parameter conditions, with 100,000 synthetic
snapshot trials per context and shared random inputs across conditions/rules.
At independent false-positive and missed-detection probabilities of 0.1,
three-of-four admits 94.67% of valid-context trials and 0.380% of invalid-context
trials. Fully shared recognition errors raise invalid-context admission to
10.02%. These error probabilities are hypothetical sensitivity inputs.

## Reproduction

Use Python **3.12.3**, Git, and the `patch` utility. From a full clone:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r thesis-revision/requirements.txt
python thesis-revision/verify-artifact.py
python thesis-revision/reproduce.py --output /tmp/chapter6-reproduction
```

The runner creates a temporary detached worktree at the exact historical
revision `2a0c66a63e920ed3dbb1cfa3ebf476392da2f98b`, applies the retained RF
correction to a temporary copy, and compares all recorded baseline fields and
all five raw sensitivity outputs. It preserves the current checkout and
archived data. A shallow clone must first fetch the pinned revision's history.
Optional figure/report regeneration is documented in the artefact README.

## Scope

This is an admission-model evaluation. Despite the repository name, the
experiments use Python and SimPy, without an NS-3 radio-stack benchmark.
Ranging is true geometry plus specified bias and noise. RF is a model-based
consistency check at the claimed position. The baseline visual query matches
ideal shared object labels; it is not an image-recognition experiment. The
sensitivity extension models recognition errors, correlation, missing
observations, dishonest positive reports, and field of view.

These simulations do not validate physical relay resistance, camera accuracy,
a trusted acquisition path, feature-to-asset binding, consensus latency, or
the complete cryptographic evidence object. See the artefact for exact
assumptions, parameters, and limitations.

## Earlier examples

`PYTHON_EVALUATION_RESULTS.md`, `pol-python-results.*`, `pol-visual-results.*`,
and the original visualisation scripts/outputs are retained historical
examples. Their configurations and aggregates differ from the corrected,
seeded thesis evaluation. They are not the sources for the revised thesis
tables or figures. The current figures and data are under `thesis-revision/`.

The original CLI remains available for exploratory examples:

```sh
python pol_simulation.py --all-scenarios
```

That command does not reproduce the thesis's seeded seven-scenario evaluation;
use `thesis-revision/reproduce.py` for it.
