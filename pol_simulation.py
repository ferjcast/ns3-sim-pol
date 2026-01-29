#!/usr/bin/env python3
"""
PoL Witnessing Zone Simulation - Python Implementation

A discrete-event simulation of the Proof-of-Location witnessing zone protocol
using SimPy. This implements the same concepts as the NS-3 C++ module but
with significantly simpler code.

Author: PoL Simulation Framework
"""

import simpy
import numpy as np
import json
import csv
import hashlib
import time
import sys
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple
from enum import Enum, auto
from collections import defaultdict
import argparse


# =============================================================================
# Constants and Configuration
# =============================================================================

SPEED_OF_LIGHT = 299792458.0  # m/s
UWB_BANDWIDTH = 500e6  # 500 MHz


class Modality(Enum):
    RF_FINGERPRINT = auto()
    AUDIO = auto()
    VISUAL = auto()
    TEMPERATURE = auto()


class ObjectType(Enum):
    CAR = "car"
    TRUCK = "truck"
    PERSON = "person"
    CONTAINER = "container"
    FORKLIFT = "forklift"


@dataclass
class SceneObject:
    """Object in the visual scene."""
    obj_id: str
    obj_type: ObjectType
    color: str
    position: 'Vector3'
    size: float = 2.0  # meters

    def __repr__(self):
        return f"{self.color} {self.obj_type.value} at {self.position}"


class AttackType(Enum):
    NONE = auto()
    DISTANCE_FRAUD = auto()
    RELAY = auto()
    SCENE_SPOOFING = auto()
    WITNESS_COLLUSION = auto()


