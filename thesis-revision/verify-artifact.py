#!/usr/bin/env python3
"""Check the packaged files and optional independently reproduced run outputs."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
STUDY = HERE/'internal-review/experiments/capture-sensitivity'
RESPONSE = HERE/'internal-review/response'
RAW = ['manifest.json', 'results.csv', 'checks.json', 'paired.json', 'batch-counts.json']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(baseline=None, sensitivity=None):
    manifest = json.loads((HERE/'artifact-manifest.json').read_text())
    for name, digest in manifest['files_sha256'].items():
        path = Path(name)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError(f'Unsafe manifest path: {name}')
        if sha(HERE/path) != digest:
            raise ValueError(f'Packaged file differs: {name}')
    export = json.loads((STUDY/'thesis-export.json').read_text())
    for name, digest in export['exported'].items():
        if sha(HERE/name) != digest:
            raise ValueError(f'Table/plot source differs: {name}')
    checks = json.loads((STUDY/'results/proximity-map-checks.json').read_text())
    assert sha(HERE/'assets/figures/capture-proximity-map.pdf') == checks['figure_sha256']
    assert sha(STUDY/'draw-proximity-map.py') == checks['script_sha256']
    if baseline is not None:
        recorded = json.loads((RESPONSE/'capture-simulation-checks.json').read_text())
        actual = json.loads(baseline.read_text())
        if actual != recorded:
            raise ValueError('Baseline run differs from the archived run (including versions, seeds and source hashes).')
    if sensitivity is not None:
        for name in RAW:
            if (sensitivity/name).read_bytes() != (STUDY/'results'/name).read_bytes():
                raise ValueError(f'Sensitivity rerun differs: {name}')
    return {'packaged_files_verified': len(manifest['files_sha256']),
            'baseline_exact_match': True if baseline is not None else None,
            'sensitivity_exact_match': True if sensitivity is not None else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--sensitivity', type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.baseline, args.sensitivity), indent=2))


if __name__ == '__main__':
    main()
