#!/usr/bin/env python3
"""Controlled snapshot sensitivity study; does not edit the thesis.

Requires NumPy and SimPy, the retained correction loader, and an authorised source
checkout. Vectorised observation trials are checked against the supplied policy
and quorum implementation, and against exact conditional mixture expectations.
"""
import argparse
import csv
import hashlib
import importlib.util
import itertools
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

import numpy as np

HERE = Path(__file__).resolve().parent
LOADER = HERE.parents[1] / 'response' / 'check-capture-simulation.py'
RULES = [('single_preselected', 1), ('1_of_4', 1), ('2_of_4', 2), ('3_of_4', 3), ('4_of_4', 4)]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wilson(count, total):
    z = 1.959963984540054
    p = count / total
    den = 1 + z*z / total
    mid = (p + z*z / (2*total)) / den
    half = z * math.sqrt(p*(1-p)/total + z*z/(4*total*total)) / den
    return max(0., mid-half), min(1., mid+half)


def tail(n, k, p):
    if k <= 0:
        return 1.
    return sum(math.comb(n, i) * p**i * (1-p)**(n-i) for i in range(k, n+1))


def conditional_probability(n, k, positive, missing, error_common, missing_common):
    if k <= 0:
        return 1.
    if k > n:
        return 0.
    a, b = error_common, missing_common
    return (
        (1-a)*(1-b)*tail(n, k, positive*(1-missing))
        + a*(1-b)*positive*tail(n, k, 1-missing)
        + (1-a)*b*(1-missing)*tail(n, k, positive)
        + a*b*(1-missing)*positive
    )


def vectors(n, seed):
    rng = np.random.default_rng(seed)
    bank = {
        'range_z': rng.standard_normal((n, 4)),
        'rf_prover_z': rng.standard_normal((n, 4)),
        'rf_expected_z': rng.standard_normal((n, 4, 4)),
        'error_local_u': rng.random((n, 4)),
        'error_shared_u': rng.random((n, 1)),
        'error_mode_u': rng.random((n, 1)),
        'missing_local_u': rng.random((n, 4)),
        'missing_shared_u': rng.random((n, 1)),
        'missing_mode_u': rng.random((n, 1)),
        'single_index': rng.integers(0, 4, n, dtype=np.int8),
    }
    return bank


def cases(design):
    profile = design['profile']
    common = dict(position=profile['interior_position'], range_sd=profile['range_noise_sd_m'],
                  fp=.1, fn=.1, error_common=0., missing=0., missing_common=0.,
                  dishonest=0, fov=360., visual_range=profile['visual_range_m'], boundary_offset=None)
    result = []

    def add(block, **kw):
        result.append(dict(common, block=block, case_id=f'{block}-{len(result):03}', **kw))

    # Preserve the declared full grid, including limiting cases and duplicates
    # between blocks; no outcome-dependent filtering or parameter tuning.
    spec = design['error_sweep']
    for fp, fn, c in itertools.product(spec['false_positive'], spec['false_negative'], spec['error_common_fraction']):
        add('errors', fp=fp, fn=fn, error_common=c)
    spec = design['availability_sweep']
    for miss, cm, ce in itertools.product(spec['missing_probability'], spec['missing_common_fraction'], spec['error_common_fraction']):
        add('availability', missing=miss, missing_common=cm, error_common=ce)
    spec = design['dishonest_sweep']
    for f, ce in itertools.product(spec['dishonest_witnesses'], spec['error_common_fraction']):
        add('dishonest', dishonest=f, error_common=ce)
    spec = design['visibility_sweep']
    for xy, fov, vr in itertools.product(spec['positions_xy'], spec['horizontal_fov_degrees'], spec['visual_range_m']):
        add('visibility', position=xy+[profile['prover_height_m']], fov=fov, visual_range=vr)
    spec = design['boundary_sweep']
    a = profile['placement_radius_m']/math.sqrt(2)
    nominal_distance = (profile['range_limit_m']-profile['range_offset_m'])/(1+profile['range_bias_fraction'])
    boundary = math.sqrt(nominal_distance**2 - (spec['path_y_m']-a)**2
                         - (profile['witness_height_m']-profile['prover_height_m'])**2) - a
    for off, sigma, error in itertools.product(spec['offsets_from_biased_third_witness_boundary_m'],
                                              spec['range_noise_sd_m'], spec['recognition_error_probabilities']):
        add('boundary', position=[boundary+off, spec['path_y_m'], profile['prover_height_m']],
            boundary_offset=off, range_sd=sigma, fp=error, fn=error)
    return result, boundary