@dataclass
class Vector3:
    """3D position vector."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def distance_to(self, other: 'Vector3') -> float:
        return np.sqrt(
            (self.x - other.x)**2 +
            (self.y - other.y)**2 +
            (self.z - other.z)**2
        )

    def __repr__(self):
        return f"({self.x:.2f}, {self.y:.2f}, {self.z:.2f})"


@dataclass
class ZoneConfig:
    """Witnessing zone configuration."""
    center: Vector3 = field(default_factory=Vector3)
    radius: float = 20.0
    n_witnesses: int = 4
    quorum_k: int = 3
    block_interval: float = 1.0  # seconds
    zone_id: str = "zone-01"
    enabled_sensors: Set[Modality] = field(default_factory=lambda: {Modality.RF_FINGERPRINT})


@dataclass
class Beacon:
    """RF beacon for fingerprinting (co-located with witnesses)."""
    mac: str
    position: Vector3
    tx_power: float = 0.0  # dBm


# =============================================================================
# UWB Channel Model
# =============================================================================

class UWBChannelModel:
    """IEEE 802.15.4a UWB propagation model."""

    def __init__(self, nlos: bool = False):
        self.nlos = nlos
        self.path_loss_exp = 3.5 if nlos else 2.0
        self.shadow_std = 6.0 if nlos else 3.0  # dB
        self.d0 = 1.0  # reference distance
        self.pl0 = 40.0  # path loss at d0

    def get_path_loss(self, distance: float) -> float:
        """Calculate path loss in dB."""
        if distance < self.d0:
            distance = self.d0
        pl = self.pl0 + 10 * self.path_loss_exp * np.log10(distance / self.d0)
        shadow = np.random.normal(0, self.shadow_std)
        return pl + shadow

    def get_ranging_error(self, distance: float) -> float:
        """Get ranging error in meters."""
        # UWB ranging error model
        base_error = 0.1  # 10 cm base error
        distance_dependent = 0.01 * distance  # 1% of distance
        multipath = np.random.normal(0, 0.05)  # 5 cm multipath
        return base_error + distance_dependent + multipath


# =============================================================================
# Environmental Sensing
# =============================================================================

class RfFingerprintSensor:
    """RF fingerprint sensor model."""

    def __init__(self):
        self.beacons: List[Beacon] = []
        self.path_loss_exp = 2.5

    def add_beacon(self, mac: str, position: Vector3, tx_power: float = 0.0):
        self.beacons.append(Beacon(mac, position, tx_power))

    def sample(self, position: Vector3) -> Dict[str, float]:
        """Sample RSSI values at given position."""
        fingerprint = {}
        for beacon in self.beacons:
            distance = position.distance_to(beacon.position)
            if distance < 0.1:
                distance = 0.1
            # Free-space path loss with some noise
            rssi = beacon.tx_power - 40 - 10 * self.path_loss_exp * np.log10(distance)
            rssi += np.random.normal(0, 2)  # measurement noise
            fingerprint[beacon.mac] = rssi
        return fingerprint

    @staticmethod
    def compute_similarity(fp1: Dict[str, float], fp2: Dict[str, float]) -> float:
        """Compute cosine similarity between fingerprints."""
        common_keys = set(fp1.keys()) & set(fp2.keys())
        if not common_keys:
            return 0.0

        v1 = np.array([fp1[k] for k in common_keys])
        v2 = np.array([fp2[k] for k in common_keys])

        # Normalize to positive values for cosine similarity
        v1 = v1 - min(v1.min(), v2.min()) + 1
        v2 = v2 - min(v1.min(), v2.min()) + 1

        dot = np.dot(v1, v2)
        norm = np.linalg.norm(v1) * np.linalg.norm(v2)
        return dot / norm if norm > 0 else 0.0


class VisualSensor:
    """Visual sensor that can observe and query a scene."""

    def __init__(self, fov_angle: float = 120.0, max_range: float = 50.0):
        self.fov_angle = fov_angle  # degrees
        self.max_range = max_range  # meters
        self.scene_objects: List[SceneObject] = []

    def add_object(self, obj: SceneObject):
        """Add an object to the scene."""
        self.scene_objects.append(obj)

    def remove_object(self, obj_id: str):
        """Remove an object from the scene."""
        self.scene_objects = [o for o in self.scene_objects if o.obj_id != obj_id]

    def get_visible_objects(self, observer_pos: Vector3,
                            observer_heading: float = 0.0) -> List[SceneObject]:
        """Get objects visible from observer position."""
        visible = []
        for obj in self.scene_objects:
            distance = observer_pos.distance_to(obj.position)
            if distance > self.max_range:
                continue

            # Check if within field of view (simplified: 360° for simulation)
            # In real implementation, would check angle relative to heading
            visible.append(obj)

        return visible

    def query(self, observer_pos: Vector3, query_str: str) -> Tuple[bool, List[SceneObject]]:
        """
        Answer a natural language query about the scene.

        Supported query patterns:
        - "is there a {color} {type}?" -> bool
        - "is there a {type}?" -> bool
        - "what {type}s are there?" -> list

        Returns (answer, matching_objects)
        """
        visible = self.get_visible_objects(observer_pos)
        query_lower = query_str.lower().strip().rstrip('?')

        # Parse query
        matches = []

        # Check for color + type pattern
        for obj in visible:
            obj_desc = f"{obj.color} {obj.obj_type.value}".lower()
            type_only = obj.obj_type.value.lower()

            if obj_desc in query_lower or type_only in query_lower:
                # Check if color is specified and matches
                if obj.color.lower() in query_lower or obj.color.lower() not in query_lower:
                    matches.append(obj)

        # More precise matching
        matches = []
        for obj in visible:
            color_match = obj.color.lower() in query_lower
            type_match = obj.obj_type.value.lower() in query_lower

            # If color specified in query, both must match
            # If only type specified, type must match
            has_color_in_query = any(c in query_lower for c in
                ['red', 'blue', 'green', 'yellow', 'white', 'black', 'orange', 'silver'])

            if has_color_in_query:
                if color_match and type_match:
                    matches.append(obj)
            else:
                if type_match:
                    matches.append(obj)

        answer = len(matches) > 0
        return answer, matches

    def describe_scene(self, observer_pos: Vector3) -> str:
        """Get a text description of visible objects."""
        visible = self.get_visible_objects(observer_pos)
        if not visible:
            return "No objects visible"

        descriptions = [f"{obj.color} {obj.obj_type.value}" for obj in visible]
        return f"Visible: {', '.join(descriptions)}"


class EnvironmentalSensing:
    """Environmental sensing module."""

    def __init__(self):
        self.rf_sensor = RfFingerprintSensor()
        self.visual_sensor = VisualSensor()
        self.enabled_modalities: Set[Modality] = set()
        self.base_temperature = 25.0  # Celsius

    def enable_modality(self, modality: Modality, enabled: bool = True):
        if enabled:
            self.enabled_modalities.add(modality)
        else:
            self.enabled_modalities.discard(modality)

    def sample(self, position: Vector3) -> Dict[str, any]:
        """Sample all enabled sensors at position."""
        features = {}

        if Modality.RF_FINGERPRINT in self.enabled_modalities:
            features['rf_fingerprint'] = self.rf_sensor.sample(position)

        if Modality.TEMPERATURE in self.enabled_modalities:
            # Temperature with slight spatial variation
            temp = self.base_temperature + np.random.normal(0, 0.5)
            features['temperature'] = temp

        if Modality.AUDIO in self.enabled_modalities:
            # Simulated audio ambient level
            features['audio_level'] = 40 + np.random.normal(0, 5)  # dB

        if Modality.VISUAL in self.enabled_modalities:
            features['visual_scene'] = self.visual_sensor.describe_scene(position)

        return features

    def visual_query(self, position: Vector3, query: str) -> Tuple[bool, List[SceneObject]]:
        """Query the visual scene from a position."""
        return self.visual_sensor.query(position, query)


# =============================================================================
# Distance Bounding Protocol
# =============================================================================

@dataclass
class DBSession:
    """Distance bounding session state."""
    session_id: str
    prover_id: str
    witness_id: int
    n_rounds: int = 32
    challenges: List[int] = field(default_factory=list)
    responses: List[int] = field(default_factory=list)
    rtts: List[float] = field(default_factory=list)
    measured_distance: float = 0.0
    completed: bool = False
    valid: bool = False


class DistanceBoundingProtocol:
    """Challenge-response distance bounding protocol."""

    def __init__(self, n_rounds: int = 32, secret_key: bytes = None):
        self.n_rounds = n_rounds
        self.secret_key = secret_key or b'default_key_12345'

    def generate_challenges(self) -> List[int]:
        """Generate random challenge bits."""
        return [np.random.randint(0, 2) for _ in range(self.n_rounds)]

    def compute_response(self, challenge: int, round_idx: int) -> int:
        """Compute response to challenge."""
        # Simple XOR-based response (in real system, would use PRF)
        key_bit = self.secret_key[round_idx % len(self.secret_key)] & 1
        return challenge ^ key_bit

    def verify_response(self, challenge: int, response: int, round_idx: int) -> bool:
        """Verify a response is correct."""
        expected = self.compute_response(challenge, round_idx)
        return response == expected

    def compute_distance(self, rtts: List[float]) -> float:
        """Compute distance from RTT measurements."""
        if not rtts:
            return float('inf')
        # Use median to be robust against outliers
        median_rtt = np.median(rtts)
        return (median_rtt * SPEED_OF_LIGHT) / 2.0


# =============================================================================
# Admission Policies
# =============================================================================

class AdmissionPolicy:
    """Base admission policy."""

    def evaluate(self, claim: 'LocationClaim', evidence: 'Evidence') -> Tuple[bool, str]:
        raise NotImplementedError


class SupplyChainPolicy(AdmissionPolicy):
    """Supply chain admission policy."""

    def __init__(self, max_distance: float = 20.0, rf_threshold: float = 0.6):
        self.max_distance = max_distance
        self.rf_threshold = rf_threshold

    def evaluate(self, claim: 'LocationClaim', evidence: 'Evidence') -> Tuple[bool, str]:
        # Check distance bound
        if evidence.measured_distance > self.max_distance:
            return False, f"Distance {evidence.measured_distance:.2f}m exceeds max {self.max_distance}m"

        # Check RF fingerprint similarity
        if evidence.rf_similarity < self.rf_threshold:
            return False, f"RF similarity {evidence.rf_similarity:.2f} below threshold {self.rf_threshold}"

        return True, "Admitted"


class MediaProvenancePolicy(AdmissionPolicy):
    """Media provenance policy with visual checks."""

    def __init__(self, max_distance: float = 5.0, visual_threshold: float = 0.7):
        self.max_distance = max_distance
        self.visual_threshold = visual_threshold

    def evaluate(self, claim: 'LocationClaim', evidence: 'Evidence') -> Tuple[bool, str]:
        if evidence.measured_distance > self.max_distance:
            return False, f"Distance exceeds maximum"

        # Would check visual features here
        return True, "Admitted"


class VisualVerificationPolicy(AdmissionPolicy):
    """Policy that requires visual query consensus among witnesses."""

    def __init__(self, max_distance: float = 20.0, rf_threshold: float = 0.5,
                 required_queries: List[str] = None, require_all_true: bool = True):
        self.max_distance = max_distance
        self.rf_threshold = rf_threshold
        self.required_queries = required_queries or []
        self.require_all_true = require_all_true  # All queries must return True

    def evaluate(self, claim: 'LocationClaim', evidence: 'Evidence') -> Tuple[bool, str]:
        # Check distance bound
        if evidence.measured_distance > self.max_distance:
            return False, f"Distance {evidence.measured_distance:.2f}m exceeds max {self.max_distance}m"

        # Check RF fingerprint
        if evidence.rf_similarity < self.rf_threshold:
            return False, f"RF similarity {evidence.rf_similarity:.2f} below threshold"

        # Check required visual queries
        for query in self.required_queries:
            if query not in evidence.visual_query_results:
                return False, f"Missing visual query result: {query}"

            answer = evidence.visual_query_results[query]
            if self.require_all_true and not answer:
                return False, f"Visual query failed: {query}"

        return True, "Admitted (visual verification passed)"


# =============================================================================
# Claims and Evidence
# =============================================================================

@dataclass
class LocationClaim:
    """Location claim from prover."""
    claim_id: str
    prover_id: str
    claimed_position: Vector3
    timestamp: float
    features: Dict[str, any] = field(default_factory=dict)


@dataclass
class Evidence:
    """Evidence collected by witness."""
    claim_id: str
    witness_id: int
    measured_distance: float
    db_valid: bool
    rf_similarity: float
    features: Dict[str, any] = field(default_factory=dict)
    visual_query_results: Dict[str, bool] = field(default_factory=dict)  # query -> answer


@dataclass
class Vote:
    """Witness vote on a claim."""
    witness_id: int
    claim_id: str
    admit: bool
    reason: str
    evidence: Evidence


@dataclass
class Attestation:
    """Final attestation for a claim."""
    claim_id: str
    prover_id: str
    position: Vector3
    timestamp: float
    votes: List[Vote]
    admitted: bool
    quorum_reached: bool


# =============================================================================
# Witness Node
# =============================================================================

class WitnessNode:
    """Witness node in the witnessing zone."""

    def __init__(self, env: simpy.Environment, witness_id: int, position: Vector3,
                 config: ZoneConfig, policy: AdmissionPolicy, sensing: EnvironmentalSensing):
        self.env = env
        self.witness_id = witness_id
        self.position = position
        self.config = config
        self.policy = policy
        self.sensing = sensing
        self.channel = UWBChannelModel()
        self.db_protocol = DistanceBoundingProtocol()

        # State
        self.pending_claims: Dict[str, LocationClaim] = {}
        self.evidence: Dict[str, Evidence] = {}
        self.votes: Dict[str, Vote] = {}
        self.peer_votes: Dict[str, List[Vote]] = defaultdict(list)

        # Reference fingerprint at witness position
        self.ref_fingerprint = self.sensing.rf_sensor.sample(position)

        # Visual queries to ask about the scene
        self.visual_queries: List[str] = []

        # Statistics
        self.claims_processed = 0
        self.attestations_issued = 0

    def add_visual_query(self, query: str):
        """Add a visual query to ask when processing claims."""
        self.visual_queries.append(query)

    def process_claim(self, claim: LocationClaim, prover_position: Vector3) -> Evidence:
        """Process a location claim from a prover."""
        self.claims_processed += 1

        # Perform distance bounding
        true_distance = self.position.distance_to(prover_position)
        ranging_error = self.channel.get_ranging_error(true_distance)
        measured_distance = true_distance + ranging_error

        # Simulate DB protocol rounds
        challenges = self.db_protocol.generate_challenges()
        responses = [self.db_protocol.compute_response(c, i) for i, c in enumerate(challenges)]
        db_valid = all(
            self.db_protocol.verify_response(c, r, i)
            for i, (c, r) in enumerate(zip(challenges, responses))
        )

        # Verify RF fingerprint: Compare Prover's reported features (claim.features)
        # against the Expected features at the Claimed Position.
        # This checks "Is the RF environment at the Claimed Position consistent with what the Prover reported?"
        
        expected_features = self.sensing.sample(claim.claimed_position)
        
        # Extract RF fingerprint from claim features
        prover_rf_data = claim.features.get('rf_fingerprint', {})
        
        # Extract expected RF fingerprint
        expected_rf_data = expected_features.get('rf_fingerprint', {})
        
        rf_similarity = RfFingerprintSensor.compute_similarity(
            expected_rf_data, prover_rf_data
        )

        # Execute visual queries from witness position
        visual_results = {}
        for query in self.visual_queries:
            answer, objects = self.sensing.visual_query(self.position, query)
            visual_results[query] = answer

        evidence = Evidence(
            claim_id=claim.claim_id,
            witness_id=self.witness_id,
            measured_distance=measured_distance,
            db_valid=db_valid,
            rf_similarity=rf_similarity,
            features=claim.features,
            visual_query_results=visual_results
        )

        self.evidence[claim.claim_id] = evidence
        return evidence

    def vote_on_claim(self, claim: LocationClaim, evidence: Evidence) -> Vote:
        """Vote on whether to admit the claim."""
        admit, reason = self.policy.evaluate(claim, evidence)

        vote = Vote(
            witness_id=self.witness_id,
            claim_id=claim.claim_id,
            admit=admit,
            reason=reason,
            evidence=evidence
        )

        self.votes[claim.claim_id] = vote
        return vote

    def receive_peer_vote(self, vote: Vote):
        """Receive a vote from a peer witness."""
        self.peer_votes[vote.claim_id].append(vote)

    def check_quorum(self, claim_id: str) -> Optional[Attestation]:
        """Check if quorum is reached for a claim."""
        all_votes = self.peer_votes[claim_id].copy()
        if claim_id in self.votes:
            all_votes.append(self.votes[claim_id])

        if len(all_votes) < self.config.quorum_k:
            return None

        admit_votes = sum(1 for v in all_votes if v.admit)
        quorum_reached = len(all_votes) >= self.config.quorum_k
        admitted = admit_votes >= self.config.quorum_k

        if quorum_reached:
            claim = self.pending_claims.get(claim_id)
            if claim:
                self.attestations_issued += 1
                return Attestation(
                    claim_id=claim_id,
                    prover_id=claim.prover_id,
                    position=claim.claimed_position,
                    timestamp=self.env.now,
                    votes=all_votes,
                    admitted=admitted,
                    quorum_reached=True
                )

        return None


# =============================================================================
# Prover Node
# =============================================================================

class ProverNode:
    """Prover node requesting location attestation."""

    def __init__(self, env: simpy.Environment, prover_id: str, position: Vector3,
                 sensing: EnvironmentalSensing, attack_type: AttackType = AttackType.NONE):
        self.env = env
        self.prover_id = prover_id
        self.position = position
        self.sensing = sensing
        self.attack_type = attack_type

        # State
        self.claim_counter = 0
        self.successful_attestations = 0
        self.failed_attestations = 0
        self.attestations: List[Attestation] = []

    def create_claim(self) -> LocationClaim:
        """Create a location claim."""
        self.claim_counter += 1
        claim_id = f"{self.prover_id}-{self.claim_counter}"

        # Sample environmental features
        features = self.sensing.sample(self.position)

        # Apply attack modifications if any
        claimed_position = self.position
        if self.attack_type == AttackType.DISTANCE_FRAUD:
            # Claim to be closer than actual
            claimed_position = Vector3(
                self.position.x * 0.5,
                self.position.y * 0.5,
                self.position.z
            )

        return LocationClaim(
            claim_id=claim_id,
            prover_id=self.prover_id,
            claimed_position=claimed_position,
            timestamp=self.env.now,
            features=features
        )

    def receive_attestation(self, attestation: Attestation):
        """Receive attestation result."""
        self.attestations.append(attestation)
        if attestation.admitted:
            self.successful_attestations += 1
        else:
            self.failed_attestations += 1


# =============================================================================
# Simulation Environment
# =============================================================================

class PolSimulation:
    """Main simulation environment."""

    def __init__(self, config: ZoneConfig, policy: AdmissionPolicy):
        self.env = simpy.Environment()
        self.config = config
        self.policy = policy

        # Create shared sensing environment
        self.sensing = EnvironmentalSensing()
        self.sensing.enable_modality(Modality.RF_FINGERPRINT)
        self.sensing.enable_modality(Modality.TEMPERATURE)

        # Values will be added when witnesses are created


        # Nodes
        self.witnesses: List[WitnessNode] = []
        self.provers: List[ProverNode] = []

        # Statistics
        self.stats = {
            'total_claims': 0,
            'successful_attestations': 0,
            'failed_attestations': 0,
            'true_positives': 0,
            'false_positives': 0,
            'true_negatives': 0,
            'false_negatives': 0,
        }

    def _setup_beacons(self):
        """Setup RF beacons in the environment."""
        # DEPRECATED: Beacons are now co-located with witnesses in create_witnesses()
        pass

    def add_scene_object(self, obj_id: str, obj_type: ObjectType, color: str,
                         position: Vector3, size: float = 2.0):
        """Add an object to the visual scene."""
        obj = SceneObject(obj_id, obj_type, color, position, size)
        self.sensing.visual_sensor.add_object(obj)
        return obj

    def remove_scene_object(self, obj_id: str):
        """Remove an object from the scene."""
        self.sensing.visual_sensor.remove_object(obj_id)

    def set_visual_queries(self, queries: List[str]):
        """Set visual queries for all witnesses to answer."""
        for witness in self.witnesses:
            for query in queries:
                witness.add_visual_query(query)

    def get_scene_description(self) -> str:
        """Get a description of the current scene."""
        objects = self.sensing.visual_sensor.scene_objects
        if not objects:
            return "Empty scene"
        return "Scene objects: " + ", ".join(str(o) for o in objects)

    def create_witnesses(self) -> List[WitnessNode]:
        """Create witness nodes based on configuration."""
        positions = self._compute_witness_positions()

        for i, pos in enumerate(positions[:self.config.n_witnesses]):
            witness = WitnessNode(
                env=self.env,
                witness_id=i,
                position=pos,
                config=self.config,
                policy=self.policy,
                sensing=self.sensing
            )
            self.witnesses.append(witness)
            
            # Register this witness as an RF Beacon
            # MAC address derived from witness ID
            mac = f"00:11:22:33:44:{i:02x}"
            self.sensing.rf_sensor.add_beacon(mac, pos, tx_power=0.0)

        return self.witnesses

    def _compute_witness_positions(self) -> List[Vector3]:
        """Compute witness positions based on geometry."""
        positions = []
        n = self.config.n_witnesses

        if n == 4:
            # Square geometry
            half = self.config.radius / np.sqrt(2)
            positions = [
                Vector3(self.config.center.x - half, self.config.center.y - half, 3),
                Vector3(self.config.center.x + half, self.config.center.y - half, 3),
                Vector3(self.config.center.x + half, self.config.center.y + half, 3),
                Vector3(self.config.center.x - half, self.config.center.y + half, 3),
            ]
        else:
            # Hexagonal/circular geometry
            for i in range(n):
                angle = 2 * np.pi * i / n
                x = self.config.center.x + self.config.radius * np.cos(angle)
                y = self.config.center.y + self.config.radius * np.sin(angle)
                positions.append(Vector3(x, y, 3))

        return positions

    def create_prover(self, position: Vector3, prover_id: str = "prover-1",
                     attack_type: AttackType = AttackType.NONE) -> ProverNode:
        """Create a prover node."""
        prover = ProverNode(
            env=self.env,
            prover_id=prover_id,
            position=position,
            sensing=self.sensing,
            attack_type=attack_type
        )
        self.provers.append(prover)
        return prover

    def process_claim(self, prover: ProverNode):
        """Process a single claim from prover through all witnesses."""
        claim = prover.create_claim()
        self.stats['total_claims'] += 1

        # Each witness processes the claim
        votes = []
        for witness in self.witnesses:
            witness.pending_claims[claim.claim_id] = claim
            evidence = witness.process_claim(claim, prover.position)
            vote = witness.vote_on_claim(claim, evidence)
            votes.append(vote)

            # Broadcast vote to peers
            for peer in self.witnesses:
                if peer.witness_id != witness.witness_id:
                    peer.receive_peer_vote(vote)

        # Check quorum on first witness (all have same view)
        attestation = self.witnesses[0].check_quorum(claim.claim_id)

        if attestation:
            prover.receive_attestation(attestation)

            # Update statistics
            is_honest = prover.attack_type == AttackType.NONE
            is_inside = prover.position.distance_to(self.config.center) <= self.config.radius * 1.5

            if attestation.admitted:
                self.stats['successful_attestations'] += 1
                if is_honest and is_inside:
                    self.stats['true_positives'] += 1
                else:
                    self.stats['false_positives'] += 1
            else:
                self.stats['failed_attestations'] += 1
                if not is_honest or not is_inside:
                    self.stats['true_negatives'] += 1
                else:
                    self.stats['false_negatives'] += 1

    def run_periodic_claims(self, prover: ProverNode, interval: float, duration: float):
        """Run periodic claim submission."""
        def claim_process():
            while self.env.now < duration:
                self.process_claim(prover)
                yield self.env.timeout(interval)

        self.env.process(claim_process())

    def run(self, duration: float):
        """Run the simulation."""
        self.env.run(until=duration)

    def get_results(self) -> Dict:
        """Get simulation results."""
        total_attest = self.stats['successful_attestations'] + self.stats['failed_attestations']

        # Compute metrics
        tp = self.stats['true_positives']
        fp = self.stats['false_positives']
        tn = self.stats['true_negatives']
        fn = self.stats['false_negatives']

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        return {
            'configuration': {
                'n_witnesses': self.config.n_witnesses,
                'quorum_k': self.config.quorum_k,
                'zone_radius': self.config.radius,
            },
            'performance': {
                'total_claims': self.stats['total_claims'],
                'successful_attestations': self.stats['successful_attestations'],
                'failed_attestations': self.stats['failed_attestations'],
                'success_rate': self.stats['successful_attestations'] / total_attest if total_attest > 0 else 0,
            },
            'security': {
                'true_positives': tp,
                'false_positives': fp,
                'true_negatives': tn,
                'false_negatives': fn,
                'precision': precision,
                'recall': recall,
                'f1_score': f1,
            }
        }


# =============================================================================
# Main Entry Point
# =============================================================================

def run_scenario(name: str, n_witnesses: int, quorum: int, radius: float,
                sim_time: float, prover_pos: Vector3,
                attack_type: AttackType = AttackType.NONE,
                verbose: bool = False) -> Dict:
    """Run a single simulation scenario."""

    print(f"\n{'='*60}")
    print(f"Scenario: {name}")
    print(f"{'='*60}")
    print(f"  Witnesses: {n_witnesses}")
    print(f"  Quorum: {quorum}")
    print(f"  Zone Radius: {radius} m")
    print(f"  Simulation Time: {sim_time} s")
    print(f"  Prover Position: {prover_pos}")
    print(f"  Attack Type: {attack_type.name}")
    print()

    # Create configuration
    config = ZoneConfig(
        center=Vector3(0, 0, 0),
        radius=radius,
        n_witnesses=n_witnesses,
        quorum_k=quorum,
        zone_id=f"zone-{name}",
    )

    # Create policy
    policy = SupplyChainPolicy(
        max_distance=radius * 2.0,  # Cover zone diagonal
        rf_threshold=0.5
    )

    # Create simulation
    sim = PolSimulation(config, policy)
    sim.create_witnesses()

    # Create prover
    prover = sim.create_prover(prover_pos, attack_type=attack_type)

    # Run periodic claims
    claim_interval = 2.0
    sim.run_periodic_claims(prover, claim_interval, sim_time)

    # Run simulation
    start_time = time.time()
    sim.run(sim_time)
    elapsed = time.time() - start_time

    # Get results
    results = sim.get_results()
    results['scenario'] = name
    results['elapsed_time'] = elapsed

    # Print summary
    print("Results:")
    print(f"  Successful Attestations: {results['performance']['successful_attestations']}")
    print(f"  Failed Attestations: {results['performance']['failed_attestations']}")
    print(f"  Success Rate: {results['performance']['success_rate']*100:.1f}%")
    print(f"  Simulation Time: {elapsed:.2f}s")

    return results


def _run_single_simulation(name: str, n_witnesses: int, quorum: int, radius: float,
                          sim_time: float, prover_pos: Vector3,
                          attack_type: AttackType = AttackType.NONE) -> Dict:
    """Run a single simulation instance without printing."""
    # Create configuration
    config = ZoneConfig(
        center=Vector3(0, 0, 0),
        radius=radius,
        n_witnesses=n_witnesses,
        quorum_k=quorum,
        zone_id=f"zone-{name}",
    )

    # Create policy
    policy = SupplyChainPolicy(
        max_distance=radius * 2.0,  # Cover zone diagonal
        rf_threshold=0.5
    )

    # Create simulation
    sim = PolSimulation(config, policy)
    sim.create_witnesses()

    # Create prover
    prover = sim.create_prover(prover_pos, attack_type=attack_type)

    # Run periodic claims
    claim_interval = 2.0
    sim.run_periodic_claims(prover, claim_interval, sim_time)

    # Run simulation
    start_time = time.time()
    sim.run(sim_time)
    elapsed = time.time() - start_time

    # Get results
    results = sim.get_results()
    results['scenario'] = name
    results['elapsed_time'] = elapsed
    
    return results


def run_monte_carlo_analysis(iterations: int, name: str, n_witnesses: int, quorum: int, 
                             radius: float, sim_time: float, prover_pos: Vector3, 
                             attack_type: AttackType = AttackType.NONE) -> Dict:
    """Run Monte Carlo simulation analysis."""
    
    print(f"\n{'*'*60}")
    print(f"Monte Carlo Simulation: {name}")
    print(f"Iterations: {iterations}")
    print(f"Configuration: {n_witnesses} witnesses, Quorum {quorum}, Radius {radius}m")
    print(f"{'*'*60}")

    stats = defaultdict(list)
    
    start_time = time.time()
    
    for i in range(iterations):
        res = _run_single_simulation(name, n_witnesses, quorum, radius, sim_time, prover_pos, attack_type)
        
        stats['success_rate'].append(res['performance']['success_rate'])
        stats['precision'].append(res['security']['precision'])
        stats['recall'].append(res['security']['recall'])
        stats['fps'].append(res['security']['false_positives'])
        stats['fns'].append(res['security']['false_negatives'])
        stats['tps'].append(res['security']['true_positives'])
        
        # Progress bar
        if (i+1) % 10 == 0 or i == iterations-1:
            sys.stdout.write(f"\rProgress: {i+1}/{iterations} runs completed")
            sys.stdout.flush()
    print("\n")
    
    total_time = time.time() - start_time
    
    def print_stat(label, data):
        d = np.array(data)
        print(f"  {label:<20}: Mean={np.mean(d):.4f} | Std={np.std(d):.4f} | Min={np.min(d):.4f} | Max={np.max(d):.4f}")
        return np.mean(d), np.std(d)
        
    print(f"Results Summary for {name} ({iterations} runs):")
    print("-" * 60)
    print_stat("Success Rate", stats['success_rate'])
    print_stat("Precision", stats['precision'])
    print_stat("Recall", stats['recall'])
    print_stat("True Positives", stats['tps'])
    print_stat("False Positives", stats['fps'])
    print_stat("False Negatives", stats['fns'])
    print("-" * 60)
    print(f"Total Computation Time: {total_time:.2f}s (Avg: {total_time/iterations:.4f}s/run)")
    
    return {
        'scenario': name,
        'mode': 'monte_carlo',
        'iterations': iterations,
        'summary': {k: {'mean': float(np.mean(v)), 'std': float(np.std(v))} for k, v in stats.items()}
    }






def run_visual_scenario(verbose: bool = False) -> Dict:
    """Run visual verification scenario with scene objects and queries."""

    print(f"\n{'='*60}")
    print("Scenario: Visual Verification (Red Car)")
    print(f"{'='*60}")
    print("  Testing: Witnesses verify 'Is there a red car?' in the zone")
    print()

    # Configuration
    config = ZoneConfig(
        center=Vector3(0, 0, 0),
        radius=20.0,
        n_witnesses=4,
        quorum_k=3,
        zone_id="visual-zone",
    )

    # Policy requiring visual query to pass
    policy = VisualVerificationPolicy(
        max_distance=40.0,
        rf_threshold=0.5,
        required_queries=["is there a red car?"],
        require_all_true=True
    )

    # Create simulation
    sim = PolSimulation(config, policy)

    # Add a red car to the scene
    sim.add_scene_object("car1", ObjectType.CAR, "red", Vector3(5, 5, 0), size=4.0)
    sim.add_scene_object("truck1", ObjectType.TRUCK, "blue", Vector3(-5, 10, 0), size=6.0)

    print(f"  {sim.get_scene_description()}")
    print()

    # Create witnesses and set visual query
    sim.create_witnesses()
    sim.set_visual_queries(["is there a red car?"])

    # Create prover near the car
    prover = sim.create_prover(Vector3(5, 5, 1.5))

    # Run claims
    sim.run_periodic_claims(prover, interval=2.0, duration=20.0)

    start_time = time.time()
    sim.run(20.0)
    elapsed = time.time() - start_time

    results = sim.get_results()
    results['scenario'] = "VisualVerification-RedCar"
    results['elapsed_time'] = elapsed
    results['visual_query'] = "is there a red car?"
    results['scene_objects'] = ["red car at (5,5)", "blue truck at (-5,10)"]

    print("Results:")
    print(f"  Successful Attestations: {results['performance']['successful_attestations']}")
    print(f"  Failed Attestations: {results['performance']['failed_attestations']}")
    print(f"  Success Rate: {results['performance']['success_rate']*100:.1f}%")

    # Now test with NO red car (remove it)
    print(f"\n{'='*60}")
    print("Scenario: Visual Verification (No Red Car)")
    print(f"{'='*60}")

    sim2 = PolSimulation(config, policy)
    # Only blue truck, no red car
    sim2.add_scene_object("truck1", ObjectType.TRUCK, "blue", Vector3(-5, 10, 0), size=6.0)

    print(f"  {sim2.get_scene_description()}")
    print()

    sim2.create_witnesses()
    sim2.set_visual_queries(["is there a red car?"])
    prover2 = sim2.create_prover(Vector3(5, 5, 1.5))
    sim2.run_periodic_claims(prover2, interval=2.0, duration=20.0)
    sim2.run(20.0)

    results2 = sim2.get_results()
    print("Results (no red car in scene):")
    print(f"  Successful Attestations: {results2['performance']['successful_attestations']}")
    print(f"  Failed Attestations: {results2['performance']['failed_attestations']}")
    print(f"  Success Rate: {results2['performance']['success_rate']*100:.1f}%")
    print("  (Expected: 0% - query 'is there a red car?' should fail)")

    return results


def main():
    parser = argparse.ArgumentParser(description='PoL Witnessing Zone Simulation')
    parser.add_argument('--witnesses', type=int, default=4, help='Number of witnesses')
    parser.add_argument('--quorum', type=int, default=3, help='Quorum threshold')
    parser.add_argument('--radius', type=float, default=20.0, help='Zone radius (m)')
    parser.add_argument('--time', type=float, default=60.0, help='Simulation time (s)')
    parser.add_argument('--output', type=str, default='pol-results', help='Output file prefix')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--all-scenarios', action='store_true', help='Run all evaluation scenarios')
    parser.add_argument('--monte-carlo', type=int, default=0, help='Number of Monte Carlo iterations (default: 0 = disabled)')
    args = parser.parse_args()

    print("=" * 60)
    print("PoL Witnessing Zone Simulation - Python Implementation")
    print("=" * 60)

    all_results = []

    if args.all_scenarios:
        # Run baseline scenarios from spec
        scenarios = [
            # Baseline scenarios
            ("Baseline-4W", 4, 3, 20.0, 60.0, Vector3(5, 5, 1.5), AttackType.NONE),
            ("Baseline-6W", 6, 4, 20.0, 60.0, Vector3(5, 5, 1.5), AttackType.NONE),

            # Attack scenarios
            ("DistanceFraud", 4, 3, 20.0, 60.0, Vector3(30, 30, 1.5), AttackType.DISTANCE_FRAUD),

            # Edge position
            ("EdgePosition", 4, 3, 20.0, 60.0, Vector3(15, 15, 1.5), AttackType.NONE),
        ]

        for name, nw, q, r, t, pos, attack in scenarios:
            if args.monte_carlo > 0:
                results = run_monte_carlo_analysis(args.monte_carlo, name, nw, q, r, t, pos, attack)
            else:
                results = run_scenario(name, nw, q, r, t, pos, attack, args.verbose)
            all_results.append(results)

        # Run visual verification scenario (skip for Monte Carlo as it's deterministic-ish/qualitative)
        if args.monte_carlo == 0:
            visual_results = run_visual_scenario(args.verbose)
            all_results.append(visual_results)
    else:
        # Run single scenario with command-line parameters
        if args.monte_carlo > 0:
            results = run_monte_carlo_analysis(
                args.monte_carlo,
                "Custom",
                args.witnesses,
                args.quorum,
                args.radius,
                args.time,
                Vector3(5, 5, 1.5), # Standard position
                AttackType.NONE
            )
        else:
            results = run_scenario(
                "Custom",
                args.witnesses,
                args.quorum,
                args.radius,
                args.time,
                Vector3(5, 5, 1.5),
                AttackType.NONE,
                args.verbose
            )
        all_results.append(results)

    # Export results
    # JSON
    with open(f"{args.output}.json", 'w') as f:
        json.dump(all_results, f, indent=2)

    # CSV
    # CSV
    with open(f"{args.output}.csv", 'w', newline='') as f:
        writer = csv.writer(f)
        
        has_mc = any(r.get('mode') == 'monte_carlo' for r in all_results)
        
        if has_mc:
             writer.writerow(['Scenario', 'Iterations', 'SuccessRate(Mean)', 'SuccessRate(Std)', 'Precision(Mean)', 'Recall(Mean)'])
             for r in all_results:
                 if r.get('mode') == 'monte_carlo':
                     s = r['summary']
                     writer.writerow([
                         r['scenario'], 
                         r['iterations'],
                         f"{s['success_rate']['mean']:.4f}",
                         f"{s['success_rate']['std']:.4f}",
                         f"{s['precision']['mean']:.4f}",
                         f"{s['recall']['mean']:.4f}"
                     ])
                 else:
                     # For single runs mixed with MC, just note it in scenario
                     writer.writerow([r['scenario'], "1 (Single)", f"{r['performance']['success_rate']:.4f}", "0.0", f"{r['security']['precision']:.4f}", f"{r['security']['recall']:.4f}"])
        else:
            writer.writerow([
                'Scenario', 'Witnesses', 'Quorum', 'Radius',
                'Successful', 'Failed', 'SuccessRate',
                'TP', 'FP', 'TN', 'FN', 'Precision', 'Recall', 'F1'
            ])
            for r in all_results:
                writer.writerow([
                    r['scenario'],
                    r['configuration']['n_witnesses'],
                    r['configuration']['quorum_k'],
                    r['configuration']['zone_radius'],
                    r['performance']['successful_attestations'],
                    r['performance']['failed_attestations'],
                    f"{r['performance']['success_rate']*100:.1f}",
                    r['security']['true_positives'],
                    r['security']['false_positives'],
                    r['security']['true_negatives'],
                    r['security']['false_negatives'],
                    f"{r['security']['precision']:.3f}",
                    f"{r['security']['recall']:.3f}",
                    f"{r['security']['f1_score']:.3f}",
                ])

    print(f"\n{'='*60}")
    print("Results exported to:")
    print(f"  {args.output}.json")
    print(f"  {args.output}.csv")
    print("=" * 60)


if __name__ == '__main__':
    main()
