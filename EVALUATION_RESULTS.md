# PoL Witnessing Zone NS-3 Simulation - Evaluation Results

## Overview

This document summarizes the evaluation of the Proof-of-Location (PoL) Witnessing Zone simulation implemented in NS-3.40.

## Implementation Summary

The NS-3 module `pol-witnessing-zone` was implemented with the following components:

### Core Models
- **UWB Propagation Loss Model**: IEEE 802.15.4a-based channel models for LOS/NLOS environments
- **Distance Bounding Protocol**: Challenge-response protocol for ToF-based distance measurement
- **Environmental Sensing**: RF fingerprint, audio, visual, and temperature sensors
- **Ranging Error Model**: Realistic UWB ranging with multipath and noise

### Applications
- **Witness Application**: Full witness node implementation with claim processing, distance bounding, and admission evaluation
- **Prover Application**: Location claim submission with feature disclosure
- **Admission Policies**: Supply Chain, Media Provenance, and Mobility policies

### Attack Models
- Distance Fraud Attack
- Relay Attack
- Scene Spoofing Attack
- Witness Collusion

## Baseline Evaluation Results

### Scenario 1: Supply Chain (Cocoa) - 4 Witnesses

**Configuration:**
- Witnesses: 4 (square geometry)
- Quorum: 3
- Zone Radius: 20 m
- Simulation Time: 60 s
- Prover Position: (5, 5, 1.5) - inside zone

**Results:**
- Successful Attestations: 232
- Failed Attestations: 0
- Success Rate: 100.0%

### Scenario 2: Supply Chain (Cocoa) - 6 Witnesses

**Configuration:**
- Witnesses: 6 (hexagonal geometry)
- Quorum: 4
- Zone Radius: 20 m
- Simulation Time: 60 s
- Prover Position: (5, 5, 1.5) - inside zone

**Results:**
- Successful Attestations: 116
- Failed Attestations: 0
- Success Rate: 100.0%

## Key Findings

1. **Protocol Correctness**: The distance bounding protocol correctly measures distances between witnesses and prover using geometric distance calculation with ranging error model.

2. **Admission Policy**: The Supply Chain policy successfully admits honest provers when:
   - Distance bound is within the maximum allowed distance
   - RF fingerprint similarity exceeds the threshold

3. **Scalability**: Increasing witnesses from 4 to 6 with corresponding quorum increase (3 to 4) reduces throughput by approximately 50% due to higher coordination requirements.

4. **Network Requirements**: The simulation uses a shared CSMA channel for reliable inter-node communication, simulating a local zone network.

## Technical Notes

- Distance calculation uses geometric distance from mobility models with UWB ranging error model applied
- Block interval: 1 second
- Distance bounding: 32 rounds per session
- Claims submitted every 2 seconds

## Files Generated

- `/Users/fernando/Downloads/ns-3.40/contrib/pol-witnessing-zone/` - Full NS-3 module
- `pol-cocoa-results.csv` - CSV format results
- `pol-cocoa-results.json` - JSON format results

## Module Structure

```
contrib/pol-witnessing-zone/
├── CMakeLists.txt
├── model/
│   ├── pol-common.h              # Common types and structures
│   ├── pol-channel-model.h/cc    # UWB propagation model
│   ├── distance-bounding-protocol.h/cc  # DB protocol
│   ├── environmental-sensing.h/cc  # Sensor models
│   ├── admission-policy.h/cc     # Policy framework
│   ├── crypto-utils.h/cc         # Cryptographic utilities
│   ├── evidence-object.h/cc      # Evidence structures
│   ├── witness-application.h/cc  # Witness node application
│   ├── prover-application.h/cc   # Prover application
│   └── attack-models.h/cc        # Adversary models
├── helper/
│   ├── pol-zone-helper.h/cc      # Zone deployment helper
│   └── pol-stats-helper.h/cc     # Statistics collection
└── examples/
    └── pol-cocoa-example.cc      # Supply chain example
```

## Running the Simulation

```bash
cd /Users/fernando/Downloads/ns-3.40
./ns3 run "pol-cocoa-example --nWitnesses=4 --quorum=3 --simTime=60"
```

### Available Parameters:
- `--nWitnesses`: Number of witness nodes (default: 4)
- `--quorum`: Quorum threshold k (default: 3)
- `--radius`: Zone radius in meters (default: 20)
- `--simTime`: Simulation duration in seconds (default: 60)
- `--verbose`: Enable verbose logging (default: false)
- `--output`: Output file prefix (default: pol-cocoa-results)
