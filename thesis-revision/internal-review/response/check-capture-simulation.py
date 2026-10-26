#!/usr/bin/env python3
"""Reproduce capture admission with an explicit local RF correction.

The private upstream checkout is never edited. --upstream reproduces the six
uncorrected checks; the default patches a temporary copy and adds an outside
prover forging an inside claim and RF fingerprint.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

import numpy as np
import simpy


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_simulator(root, work, upstream):
    source = root / 'pol_simulation.py'
    patch = Path(__file__).with_name('capture-rf-normalization.patch')
    loaded = source
    correction = {'applied': False}
    if not upstream:
        expected = '329646654f7d1331a77a20c0067a70319f7c7e22b8a391119669c21196e330cf'
        if digest(source) != expected:
            raise ValueError('Simulator digest differs from the inspected source; inspect before patching.')
        loaded = work / 'pol_simulation_corrected.py'
        subprocess.run(
            ['patch', '--batch', '--fuzz=0', '--output', str(loaded), str(source)],
            input=patch.read_text(), text=True, capture_output=True, check=True,
        )
        correction = {
            'applied': True, 'version': 'rf-shared-offset-v1',
            'patch': patch.name, 'patch_sha256': digest(patch),
            'description': 'Compute one offset from both original RSSI vectors before shifting either.',
        }
    correction['loaded_simulator_sha256'] = digest(loaded)
    spec = importlib.util.spec_from_file_location('capture_simulator', loaded)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module, correction


def check_similarity(module):
    """Verify the symmetric shared-offset cosine and its edge cases."""
    similarity = module.RfFingerprintSensor.compute_similarity
    assert similarity({}, {}) == 0
    assert similarity({'a': -60.}, {'b': -60.}) == 0
    np.testing.assert_allclose(similarity({'a': -60.}, {'a': -60.}), 1.)
    pairs = [(np.array([-90., -60., -50.]), np.array([-85., -65., -55.]))]
    rng = np.random.default_rng(20261026)
    pairs.extend((rng.normal(-70, 10, 4), rng.normal(-70, 10, 4)) for _ in range(100))
    for first, second in pairs:
        fp1, fp2 = dict(enumerate(first)), dict(enumerate(second))
        offset = min(first.min(), second.min())
        v, w = first - offset + 1, second - offset + 1
        expected = np.dot(v, w) / (np.linalg.norm(v) * np.linalg.norm(w))
        score = similarity(fp1, fp2)
        np.testing.assert_allclose(score, expected, rtol=1e-12, atol=1e-12)
        np.testing.assert_allclose(score, similarity(fp2, fp1), rtol=1e-12, atol=1e-12)
        assert 0 <= score <= 1 + 1e-12
    return {'shared_offset_and_symmetry_pairs': len(pairs), 'edge_cases': 3, 'passed': True}


def run_scenario(m, name, n, k, radius, pos, attack, visual):
    if name not in ('FalseInteriorClaim', 'VisualPresent', 'VisualAbsent'):
        return m._run_single_simulation(name, n, k, radius, 60., m.Vector3(*pos), attack)
    config = m.ZoneConfig(n_witnesses=n, quorum_k=k, radius=radius)
    if visual is None:
        policy = m.SupplyChainPolicy(max_distance=20., rf_threshold=.5)
    else:
        policy = m.VisualVerificationPolicy(
            max_distance=40., rf_threshold=.5,
            required_queries=['is there a red car?'], require_all_true=True,
        )
    sim = m.PolSimulation(config, policy)
    if visual is not None:
        if visual:
            sim.add_scene_object('car1', m.ObjectType.CAR, 'red', m.Vector3(5, 5, 0), size=4)
        sim.add_scene_object('truck1', m.ObjectType.TRUCK, 'blue', m.Vector3(-5, 10, 0), size=6)
    sim.create_witnesses()
    if visual is not None:
        sim.set_visual_queries(['is there a red car?'])
    if name == 'FalseInteriorClaim':
        class ForgedInteriorProver(m.ProverNode):
            def create_claim(self):
                claim = super().create_claim()
                claim.claimed_position = m.Vector3(5, 5, 1.5)
                # Give the attacker a plausible model-generated fingerprint at
                # the forged coordinate. Ranging still uses its actual position.
                claim.features['rf_fingerprint'] = self.sensing.rf_sensor.sample(claim.claimed_position)
                return claim

        prover = ForgedInteriorProver(sim.env, 'prover-1', m.Vector3(*pos), sim.sensing, attack)
        sim.provers.append(prover)
        positions = sim._compute_witness_positions()
        true_count = sum(p.distance_to(prover.position) <= 20 for p in positions)
        claim_count = sum(p.distance_to(m.Vector3(5, 5, 1.5)) <= 20 for p in positions)
        assert true_count == 2 and claim_count == 4 and true_count < k <= claim_count
    else:
        prover = sim.create_prover(m.Vector3(*pos))
    sim.run_periodic_claims(prover, 2., 60.)
    sim.run(60.)
    return sim.get_results()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='Authorised checkout of ferjcast/ns3-sim-pol')
    parser.add_argument('--iterations', type=int, default=1000)
    parser.add_argument('--seed', type=int, default=260026)
    parser.add_argument('--upstream', action='store_true', help='Reproduce the six original unpatched checks')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.iterations < 1:
        parser.error('--iterations must be positive')
    if os.environ.get('PYTHONHASHSEED') != '0':
        parser.error('Start Python with PYTHONHASHSEED=0 for the recorded set iteration order')
    root = args.source.resolve()
    with tempfile.TemporaryDirectory(prefix='capture-rf-corrected-') as work:
        m, correction = load_simulator(root, Path(work), args.upstream)
        record = {
            'source_revision': subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip(),
            'python_hash_seed': os.environ['PYTHONHASHSEED'], 'python': platform.python_version(),
            'numpy': np.__version__, 'simpy': simpy.__version__, 'iterations': args.iterations,
            'seed_note': 'New revision seeds, not recovered historical seeds. Seed once before each scenario.',
            'sources': {p.name: digest(p) for p in root.glob('*.py')},
            'driver_sha256': digest(Path(__file__)), 'correction': correction,
            'geometry': {}, 'scenarios': [],
        }
        if not args.upstream:
            record['similarity_checks'] = check_similarity(m)
        for n, r in [(4, 12.), (6, 12.), (4, 20.)]:
            s = m.PolSimulation(m.ZoneConfig(n_witnesses=n, radius=r), m.SupplyChainPolicy())
            record['geometry'][f'{n}W-r{r}'] = [[float(p.x), float(p.y), float(p.z)] for p in s._compute_witness_positions()]
        scenarios = [
            ('Interior4W', 4, 3, 12., (5, 5, 1.5), m.AttackType.NONE, None),
            ('Interior6W', 6, 4, 12., (5, 5, 1.5), m.AttackType.NONE, None),
            ('DistanceFraud', 4, 3, 12., (30, 30, 1.5), m.AttackType.DISTANCE_FRAUD, None),
            ('Boundary', 4, 3, 12., (9.28, 0, 1.5), m.AttackType.NONE, None),
            ('VisualPresent', 4, 3, 20., (5, 5, 1.5), m.AttackType.NONE, True),
            ('VisualAbsent', 4, 3, 20., (5, 5, 1.5), m.AttackType.NONE, False),
        ]
        if not args.upstream:
            scenarios.append(('FalseInteriorClaim', 4, 3, 12., (18, 0, 1.5), m.AttackType.DISTANCE_FRAUD, None))
        for idx, (name, n, k, radius, pos, attack, visual) in enumerate(scenarios):
            seed = args.seed + idx
            np.random.seed(seed)
            rates, admitted = [], []
            for _ in range(args.iterations):
                result = run_scenario(m, name, n, k, radius, pos, attack, visual)
                p = result['performance']
                assert p['total_claims'] == 30
                assert p['successful_attestations'] + p['failed_attestations'] == 30
                rates.append(p['success_rate'])
                admitted.append(p['successful_attestations'])
            claimed = (5, 5, 1.5) if name == 'FalseInteriorClaim' else ((15, 15, 1.5) if name == 'DistanceFraud' else pos)
            row = {
                'name': name, 'seed': seed, 'n': n, 'k': k, 'placement_radius': radius,
                'prover': pos, 'claimed_position': claimed,
                'rf_report': 'forged sample at claimed position' if name == 'FalseInteriorClaim' else 'sample at actual position',
                'max_distance': 40 if visual is not None else 20,
                'mean': float(np.mean(rates)), 'std_population': float(np.std(rates)),
                'mean_admitted': float(np.mean(admitted)), 'run_admitted_counts': admitted,
            }
            record['scenarios'].append(row)
            print(json.dumps({k: v for k, v in row.items() if k != 'run_admitted_counts'}), flush=True)
            args.output.write_text(json.dumps(record, indent=2) + '\n')


if __name__ == '__main__':
    main()
