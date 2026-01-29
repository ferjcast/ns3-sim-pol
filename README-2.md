# PoL Witnessing Zone Simulation

A discrete-event simulation of Proof-of-Location (PoL) witnessing zones using Python and SimPy. This project implements a location verification protocol where multiple witness nodes collaboratively attest to a prover's physical presence within a defined zone.

## Overview

The PoL witnessing zone protocol enables trustless location verification through:

- **Distance Bounding**: UWB-based challenge-response protocol to measure physical distance
- **Environmental Sensing**: RF fingerprinting, temperature, and visual scene verification
- **Quorum Consensus**: Multiple witnesses must agree before issuing attestations
- **Admission Policies**: Configurable rules for accepting or rejecting location claims

```
                    Witnessing Zone (radius=20m)

        W0 ●─────────────────────────────● W1
           │                             │
           │      🚗 red car             │
           │         ◆ Prover            │
           │                             │
           │   🚛 blue truck             │
           │                             │
        W3 ●─────────────────────────────● W2

    Witnesses query: "Is there a red car?"
    All witnesses answer: YES → Attestation issued
```

## Installation

```bash
cd /path/to/ns3-sim-pol

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install simpy numpy
```

## Quick Start

```bash
# Run all evaluation scenarios
python pol_simulation.py --all-scenarios

# Run custom scenario
python pol_simulation.py --witnesses 4 --quorum 3 --radius 20 --time 60
```

## Evaluation Results

### Baseline Scenarios

| Scenario | Witnesses | Quorum | Success Rate | Description |
|----------|-----------|--------|--------------|-------------|
| Baseline-4W | 4 | 3 | **100%** | Honest prover inside zone |
| Baseline-6W | 6 | 4 | **100%** | More witnesses, higher quorum |
| DistanceFraud | 4 | 3 | **0%** | Attacker correctly rejected |
| EdgePosition | 4 | 3 | **17%** | Prover at zone boundary |

### Visual Verification Scenarios

| Scenario | Scene Objects | Query | Success Rate |
|----------|---------------|-------|--------------|
| Red Car Present | red car, blue truck | "is there a red car?" | **80%** |
| No Red Car | blue truck only | "is there a red car?" | **0%** |

### Monte Carlo Analysis

Running the simulation with 20 runs to average out channel noise:

| Metric | Mean | Std Dev | Description |
|--------|------|---------|-------------|
| **Success Rate** | **97.8%** | ± 6.1% | Performance stability |
| **Precision** | **1.000** | 0.00 | No false positives consistently |
| **Recall** | **0.978** | ± 0.06 | Occasional false negatives |

### Security Metrics

| Metric | Value | Description |
|--------|-------|-------------|
| True Positives | 30 | Honest provers correctly admitted |
| False Positives | 0 | Attackers incorrectly admitted |
| True Negatives | 30 | Attackers correctly rejected |
| Precision | 1.0 | No false admissions |
| Recall | 1.0 | No false rejections (baseline) |

## Architecture

```
pol_simulation.py
├── Core Models
│   ├── Vector3              # 3D position
│   ├── ZoneConfig           # Zone configuration
│   ├── UWBChannelModel      # IEEE 802.15.4a propagation
│   └── DistanceBoundingProtocol  # Challenge-response
│
├── Environmental Sensing
│   ├── RfFingerprintSensor  # RSSI-based fingerprinting
│   ├── VisualSensor         # Scene object queries
│   └── EnvironmentalSensing # Combined sensor module
│
├── Admission Policies
│   ├── SupplyChainPolicy    # Distance + RF checks
│   ├── MediaProvenancePolicy # Visual verification
│   └── VisualVerificationPolicy # Scene query consensus
│
├── Nodes
│   ├── WitnessNode          # Witness with sensing + voting
│   └── ProverNode           # Location claim submitter
│
├── Protocol
│   ├── LocationClaim        # Prover's location claim
│   ├── Evidence             # Witness-collected evidence
│   ├── Vote                 # Witness vote on claim
│   └── Attestation          # Final quorum result
│
└── Simulation
    └── PolSimulation        # Main simulation environment
```

