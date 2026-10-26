#!/usr/bin/env python3
"""Verify a second execution and guard the thesis against accidental edits."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FILES = ['manifest.json', 'results.csv', 'checks.json', 'paired.json', 'batch-counts.json']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repeat', type=Path, required=True)
    parser.add_argument('--results-only', action='store_true',
                        help='Check experiment reproduction after authorised manuscript integration; retain the historical guard record')
    args = parser.parse_args()
    digests = {}
    for name in FILES:
        primary, repeat = HERE/'results'/name, args.repeat/name
        assert primary.read_bytes() == repeat.read_bytes(), f'Reproduction mismatch: {name}'
        digests[name] = sha(primary)
    guard = json.loads((HERE/'thesis-guard.json').read_text())
    if not args.results_only:
        for name, digest in guard.items():
            assert sha(ROOT/name) == digest, f'Protected thesis file changed: {name}'
    manifest = json.loads((HERE/'results/manifest.json').read_text())
    assert manifest['driver_sha256'] == sha(HERE/'run-study.py')
    assert manifest['design_sha256'] == sha(HERE/'design.json')
    record = {
        'exact_repeat_match': True, 'matching_files': FILES,
        'verified_output_sha256': digests,
        'protected_thesis_files_checked': 0 if args.results_only else len(guard),
        'thesis_unchanged': None if args.results_only else True,
        'guard_sha256': sha(HERE/'thesis-guard.json'),
    }
    filename = 'reproduction-verification.json' if args.results_only else 'verification.json'
    (HERE/'results'/filename).write_text(json.dumps(record, indent=2)+'\n')
    if args.results_only:
        print(f'{len(FILES)} raw outputs reproduced exactly; historical pre-integration guard preserved.')
    else:
        print(f'{len(FILES)} raw outputs reproduced exactly; {len(guard)} protected thesis files unchanged.')


if __name__ == '__main__':
    main()
