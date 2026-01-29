# PoL Witnessing Zone - Python Simulation Results

## Overview

This Python implementation uses SimPy for discrete-event simulation, providing a simpler alternative to the full NS-3 C++ module while maintaining the same protocol semantics.

## Implementation (~600 lines vs ~3000 lines in C++)

### Components
- **UWB Channel Model**: IEEE 802.15.4a path loss with ranging error
- **Distance Bounding Protocol**: Challenge-response with configurable rounds
- **Environmental Sensing**: RF fingerprint with beacon-based RSSI simulation
- **Admission Policies**: Supply Chain policy with distance and RF thresholds
- **Attack Models**: Distance fraud, relay, scene spoofing

## Evaluation Results

### Scenario 1: Baseline (4 Witnesses)
| Metric | Value |
|--------|-------|
| Witnesses | 4 (square geometry) |
| Quorum | 3 |
| Zone Radius | 20 m |
| Prover Position | (5, 5, 1.5) - inside zone |
| **Success Rate** | **100%** |
| True Positives | 30 |
| False Positives | 0 |
| Precision | 1.0 |
| Recall | 1.0 |

### Scenario 2: Baseline (6 Witnesses)
| Metric | Value |
|--------|-------|
| Witnesses | 6 (hexagonal geometry) |
| Quorum | 4 |
| Zone Radius | 20 m |
| Prover Position | (5, 5, 1.5) - inside zone |
| **Success Rate** | **100%** |
| True Positives | 30 |
| Precision | 1.0 |
| Recall | 1.0 |

### Scenario 3: Distance Fraud Attack
| Metric | Value |
|--------|-------|
| Prover True Position | (30, 30, 1.5) - outside zone |
| Claimed Position | (15, 15, 1.5) - fraudulent |
| Attack Type | Distance Fraud |
| **Success Rate** | **0%** (correctly rejected) |
| True Negatives | 30 |
| False Positives | 0 |

### Scenario 4: Edge Position
| Metric | Value |
|--------|-------|
| Prover Position | (15, 15, 1.5) - zone edge |
| **Success Rate** | **0%** |
| Analysis | Distance to farthest witness (~41m) exceeds max (40m) |

## Key Findings

1. **Protocol Correctness**: Honest provers inside the zone achieve 100% attestation success
2. **Attack Detection**: Distance fraud attacks are correctly rejected (0% success for attacker)
3. **Edge Cases**: Provers near zone boundaries may be rejected due to geometric constraints
4. **Performance**: Python simulation runs in milliseconds vs seconds for NS-3

## Running the Simulation

```bash
cd /Users/fernando/Downloads/ns3-sim-pol
source venv/bin/activate

# Run all scenarios
python pol_simulation.py --all-scenarios

# Run custom scenario
python pol_simulation.py --witnesses 4 --quorum 3 --radius 20 --time 60
```

## Comparison: Python vs NS-3 C++

| Aspect | Python (SimPy) | NS-3 C++ |
|--------|----------------|----------|
| Lines of Code | ~600 | ~3000 |
| Setup Time | Seconds | Minutes (compilation) |
| Network Simulation | Abstract | Full WiFi/CSMA stack |
| Execution Speed | Faster | Slower |
| Realism | Medium | High |
| Extensibility | Easy | Complex |

## Files

- `pol_simulation.py` - Main Python simulation
- `pol-python-results.json` - JSON results
- `pol-python-results.csv` - CSV results