## Usage Examples

### Basic Simulation

```python
from pol_simulation import *

# Configure zone
config = ZoneConfig(
    center=Vector3(0, 0, 0),
    radius=20.0,
    n_witnesses=4,
    quorum_k=3
)

# Create policy
policy = SupplyChainPolicy(max_distance=40.0, rf_threshold=0.5)

# Run simulation
sim = PolSimulation(config, policy)
sim.create_witnesses()
prover = sim.create_prover(Vector3(5, 5, 1.5))
sim.run_periodic_claims(prover, interval=2.0, duration=60.0)
sim.run(60.0)

# Get results
results = sim.get_results()
print(f"Success rate: {results['performance']['success_rate']*100:.1f}%")
```

### Visual Scene Verification

```python
from pol_simulation import *

config = ZoneConfig(n_witnesses=4, quorum_k=3, radius=20.0)

# Policy requires visual confirmation
policy = VisualVerificationPolicy(
    max_distance=40.0,
    required_queries=["is there a red car?"],
    require_all_true=True
)

sim = PolSimulation(config, policy)

# Add objects to scene
sim.add_scene_object("car1", ObjectType.CAR, "red", Vector3(5, 5, 0))
sim.add_scene_object("truck1", ObjectType.TRUCK, "blue", Vector3(-5, 10, 0))

# Configure witnesses to query the scene
sim.create_witnesses()
sim.set_visual_queries(["is there a red car?"])

# Run
prover = sim.create_prover(Vector3(5, 5, 1.5))
sim.run_periodic_claims(prover, interval=2.0, duration=20.0)
sim.run(20.0)

# Red car present → claims admitted
# No red car → claims rejected
```

### Attack Simulation

```python
from pol_simulation import *

config = ZoneConfig(n_witnesses=4, quorum_k=3, radius=20.0)
policy = SupplyChainPolicy(max_distance=40.0)

sim = PolSimulation(config, policy)
sim.create_witnesses()

# Attacker outside zone trying distance fraud
attacker = sim.create_prover(
    Vector3(50, 50, 1.5),  # True position: outside zone
    attack_type=AttackType.DISTANCE_FRAUD  # Claims closer position
)

sim.run_periodic_claims(attacker, interval=2.0, duration=60.0)
sim.run(60.0)

results = sim.get_results()
# Expected: 0% success (attacker rejected)
```

### Monte Carlo Analysis

To obtain statistically significant results and minimize the impact of channel noise:

```bash
# Run 100 iterations of the Custom scenario
python pol_simulation.py --monte-carlo 100 --witnesses 4 --quorum 3

# Run 50 iterations of ALL scenarios
python pol_simulation.py --monte-carlo 50 --all-scenarios
```

## Configuration Reference

### ZoneConfig

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `center` | Vector3 | (0,0,0) | Zone center position |
| `radius` | float | 20.0 | Zone radius in meters |
| `n_witnesses` | int | 4 | Number of witness nodes |
| `quorum_k` | int | 3 | Minimum votes required |
| `block_interval` | float | 1.0 | Block production interval (s) |
| `zone_id` | str | "zone-01" | Unique zone identifier |

### Admission Policies

#### SupplyChainPolicy
```python
SupplyChainPolicy(
    max_distance=20.0,    # Maximum allowed distance (m)
    rf_threshold=0.6      # Minimum RF fingerprint similarity
)
```

#### VisualVerificationPolicy
```python
VisualVerificationPolicy(
    max_distance=20.0,
    rf_threshold=0.5,
    required_queries=["is there a red car?"],  # Queries that must pass
    require_all_true=True  # All queries must return True
)
```

### Visual Scene Objects