def sensor_state(case, bank, profile, witnesses):
    pos = np.array(case['position'])
    distance = np.linalg.norm(witnesses-pos, axis=1)
    measured = (1+profile['range_bias_fraction'])*distance + profile['range_offset_m'] + case['range_sd']*bank['range_z']
    # One shared prover report, and one fresh model expectation per witness.
    mean = -40 - 25*np.log10(np.maximum(distance, .1))
    prover = mean + profile['rf_noise_sd_db']*bank['rf_prover_z']
    expected = mean + profile['rf_noise_sd_db']*bank['rf_expected_z']
    offset = np.minimum(expected.min(axis=2), prover.min(axis=1)[:, None])
    first = expected-offset[:, :, None]+1
    second = prover[:, None, :]-offset[:, :, None]+1
    similarity = np.sum(first*second, axis=2)/(np.linalg.norm(first, axis=2)*np.linalg.norm(second, axis=2))
    patch = np.array([pos[0], pos[1], 0.])
    patch_delta = patch-witnesses
    heading = np.arctan2(-witnesses[:, 1], -witnesses[:, 0])
    bearing = np.arctan2(patch_delta[:, 1], patch_delta[:, 0])
    angle = np.abs((bearing-heading+np.pi) % (2*np.pi)-np.pi)
    visible = (np.linalg.norm(patch_delta, axis=1) <= case['visual_range']) & (angle <= math.radians(case['fov']/2)+1e-12)
    return measured, similarity, visible


def observations(case, truth, bank, visible):
    error_u = np.where(bank['error_mode_u'] < case['error_common'], bank['error_shared_u'], bank['error_local_u'])
    error = error_u < (case['fn'] if truth else case['fp'])
    missing_u = np.where(bank['missing_mode_u'] < case['missing_common'], bank['missing_shared_u'], bank['missing_local_u'])
    unavailable = (missing_u < case['missing']) | ~visible[None, :]
    obs = np.logical_xor(truth, error).astype(np.int8)
    obs[unavailable] = -1
    obs[:, :case['dishonest']] = 1
    return obs


def classify(base, obs, rule, k, single):
    yes = base & (obs == 1)
    unknown = base & (obs == -1)
    if rule == 'single_preselected':
        idx = np.arange(len(base))
        positives, unknowns = yes[idx, single], unknown[idx, single]
        available = (obs[idx, single] != -1).astype(np.int8)
    else:
        positives, unknowns = yes.sum(axis=1), unknown.sum(axis=1)
        available = (obs != -1).sum(axis=1)
    admit = positives >= k
    # A diagnostic distinction within fail-closed non-admission.
    inconclusive = ~admit & ((positives.astype(np.int8)+unknowns.astype(np.int8)) >= k)
    reject = ~admit & ~inconclusive
    return admit, reject, inconclusive, available < k


def exact_expected(case, truth, base, visible, rule, k, single):
    dishonest = np.zeros(4, dtype=bool)
    dishonest[:case['dishonest']] = True
    fixed_yes = base & dishonest
    honest_visible = base & ~dishonest & visible
    if rule == 'single_preselected':
        idx = np.arange(len(base))
        c = fixed_yes[idx, single].astype(np.int8)
        n = honest_visible[idx, single].astype(np.int8)
    else:
        c = fixed_yes.sum(axis=1)
        n = honest_visible.sum(axis=1)
    positive = 1-case['fn'] if truth else case['fp']
    frequencies = np.bincount(n*5+c, minlength=25).reshape(5, 5)
    expectation = 0.
    for j in range(5):
        for f in range(5):
            count = int(frequencies[j, f])
            expectation += count*conditional_probability(j, k-f, positive, case['missing'], case['error_common'], case['missing_common'])
    return expectation/len(base)


