#!/usr/bin/env python3
"""Reproduce Chapter 6 in isolation, using the exact historical simulator revision."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
BASE = '2a0c66a63e920ed3dbb1cfa3ebf476392da2f98b'


def run(command, env, cwd=None):
    print('+ '+ ' '.join(map(str, command)), flush=True)
    subprocess.run(list(map(str, command)), env=env, cwd=cwd, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New or empty output directory')
    parser.add_argument('--experiments', choices=['all', 'baseline', 'sensitivity', 'none'], default='all')
    parser.add_argument('--figures', action='store_true', help='Also redraw the map and compile the two sensitivity figures and report; requires Matplotlib and latexmk')
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists() and any(out.iterdir()):
        parser.error('--output must be new or empty; retained results are never overwritten')
    out.mkdir(parents=True, exist_ok=True)
    spec = importlib.util.spec_from_file_location('verify_artifact', HERE/'verify-artifact.py')
    verifier = importlib.util.module_from_spec(spec); spec.loader.exec_module(verifier)
    print(json.dumps(verifier.verify()), flush=True)
    env = dict(os.environ, PYTHONHASHSEED='0')
    baseline = sensitivity = None
    with tempfile.TemporaryDirectory(prefix='capture-reproduction-') as temporary:
        temporary = Path(temporary)
        source = temporary/'source'
        # Detached worktree pins the source revision recorded in both manifests.
        # Root pol_simulation.py now contains the RF fix, so it is deliberately
        # not used as input to the historical-source-plus-retained-patch runner.
        run(['git', '-C', REPO, 'worktree', 'add', '--detach', source, BASE], env)
        try:
            if args.experiments in ('all', 'baseline'):
                baseline = out/'baseline.json'
                run([sys.executable, HERE/'internal-review/response/check-capture-simulation.py',
                     '--source', source, '--output', baseline], env)
            if args.experiments in ('all', 'sensitivity'):
                sensitivity = out/'sensitivity'
                run([sys.executable, HERE/'internal-review/experiments/capture-sensitivity/run-study.py',
                     '--source', source, '--output', sensitivity], env)
            verified = verifier.verify(baseline, sensitivity)
            if args.figures:
                if shutil.which('latexmk') is None:
                    raise RuntimeError('--figures requires latexmk on PATH; run inside a TeX Live environment')
                scratch = temporary/'presentation'
                shutil.copytree(HERE, scratch, ignore=shutil.ignore_patterns('__pycache__'))
                study = scratch/'internal-review/experiments/capture-sensitivity'
                plot_env = dict(env, MPLCONFIGDIR=str(temporary/'matplotlib'))
                run([sys.executable, study/'draw-proximity-map.py', '--source', source], plot_env)
                run([sys.executable, study/'export-thesis.py'], plot_env)
                run([sys.executable, study/'make-report.py'], plot_env)
                import numpy as np
                with np.load(study/'results/capture-proximity-grid.npz') as generated, np.load(HERE/'internal-review/experiments/capture-sensitivity/results/capture-proximity-grid.npz') as recorded:
                    assert set(generated.files) == set(recorded.files)
                    for key in recorded.files:
                        np.testing.assert_array_equal(generated[key], recorded[key])
                export = json.loads((HERE/'internal-review/experiments/capture-sensitivity/thesis-export.json').read_text())
                for name, digest in export['exported'].items():
                    assert verifier.sha(scratch/name) == digest, name
                for document in [scratch/'assets/figures/capture-sensitivity-correlation.tex',
                                 scratch/'assets/figures/capture-sensitivity-availability.tex', study/'report.tex']:
                    run(['latexmk', '-cd', '-pdf', '-interaction=nonstopmode', '-halt-on-error', document], plot_env)
                figures = out/'figures'; figures.mkdir()
                for document in [scratch/'assets/figures/capture-proximity-map.pdf',
                                 scratch/'assets/figures/capture-sensitivity-correlation.pdf',
                                 scratch/'assets/figures/capture-sensitivity-availability.pdf', study/'report.pdf']:
                    shutil.copy2(document, figures/document.name)
                verified['proximity_grid_exact_match'] = True
                verified['table_and_plot_sources_exact_match'] = True
                verified['figures_and_report_compiled'] = True
                # PDF byte identity is not required: the original tools embed
                # build timestamps. Numerical grids and exported data are exact.
            verified['source_revision'] = BASE
            (out/'reproduction-checks.json').write_text(json.dumps(verified, indent=2)+'\n')
            print(json.dumps(verified, indent=2), flush=True)
        finally:
            run(['git', '-C', REPO, 'worktree', 'remove', '--force', source], env)


if __name__ == '__main__':
    main()