| ObjectType | Description |
|------------|-------------|
| `CAR` | Passenger vehicle |
| `TRUCK` | Large vehicle |
| `PERSON` | Human |
| `CONTAINER` | Shipping container |
| `FORKLIFT` | Industrial vehicle |

**Supported colors:** red, blue, green, yellow, white, black, orange, silver

### Attack Types

| Attack | Description |
|--------|-------------|
| `NONE` | Honest prover |
| `DISTANCE_FRAUD` | Claim closer position than actual |
| `RELAY` | Relay messages from remote location |
| `SCENE_SPOOFING` | Fake environmental features |
| `WITNESS_COLLUSION` | Colluding witnesses |

## Command Line Options

```
python pol_simulation.py [OPTIONS]

Options:
  --witnesses INT    Number of witness nodes (default: 4)
  --quorum INT       Quorum threshold k (default: 3)
  --radius FLOAT     Zone radius in meters (default: 20.0)
  --time FLOAT       Simulation duration in seconds (default: 60.0)
  --output STR       Output file prefix (default: pol-results)
  --verbose          Enable verbose output
  --all-scenarios    Run all evaluation scenarios
  --monte-carlo INT  Number of Monte Carlo iterations (default: 0 = disabled)
```

## Output Files

| File | Format | Content |
|------|--------|---------|
| `pol-results.json` | JSON | Detailed results with all metrics |
| `pol-results.csv` | CSV | Summary table for analysis |

### JSON Output Structure

```json
{
  "scenario": "Baseline-4W",
  "configuration": {
    "n_witnesses": 4,
    "quorum_k": 3,
    "zone_radius": 20.0
  },
  "performance": {
    "total_claims": 30,
    "successful_attestations": 30,
    "failed_attestations": 0,
    "success_rate": 1.0
  },
  "security": {
    "true_positives": 30,
    "false_positives": 0,
    "true_negatives": 0,
    "false_negatives": 0,
    "precision": 1.0,
    "recall": 1.0,
    "f1_score": 1.0
  }
}
```

## Protocol Details

### Distance Bounding

1. Witness sends random challenge bit
2. Prover responds immediately
3. Witness measures round-trip time (RTT)
4. Distance = (RTT × speed_of_light) / 2
5. Repeat for N rounds (default: 32)

### RF Fingerprinting

- Beacons broadcast at known positions
- Nodes measure RSSI from each beacon
- Fingerprint = vector of RSSI values
- Similarity computed using cosine distance

### Visual Verification

1. Witnesses observe scene from their positions
2. Query parsed: "is there a {color} {type}?"
3. Match against visible objects
4. Consensus required across quorum

### Attestation Flow

```
Prover                    Witnesses (W0, W1, W2, W3)
   │                              │
   │──── LocationClaim ──────────►│
   │                              │
   │                    ┌─────────┴─────────┐
   │                    │ Distance Bounding │
   │                    │ RF Fingerprint    │
   │                    │ Visual Query      │
   │                    └─────────┬─────────┘
   │                              │
   │                    ┌─────────┴─────────┐
   │                    │  Vote (admit/reject)
   │                    │  Broadcast to peers │
   │                    └─────────┬─────────┘
   │                              │
   │                    ┌─────────┴─────────┐
   │                    │  Quorum Check     │
   │                    │  (≥k votes agree) │
   │                    └─────────┬─────────┘
   │                              │
   │◄──── Attestation ────────────│
   │                              │
```

## Comparison with NS-3 Implementation

| Aspect | Python (SimPy) | NS-3 C++ |
|--------|----------------|----------|
| Lines of Code | ~700 | ~3000 |
| Setup Time | Seconds | Minutes |
| Network Simulation | Abstract | Full stack |
| Execution Speed | Faster | Slower |
| Realism | Medium | High |
| Extensibility | Easy | Complex |

## License

GPL-2.0-only

## References

- IEEE 802.15.4a UWB channel models
- Distance bounding protocols (Brands & Chaum)
- Proof-of-Location systems