def replay(m, case, truth, measured, similarity, obs, single, bank, take=32):
    """Check vectorised votes and quorum against the supplied implementation."""
    n = min(take, len(obs))
    policy = m.VisualVerificationPolicy(max_distance=40., rf_threshold=.5,
                                         required_queries=['is there a red car?'])
    base = (measured <= 40) & (similarity >= .5)
    for rule, k in RULES:
        config = m.ZoneConfig(n_witnesses=4, quorum_k=k, radius=20.)
        simulation = m.PolSimulation(config, policy)
        simulation.create_witnesses()
        node = simulation.witnesses[0]
        fast = classify(base, obs, rule, k, single)[0]
        for trial in range(n):
            claim_id = f'check-{trial}'
            claim = m.LocationClaim(claim_id, 'p', m.Vector3(*case['position']), 0., {})
            votes = []
            for w in range(4):
                visual = {} if obs[trial, w] == -1 else {'is there a red car?': bool(obs[trial, w])}
                evidence = m.Evidence(claim_id, w, float(measured[trial, w]), True,
                                      float(similarity[trial, w]), {}, visual)
                admitted, reason = policy.evaluate(claim, evidence)
                assert admitted == bool(base[trial, w] and obs[trial, w] == 1)
                votes.append(m.Vote(w, claim_id, admitted, reason, evidence))
            node.pending_claims[claim_id] = claim
            node.votes[claim_id] = votes[0]
            node.peer_votes[claim_id] = votes[1:]
            attestation = node.check_quorum(claim_id)
            actual = votes[int(single[trial])].admit if rule == 'single_preselected' else attestation.admitted
            assert actual == bool(fast[trial])
    # Independently check vectorised RF scores with the corrected source.
    pos = np.array(case['position'])
    distances = np.linalg.norm(np.array([[p.x, p.y, p.z] for p in simulation._compute_witness_positions()])-pos, axis=1)
    mean = -40-25*np.log10(np.maximum(distances, .1))
    for i in range(min(8, n)):
        p = dict(enumerate(mean+2*bank['rf_prover_z'][i]))
        for w in range(4):
            q = dict(enumerate(mean+2*bank['rf_expected_z'][i, w]))
            np.testing.assert_allclose(m.RfFingerprintSensor.compute_similarity(q, p), similarity[i, w], rtol=1e-12, atol=1e-12)
    return n*len(RULES)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--trials', type=int, help='Override for a smoke test; final run uses the design value')
    args = parser.parse_args()
    design_path = HERE/'design.json'
    design = json.loads(design_path.read_text())
    n = args.trials or design['trials_per_condition']
    batches = design['batches']
    if n < batches or n % batches:
        parser.error('Trial count must be a positive multiple of the batch count')
    if os.environ.get('PYTHONHASHSEED') != '0':
        parser.error('Use PYTHONHASHSEED=0 for source replay')
    spec = importlib.util.spec_from_file_location('capture_loader', LOADER)
    loader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loader)
    bank = vectors(n, design['seed'])
    scenarios, boundary = cases(design)
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = {
        'design': design, 'design_sha256': sha(design_path), 'driver_sha256': sha(Path(__file__)),
        'loader_sha256': sha(LOADER), 'python': platform.python_version(), 'numpy': np.__version__,
        'trials_per_condition': n, 'scenario_count': len(scenarios),
        'source_revision': subprocess.check_output(['git', '-C', str(args.source), 'rev-parse', 'HEAD'], text=True).strip(),
        'random_generator': 'NumPy default_rng / PCG64',
        'input_sha256': {key: hashlib.sha256(value.tobytes()).hexdigest() for key, value in bank.items()},
        'third_witness_boundary_x_m': boundary, 'scenarios': scenarios,
    }
    rows, paired, counts, checks = [], [], [], {'analytical_checks': 0, 'source_replay_decisions': 0, 'monotone_checks': 0}
    base_cache, baseline_seen = {}, set()
    a = design['profile']['placement_radius_m']/math.sqrt(2)
    witnesses = np.array([[-a, -a, 3], [a, -a, 3], [a, a, 3], [-a, a, 3]])
    with tempfile.TemporaryDirectory(prefix='capture-sensitivity-') as work:
        m, correction = loader.load_simulator(args.source.resolve(), Path(work), False)
        manifest['simpy'] = loader.simpy.__version__
        manifest['correction'] = correction
        checks['rf_regression'] = loader.check_similarity(m)
        assert abs(tail(4, 3, .1)-.0037) < 1e-14
        assert abs(tail(4, 3, .9)-.9477) < 1e-14
        assert abs(conditional_probability(4, 3, .1, 0, 1, 0)-.1) < 1e-14
        for case_index, case in enumerate(scenarios):
            key = (tuple(case['position']), case['range_sd'])
            if key not in base_cache:
                measured, similarity, _ = sensor_state(case, bank, design['profile'], witnesses)
                base_cache[key] = measured, similarity
            measured, similarity = base_cache[key]
            # Visibility changes independently of the cached range/RF samples.
            patch = np.array([case['position'][0], case['position'][1], 0.])
            delta = patch-witnesses
            heading = np.arctan2(-witnesses[:, 1], -witnesses[:, 0])
            angle = np.abs((np.arctan2(delta[:, 1], delta[:, 0])-heading+np.pi) % (2*np.pi)-np.pi)
            visible = (np.linalg.norm(delta, axis=1) <= case['visual_range']) & (angle <= math.radians(case['fov']/2)+1e-12)
            base = (measured <= 40) & (similarity >= .5)
            for truth in [True, False]:
                obs = observations(case, truth, bank, visible)
                masks = {}
                stages = [('range_rf_visual', obs, base)]
                baseline_key = (key, truth)
                if baseline_key not in baseline_seen:
                    stages += [('range_only', np.ones_like(obs), measured <= 40), ('range_rf', np.ones_like(obs), base)]
                    baseline_seen.add(baseline_key)
                for stage, reports, eligible in stages:
                    for rule, k in RULES:
                        outcomes = classify(eligible, reports, rule, k, bank['single_index'])
                        admit, reject, unknown, insufficient = outcomes
                        assert np.all(admit.astype(np.int8)+reject.astype(np.int8)+unknown.astype(np.int8) == 1)
                        total = int(admit.sum())
                        low, high = wilson(total, n)
                        row = dict(case_id=case['case_id'], block=case['block'], truth_present=truth,
                                   stage=stage, rule=rule, k=k, trials=n,
                                   admitted=total, admit_rate=total/n, ci95_low=low, ci95_high=high,
                                   rejected=int(reject.sum()), inconclusive=int(unknown.sum()),
                                   insufficient_observations=int(insufficient.sum()),
                                   visible_witnesses=int(visible.sum()),
                                   **{key: value for key, value in case.items() if key not in ('case_id', 'block', 'position')},
                                   x=case['position'][0], y=case['position'][1])
                        if stage == 'range_rf_visual':
                            expected = exact_expected(case, truth, base, visible, rule, k, bank['single_index'])
                            row['analytical_expected'] = expected
                            tolerance = max(7*math.sqrt(expected*(1-expected)/n), 7/n)
                            assert abs(total/n-expected) <= tolerance, (row, tolerance)
                            checks['analytical_checks'] += 1
                            masks[rule] = admit
                        else:
                            row['analytical_expected'] = None
                        rows.append(row)
                        counts.append(dict(case_id=case['case_id'], truth_present=truth, stage=stage, rule=rule,
                                           admitted=admit.reshape(batches, -1).sum(axis=1).tolist(),
                                           inconclusive=unknown.reshape(batches, -1).sum(axis=1).tolist()))
                for lower, higher in [('1_of_4', '2_of_4'), ('2_of_4', '3_of_4'), ('3_of_4', '4_of_4')]:
                    assert np.all(~masks[higher] | masks[lower])
                    checks['monotone_checks'] += 1
                for rule, _ in RULES:
                    one = masks['single_preselected']
                    other = masks[rule]
                    paired.append(dict(case_id=case['case_id'], truth_present=truth, rule=rule,
                                       admission_difference_vs_single=float(other.mean()-one.mean()),
                                       single_only=int((one & ~other).sum()), rule_only=int((other & ~one).sum())))
                # Replay representative configurations from every block, including
                # missing observations, corruption, FOV and boundary cases.
                if case_index % 17 == 0 or case_index == len(scenarios)-1:
                    checks['source_replay_decisions'] += replay(m, case, truth, measured, similarity, obs, bank['single_index'], bank)
            if case_index % 25 == 0:
                print(f'Checked {case_index+1}/{len(scenarios)} conditions', flush=True)
    for filename, data in [('manifest.json', manifest), ('checks.json', checks), ('batch-counts.json', counts), ('paired.json', paired)]:
        (args.output/filename).write_text(json.dumps(data, indent=2, allow_nan=False)+'\n')
    with (args.output/'results.csv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(dict(checks, result_rows=len(rows)), indent=2), flush=True)


if __name__ == '__main__':
    main()
