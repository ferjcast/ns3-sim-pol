# NS-3 Simulation Specification: Proof-of-Location Witnessing Zone Evaluation

## Document Overview

This specification defines the NS-3 simulation framework for evaluating the **Augmented Witnessing Zone Architecture** for Proof-of-Location (PoL) systems as described in "Decentralized Proof-of-Location for Content Provenance: Towards Capture-Time Authenticity" (Brito, 2025).

**Target Simulator:** NS-3 (version 3.40+)
**Primary Modules:** `wifi`, `lr-wpan`, `mobility`, `internet`, `applications`, `propagation`
**Language:** C++ with Python bindings for analysis

---

## 1. System Architecture Overview

### 1.1 Core Components

The simulation models a **witnessing zone** as a bounded spatial region where:

- **Prover (P):** Mobile device claiming location presence
- **Witnesses (W₁...Wₙ):** Fixed infrastructure nodes at known positions
- **Verifier (V):** External entity receiving and validating evidence objects
- **Zone Coordinator:** Manages block intervals and consensus (optional ledger node)

### 1.2 Protocol Phases per Block Interval

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Block Interval T                                 │
├──────────────┬──────────────┬──────────────┬───────────────────────┤
│ Phase 1      │ Phase 2      │ Phase 3      │ Phase 4               │
│ Distance     │ Environmental│ Policy-Based │ Commitment &          │
│ Bounding     │ Sensing      │ Reasoning    │ Signature Aggregation │
│ (db₁...dbₙ)  │ ({fm}w)      │ (admit∈{0,1})│ (σQ, Merkle roots)    │
└──────────────┴──────────────┴──────────────┴───────────────────────┘
```

---

## 2. Simulation Parameters

### 2.1 Spatial Configuration

| Parameter | Symbol | Default Value | Range | Description |
|-----------|--------|---------------|-------|-------------|
| Zone radius | R_zone | 50 m | 10-200 m | Maximum witnessing zone extent |
| Number of witnesses | n | 4 | 3-12 | Witnesses in fully-connected mesh |
| Quorum threshold | k | 3 | ⌈n/2⌉+1 to n | Required attestations for admission |
| Witness height | h_w | 3.0 m | 1.5-10 m | Mounting height of witness nodes |
| Prover height | h_p | 1.5 m | 0.5-2.0 m | Height of prover device |
| Inter-witness distance | d_ww | 25 m | 10-100 m | Spacing between witnesses |

### 2.2 Temporal Configuration

| Parameter | Symbol | Default Value | Range | Description |
|-----------|--------|---------------|-------|-------------|
| Block interval | T | 1000 ms | 100-5000 ms | Duration of each attestation round |
| Distance bounding window | T_db | 100 ms | 10-500 ms | Max time for DB exchange |
| Sensing window | T_sense | 200 ms | 50-1000 ms | Environmental sampling duration |
| Reasoning window | T_reason | 300 ms | 100-1000 ms | Policy evaluation time |
| Signature window | T_sig | 400 ms | 100-500 ms | Commitment and aggregation time |
| Clock drift | σ_clock | 1 ms | 0-10 ms | Std dev of local clock offset |
| Simulation duration | T_sim | 300 s | 60-3600 s | Total simulation time |

### 2.3 Communication Parameters

| Parameter | Symbol | Default Value | Range | Description |
|-----------|--------|---------------|-------|-------------|
| DB protocol | - | UWB | UWB/BLE | Distance bounding radio |
| Control channel | - | WiFi 6 | WiFi/LoRa | Witness mesh communication |
| UWB frequency | f_uwb | 6.5 GHz | 3.1-10.6 GHz | IEEE 802.15.4z band |
| UWB bandwidth | BW_uwb | 500 MHz | 500-1500 MHz | Channel bandwidth |
| WiFi standard | - | 802.11ax | 11n/11ac/11ax | Control plane |
| TX power (UWB) | P_tx_uwb | -14.3 dBm | -20 to 0 dBm | Per FCC regulations |
| TX power (WiFi) | P_tx_wifi | 20 dBm | 10-30 dBm | Access point power |

### 2.4 Distance Bounding Parameters

| Parameter | Symbol | Default Value | Range | Description |
|-----------|--------|---------------|-------|-------------|
| Speed of light | c | 299792458 m/s | - | Physical constant |
| Timing resolution | τ_res | 1 ns | 0.1-10 ns | ToF measurement precision |
| Max ranging error | ε_db | 0.3 m | 0.1-1.0 m | Distance bound uncertainty |
| Challenge-response rounds | N_cr | 32 | 8-128 | Rapid bit exchanges |
| Bit duration | T_bit | 1 μs | 0.5-10 μs | Per-bit exchange time |

---

## 3. Network Topology Models

### 3.1 Witness Placement Geometries

```cpp
enum class WitnessGeometry {
    SQUARE,           // 4 witnesses at corners of square
    PENTAGON,         // 5 witnesses in regular pentagon
    HEXAGONAL,        // 6 witnesses in honeycomb pattern
    LINEAR,           // Witnesses along a line (corridor)
    RANDOM_UNIFORM,   // Uniform random within zone
    CUSTOM            // User-defined positions
};
```

#### 3.1.1 Square Configuration (Default for 2D Localization)

```cpp
// 4 coplanar witnesses for 2D distance bounding
struct SquareWitnessConfig {
    double side_length = 50.0;  // meters
    Vector3D center = {0, 0, 0};
    double height = 3.0;        // witness mounting height
    
    std::vector<Vector3D> GetPositions() {
        double half = side_length / 2.0;
        return {
            {center.x - half, center.y - half, height},  // W1
            {center.x + half, center.y - half, height},  // W2
            {center.x + half, center.y + half, height},  // W3
            {center.x - half, center.y + half, height}   // W4
        };
    }
};
```

### 3.2 Prover Mobility Models

```cpp
enum class ProverMobility {
    STATIC,               // Fixed position (baseline)
    RANDOM_WALK,          // Brownian motion within zone
    RANDOM_WAYPOINT,      // Random destinations with pause
    GAUSS_MARKOV,         // Correlated velocity model
    PEDESTRIAN,           // Realistic walking patterns
    VEHICULAR,            // Vehicle crossing zone
    TRAJECTORY_FILE       // Replay from trace file
};
```

#### 3.2.1 Mobility Configuration

```cpp
struct ProverMobilityConfig {
    ProverMobility model = ProverMobility::RANDOM_WAYPOINT;
    double min_speed = 0.5;       // m/s (pedestrian)
    double max_speed = 2.0;       // m/s
    double pause_time = 5.0;      // seconds at waypoints
    Rectangle bounds;             // Constrained to zone
    double height = 1.5;          // meters
};
```

---

## 4. Channel and Propagation Models

### 4.1 UWB Channel Model (Distance Bounding)

Based on IEEE 802.15.4a channel models for indoor/outdoor environments.

```cpp
// UWB propagation loss model
class UwbPropagationLossModel : public PropagationLossModel {
public:
    enum Environment {
        RESIDENTIAL_LOS,      // CM1: Line-of-sight residential
        RESIDENTIAL_NLOS,     // CM2: Non-line-of-sight residential
        OFFICE_LOS,           // CM3: Line-of-sight office
        OFFICE_NLOS,          // CM4: Non-line-of-sight office
        OUTDOOR_LOS,          // CM5: Line-of-sight outdoor
        OUTDOOR_NLOS,         // CM6: Non-line-of-sight outdoor
        INDUSTRIAL_LOS,       // CM7: Line-of-sight industrial
        INDUSTRIAL_NLOS       // CM8: Non-line-of-sight industrial
    };
    
    // Path loss: PL(d) = PL0 + 10*n*log10(d/d0) + S
    // where S ~ N(0, σ_s²) is shadowing
    struct ChannelParams {
        double PL0;           // Reference path loss at d0=1m (dB)
        double n;             // Path loss exponent
        double sigma_s;       // Shadowing std dev (dB)
    };
    
    static constexpr ChannelParams CM5_OUTDOOR_LOS = {45.6, 1.63, 2.0};
    static constexpr ChannelParams CM6_OUTDOOR_NLOS = {51.2, 2.44, 4.0};
};
```

### 4.2 WiFi Channel Model (Control Plane)

```cpp
// Use NS-3 built-in models
void ConfigureWifiChannel(Ptr<YansWifiChannel> channel) {
    // Log-distance path loss
    Ptr<LogDistancePropagationLossModel> lossModel = 
        CreateObject<LogDistancePropagationLossModel>();
    lossModel->SetAttribute("Exponent", DoubleValue(3.0));
    lossModel->SetAttribute("ReferenceLoss", DoubleValue(46.67));
    
    // Nakagami fading for urban environment
    Ptr<NakagamiPropagationLossModel> fading = 
        CreateObject<NakagamiPropagationLossModel>();
    lossModel->SetNext(fading);
    
    channel->SetPropagationLossModel(lossModel);
    
    // Constant speed delay
    channel->SetPropagationDelayModel(
        CreateObject<ConstantSpeedPropagationDelayModel>());
}
```

### 4.3 Ranging Error Model

```cpp
// ToF-based ranging with errors
class RangingErrorModel {
public:
    struct ErrorParams {
        double bias = 0.0;              // Systematic error (m)
        double sigma_los = 0.1;         // LOS std dev (m)
        double sigma_nlos = 0.5;        // NLOS std dev (m)
        double multipath_prob = 0.1;    // P(multipath error)
        double multipath_excess = 2.0;  // Additional NLOS delay (m equiv)
    };
    
    double GetRangingEstimate(double true_distance, bool is_los) {
        double sigma = is_los ? m_params.sigma_los : m_params.sigma_nlos;
        double error = m_rng->GetNormalValue(m_params.bias, sigma);
        
        // Multipath adds positive bias (longer apparent distance)
        if (m_rng->GetUniformValue(0, 1) < m_params.multipath_prob) {
            error += m_rng->GetExponentialValue(m_params.multipath_excess);
        }
        
        return std::max(0.0, true_distance + error);
    }
    
private:
    ErrorParams m_params;
    Ptr<UniformRandomVariable> m_rng;
};
```

---

## 5. Protocol Implementation

### 5.1 Distance Bounding Protocol

```cpp
// Implements challenge-response distance bounding
class DistanceBoundingProtocol : public Application {
public:
    // Protocol states
    enum State {
        IDLE,
        CHALLENGE_SENT,
        RESPONSE_RECEIVED,
        ROUND_COMPLETE
    };
    
    // Configuration
    struct Config {
        uint32_t num_rounds = 32;
        Time bit_duration = NanoSeconds(1000);
        Time timeout = MilliSeconds(100);
        double max_distance = 50.0;  // meters
    };
    
    // Rapid bit exchange timing
    struct RoundResult {
        uint32_t round_id;
        Time challenge_sent;
        Time response_received;
        double computed_distance;
        bool valid;
    };
    
    // Distance bound computation
    double ComputeDistanceBound() {
        std::vector<double> valid_distances;
        for (const auto& result : m_results) {
            if (result.valid) {
                Time rtt = result.response_received - result.challenge_sent;
                double distance = (rtt.GetSeconds() * SPEED_OF_LIGHT) / 2.0;
                valid_distances.push_back(distance);
            }
        }
        
        // Use minimum of valid estimates (attacker can only increase distance)
        if (valid_distances.empty()) return -1.0;
        return *std::min_element(valid_distances.begin(), valid_distances.end());
    }
    
protected:
    void StartRound();
    void HandleChallenge(Ptr<Packet> challenge);
    void HandleResponse(Ptr<Packet> response, Time received_time);
    void FinalizeDistanceBound();
    
private:
    Config m_config;
    std::vector<RoundResult> m_results;
    State m_state;
};
```

### 5.2 Environmental Sensing Module

```cpp
// Multimodal sensor simulation
class EnvironmentalSensingModule {
public:
    // Sensor modalities
    enum Modality {
        RF_FINGERPRINT,    // BLE/WiFi signal strength pattern
        AMBIENT_AUDIO,     // Audio spectral features
        VISUAL_SKETCH,     // Image perceptual hash
        TEMPERATURE,       // Ambient temperature
        BAROMETRIC,        // Atmospheric pressure
        IMU_SIGNATURE      // Inertial signature
    };
    
    // Feature descriptor with metadata
    struct FeatureDescriptor {
        Modality modality;
        std::vector<double> features;
        Time timestamp;
        double quality;        // 0-1 confidence
        double freshness;      // Time since last update
    };
    
    // RF fingerprint model
    struct RfFingerprint {
        std::map<std::string, double> beacon_rssi;  // BSSID -> RSSI
        std::vector<double> GetFeatureVector() const;
        double ComputeSimilarity(const RfFingerprint& other) const;
    };
    
    // Configure which modalities are active
    void EnableModality(Modality m, bool enabled);
    
    // Sample all enabled sensors
    std::vector<FeatureDescriptor> SampleEnvironment(Time window);
    
    // Compare prover-disclosed vs witness-observed features
    double ComputeCoherence(
        const std::vector<FeatureDescriptor>& prover_features,
        const std::vector<FeatureDescriptor>& witness_features,
        Modality modality
    );
    
private:
    std::set<Modality> m_enabled_modalities;
    std::map<Modality, Ptr<SensorModel>> m_sensor_models;
};
```

### 5.3 Policy-Based Admission Logic

```cpp
// Versioned admission policy
class AdmissionPolicy {
public:
    struct PolicyVersion {
        std::string version_id;
        Time effective_from;
        std::string description;
    };
    
    // Decision output
    struct AdmissionDecision {
        bool admit;
        double confidence;
        std::map<std::string, double> scores;  // Per-criterion scores
        std::string reason;
    };
    
    // Abstract base policy
    virtual AdmissionDecision Evaluate(
        const Claim& claim,
        const std::vector<FeatureDescriptor>& prover_features,
        const std::vector<FeatureDescriptor>& witness_features,
        double distance_bound
    ) = 0;
    
    PolicyVersion GetVersion() const { return m_version; }
    
protected:
    PolicyVersion m_version;
};

// Supply chain policy (Cocoa profile)
class SupplyChainPolicy : public AdmissionPolicy {
public:
    SupplyChainPolicy() {
        m_version = {"v1-cocoa", Now(), "Supply chain sealing policy"};
        m_ble_threshold = 0.85;
        m_max_distance = 10.0;
    }
    
    AdmissionDecision Evaluate(...) override {
        AdmissionDecision decision;
        decision.scores["distance"] = (distance_bound <= m_max_distance) ? 1.0 : 0.0;
        
        // BLE fingerprint similarity
        double ble_sim = ComputeBleFingerprints(prover_features, witness_features);
        decision.scores["ble_match"] = ble_sim;
        
        decision.admit = (decision.scores["distance"] == 1.0) && 
                         (ble_sim >= m_ble_threshold);
        decision.confidence = (decision.scores["distance"] + ble_sim) / 2.0;
        
        return decision;
    }
    
private:
    double m_ble_threshold;
    double m_max_distance;
};

// Media provenance policy
class MediaProvenancePolicy : public AdmissionPolicy {
public:
    MediaProvenancePolicy() {
        m_version = {"v2-media", Now(), "Media capture provenance policy"};
        m_visual_threshold = 0.70;
        m_audio_threshold = 0.60;
    }
    
    AdmissionDecision Evaluate(...) override {
        AdmissionDecision decision;
        
        // Visual similarity (pHash comparison)
        double visual_sim = ComputeVisualSimilarity(prover_features, witness_features);
        decision.scores["visual"] = visual_sim;
        
        // Audio fingerprint match
        double audio_sim = ComputeAudioSimilarity(prover_features, witness_features);
        decision.scores["audio"] = audio_sim;
        
        // RF beacon overlap
        double rf_overlap = ComputeRfOverlap(prover_features, witness_features);
        decision.scores["rf_beacons"] = rf_overlap;
        
        decision.admit = (visual_sim >= m_visual_threshold) &&
                         (audio_sim >= m_audio_threshold);
        decision.confidence = (visual_sim + audio_sim + rf_overlap) / 3.0;
        
        return decision;
    }
    
private:
    double m_visual_threshold;
    double m_audio_threshold;
};

// Mobility policy
class MobilityPolicy : public AdmissionPolicy {
public:
    MobilityPolicy() {
        m_version = {"v3-mobility", Now(), "Zone crossing mobility policy"};
    }
    
    AdmissionDecision Evaluate(...) override {
        // IMU trajectory validation
        // RF fingerprint consistency
        // Doppler shift estimation (if available)
        // ...
    }
};
```

### 5.4 Witness Node Application

```cpp
class WitnessApplication : public Application {
public:
    // Witness configuration
    struct Config {
        uint32_t witness_id;
        Vector3D position;
        uint32_t quorum_threshold;
        Ptr<AdmissionPolicy> policy;
        Time block_interval;
    };
    
    // Block interval state
    struct BlockState {
        uint64_t block_id;
        Time start_time;
        std::map<Address, double> distance_bounds;
        std::map<Address, std::vector<FeatureDescriptor>> prover_features;
        std::map<Address, AdmissionDecision> decisions;
    };
    
    // Evidence commitment
    struct WitnessCommitment {
        uint64_t block_id;
        Address prover;
        Hash256 merkle_root;       // Root of evidence tree
        std::vector<uint8_t> signature;
    };
    
protected:
    void StartApplication() override;
    void StopApplication() override;
    
    // Protocol handlers
    void OnNewBlockInterval();
    void HandleProverClaim(Ptr<Packet> claim, Address prover);
    void PerformDistanceBounding(Address prover);
    void SampleEnvironment();
    void EvaluateAdmission(Address prover);
    void CommitAndSign(Address prover);
    void BroadcastAttestation(const WitnessCommitment& commitment);
    
    // Consensus participation
    void HandlePeerAttestation(const WitnessCommitment& peer_commitment);
    void CheckQuorum(Address prover);
    void FinalizeBlock();
    
private:
    Config m_config;
    BlockState m_current_block;
    Ptr<EnvironmentalSensingModule> m_sensors;
    Ptr<DistanceBoundingProtocol> m_db_protocol;
    Ptr<Crypto> m_crypto;
};
```

### 5.5 Prover Node Application

```cpp
class ProverApplication : public Application {
public:
    // Claim structure
    struct Claim {
        Address prover_id;
        Vector3D claimed_position;
        Time claimed_time;
        std::vector<FeatureDescriptor> disclosed_features;
        std::vector<uint8_t> media_hash;      // Optional: content hash
        std::vector<uint8_t> signature;
    };
    
    // Evidence object received from zone
    struct EvidenceObject {
        uint64_t block_id;
        Claim claim;
        std::vector<Hash256> witness_roots;
        std::vector<uint8_t> aggregated_signature;
        std::string policy_version;
        std::string zone_id;
    };
    
protected:
    void StartApplication() override;
    void SubmitClaim(const Claim& claim);
    void HandleDistanceBoundingChallenge(Ptr<Packet> challenge);
    void HandleEvidenceObject(const EvidenceObject& evidence);
    
private:
    Ptr<Crypto> m_crypto;
    Ptr<EnvironmentalSensingModule> m_sensors;
    std::vector<EvidenceObject> m_received_evidence;
};
```

---

## 6. Attack Models

### 6.1 Adversary Capabilities

```cpp
enum class AdversaryCapability {
    NONE,                    // Honest prover
    GPS_SPOOFING,           // Fake GPS coordinates
    DISTANCE_FRAUD,         // Early response in DB
    RELAY_ATTACK,           // Mafia/terrorist fraud
    SENSOR_SPOOFING,        // Fake environmental readings
    SCENE_SPOOFING,         // Display fake visual scene
    WITNESS_COLLUSION,      // Control f < k witnesses
    REPLAY_ATTACK,          // Reuse old valid proofs
    SYBIL_ATTACK            // Multiple fake prover identities
};

class AdversaryModel {
public:
    struct Config {
        std::set<AdversaryCapability> capabilities;
        uint32_t colluding_witnesses = 0;
        double relay_delay = 0.0;          // Additional relay latency (ns)
        double position_offset = 0.0;       // Distance from actual to claimed (m)
        std::string replay_evidence_file;   // Path to replayed evidence
    };
    
    // Attack success tracking
    struct AttackOutcome {
        bool attack_attempted;
        bool attack_succeeded;
        std::string attack_type;
        double adversary_cost;  // Computational/resource cost
    };
};
```

### 6.2 Distance Fraud Attack

```cpp
// Prover tries to appear closer than actual
class DistanceFraudAttacker : public ProverApplication {
public:
    void HandleDistanceBoundingChallenge(Ptr<Packet> challenge) override {
        // Pre-compute response before challenge arrives
        // Send early to reduce apparent RTT
        Time attack_advance = NanoSeconds(m_distance_fraud_ns);
        
        Simulator::Schedule(
            Time(0) - attack_advance,  // Negative = send early
            &DistanceFraudAttacker::SendEarlyResponse,
            this, challenge
        );
    }
    
private:
    double m_distance_fraud_ns = 10.0;  // 10ns = ~1.5m distance reduction
};
```

### 6.3 Relay (Mafia Fraud) Attack

```cpp
// Attack topology: Prover <-> Accomplice <-> Witness
class RelayAttackModel {
public:
    struct RelayConfig {
        Address accomplice_address;
        Vector3D accomplice_position;  // Close to witnesses
        Time relay_latency;            // Added delay
        double relay_probability;      // Success rate
    };
    
    // Model relay path: P -> A -> W -> A -> P
    Time ComputeRelayedRtt(Time legitimate_rtt) {
        return legitimate_rtt + 2 * m_config.relay_latency;
    }
    
    // Relay should fail distance bounding
    bool DetectedByDistanceBounding(double true_distance, double bound) {
        double relayed_distance = true_distance + 
            (2 * m_config.relay_latency.GetSeconds() * SPEED_OF_LIGHT);
        return relayed_distance > bound;
    }
    
private:
    RelayConfig m_config;
};
```

### 6.4 Scene Spoofing Attack

```cpp
// Adversary displays fake content to witnesses
class SceneSpoofingAttackModel {
public:
    enum SpoofingMethod {
        SCREEN_DISPLAY,      // Show image on screen
        PROJECTION,          // Project onto surface
        PHYSICAL_STAGING,    // Arrange physical props
        AUDIO_INJECTION      // Inject fake audio
    };
    
    struct SpoofingConfig {
        SpoofingMethod method;
        double visual_fidelity;     // 0-1: How well spoof matches original
        double audio_fidelity;
        double rf_consistency;      // Can't easily spoof RF environment
        double setup_time;          // Time to prepare spoof
    };
    
    // Probability witness detects spoof
    double GetDetectionProbability(const WitnessApplication* witness) {
        double p_detect = 0.0;
        
        // Multi-witness angular inconsistency
        p_detect += AngularInconsistencyFactor();
        
        // RF fingerprint mismatch (hard to spoof)
        p_detect += (1.0 - m_config.rf_consistency) * 0.3;
        
        // Screen pixel grid detection
        if (m_config.method == SCREEN_DISPLAY) {
            p_detect += 0.2;  // Cameras may detect pixel grid
        }
        
        return std::min(1.0, p_detect);
    }
    
private:
    SpoofingConfig m_config;
};
```

### 6.5 Witness Collusion Attack

```cpp
class WitnessCollusionModel {
public:
    // Byzantine witnesses controlled by adversary
    struct CollusionConfig {
        std::set<uint32_t> colluding_witness_ids;
        bool can_suppress_honest;   // Can interfere with honest attestations
        bool can_forge_signatures;  // Has access to witness keys
    };
    
    // Check if quorum can still be reached honestly
    bool HonestQuorumPossible(uint32_t n, uint32_t k) {
        uint32_t honest = n - m_config.colluding_witness_ids.size();
        return honest >= k;
    }
    
    // Colluding witness always admits
    AdmissionDecision GetColludingDecision() {
        return {.admit = true, .confidence = 1.0, .reason = "Colluding"};
    }
    
private:
    CollusionConfig m_config;
};
```

---

## 7. Metrics and Data Collection

### 7.1 Performance Metrics

```cpp
struct PerformanceMetrics {
    // Latency metrics (per block interval)
    struct LatencyStats {
        Time distance_bounding_latency;
        Time sensing_latency;
        Time reasoning_latency;
        Time signature_latency;
        Time total_latency;
        Time consensus_latency;
    };
    
    // Throughput metrics
    struct ThroughputStats {
        double claims_per_second;
        double successful_attestations_per_second;
        double blocks_per_second;
    };
    
    // Communication overhead
    struct OverheadStats {
        uint64_t db_messages_count;
        uint64_t db_bytes_total;
        uint64_t attestation_messages_count;
        uint64_t attestation_bytes_total;
        uint64_t evidence_object_size_bytes;
    };
    
    // Resource utilization
    struct ResourceStats {
        double cpu_utilization;           // Simulated CPU time
        double memory_usage_bytes;
        double energy_consumption_joules; // If energy model enabled
    };
};
```

### 7.2 Security Metrics

```cpp
struct SecurityMetrics {
    // Attack detection
    struct AttackDetectionStats {
        uint32_t true_positives;   // Attacks correctly rejected
        uint32_t false_positives;  // Honest claims incorrectly rejected
        uint32_t true_negatives;   // Honest claims correctly admitted
        uint32_t false_negatives;  // Attacks incorrectly admitted
        
        double GetPrecision() const { return tp / (tp + fp); }
        double GetRecall() const { return tp / (tp + fn); }
        double GetF1() const { return 2*precision*recall/(precision+recall); }
    };
    
    // Per-attack-type statistics
    std::map<AdversaryCapability, AttackDetectionStats> per_attack_stats;
    
    // Localization accuracy
    struct LocalizationStats {
        double mean_error_meters;
        double std_error_meters;
        double max_error_meters;
        double percentile_90_error;
    };
    
    // Timing integrity
    struct TimingStats {
        Time max_timestamp_deviation;
        Time mean_timestamp_deviation;
        uint32_t replay_attacks_detected;
    };
};
```

### 7.3 NS-3 Trace Collection

```cpp
// Custom trace sources
class WitnessingZoneTracer {
public:
    // Trace sinks
    void ClaimSubmittedTrace(Ptr<const Packet> claim, Address prover);
    void DistanceBoundingCompleteTrace(Address prover, double bound);
    void AdmissionDecisionTrace(Address prover, bool admitted, double confidence);
    void QuorumFormedTrace(Address prover, uint32_t supporting_witnesses);
    void EvidenceObjectCreatedTrace(const EvidenceObject& evidence);
    void AttackAttemptedTrace(AdversaryCapability attack, bool detected);
    
    // Connect to applications
    void ConnectTraces(Ptr<WitnessApplication> witness) {
        witness->TraceConnectWithoutContext(
            "ClaimReceived",
            MakeCallback(&WitnessingZoneTracer::ClaimSubmittedTrace, this)
        );
        // ... more connections
    }
    
    // Output formats
    void EnablePcap(std::string prefix);
    void EnableAscii(std::string prefix);
    void EnableCsv(std::string filename);
    void EnableJson(std::string filename);
};
```

### 7.4 Data Collection Helper

```cpp
// Aggregate statistics across simulation
class SimulationStatsCollector {
public:
    void RecordBlockInterval(const BlockIntervalStats& stats);
    void RecordAttackOutcome(const AttackOutcome& outcome);
    void RecordLocalizationError(double true_distance, double estimated_distance);
    
    // Export methods
    void ExportToCsv(std::string filename);
    void ExportToJson(std::string filename);
    
    // Summary statistics
    PerformanceMetrics GetPerformanceMetrics();
    SecurityMetrics GetSecurityMetrics();
    
    void PrintSummary(std::ostream& os);
};
```

---

## 8. Simulation Scenarios

### 8.1 Scenario 1: Baseline Performance (Supply Chain - Cocoa)

**Objective:** Measure baseline latency, throughput, and overhead for supply chain sealing.

```cpp
struct CocoaScenarioConfig {
    // Zone configuration
    WitnessGeometry geometry = WitnessGeometry::SQUARE;
    uint32_t n_witnesses = 4;
    uint32_t quorum_k = 3;
    double zone_radius = 20.0;  // Container yard
    
    // Prover configuration
    ProverMobility prover_mobility = ProverMobility::STATIC;
    uint32_t n_provers = 1;  // One container at a time
    
    // Protocol configuration
    Time block_interval = MilliSeconds(1000);
    Ptr<AdmissionPolicy> policy = CreateObject<SupplyChainPolicy>();
    
    // Sensing configuration
    std::set<Modality> enabled_sensors = {
        Modality::RF_FINGERPRINT,
        Modality::TEMPERATURE
    };
    
    // No adversary (baseline)
    AdversaryModel::Config adversary = {
        .capabilities = {AdversaryCapability::NONE}
    };
    
    // Simulation parameters
    Time duration = Seconds(300);
    uint32_t n_runs = 30;  // For statistical significance
};
```

**Expected outputs:**
- Mean attestation latency: < 500 ms
- Successful attestation rate: > 99%
- Evidence object size: < 1 KB
- Communication overhead: < 10 KB/attestation

### 8.2 Scenario 2: Attack Resistance (Distance Fraud)

**Objective:** Evaluate detection rate against distance fraud attacks.

```cpp
struct DistanceFraudScenarioConfig {
    // Same base as Cocoa
    // ...
    
    // Adversary configuration
    AdversaryModel::Config adversary = {
        .capabilities = {AdversaryCapability::DISTANCE_FRAUD},
        .position_offset = 10.0  // Prover 10m outside zone
    };
    
    // Vary attack parameters
    std::vector<double> fraud_offsets = {1.0, 2.0, 5.0, 10.0, 20.0};  // meters
    
    // Metrics focus
    // - Detection rate vs. distance offset
    // - False positive rate at various thresholds
};
```

### 8.3 Scenario 3: Scene Spoofing Resistance (Media Profile)

**Objective:** Evaluate multimodal sensing against scene spoofing.

```cpp
struct MediaScenarioConfig {
    // Zone configuration
    WitnessGeometry geometry = WitnessGeometry::PENTAGON;
    uint32_t n_witnesses = 5;
    uint32_t quorum_k = 3;
    double zone_radius = 30.0;  // Public area
    
    // Prover configuration
    ProverMobility prover_mobility = ProverMobility::PEDESTRIAN;
    uint32_t n_provers = 1;
    
    // Protocol configuration
    Ptr<AdmissionPolicy> policy = CreateObject<MediaProvenancePolicy>();
    
    // Full multimodal sensing
    std::set<Modality> enabled_sensors = {
        Modality::RF_FINGERPRINT,
        Modality::AMBIENT_AUDIO,
        Modality::VISUAL_SKETCH
    };
    
    // Scene spoofing adversary
    SceneSpoofingAttackModel::Config spoof_config = {
        .method = SceneSpoofingAttackModel::SCREEN_DISPLAY,
        .visual_fidelity = 0.9,
        .audio_fidelity = 0.8,
        .rf_consistency = 0.3  // Hard to spoof RF
    };
    
    AdversaryModel::Config adversary = {
        .capabilities = {AdversaryCapability::SCENE_SPOOFING}
    };
};
```

### 8.4 Scenario 4: Witness Collusion Tolerance

**Objective:** Verify Byzantine fault tolerance with colluding witnesses.

```cpp
struct CollusionScenarioConfig {
    // Zone configuration
    uint32_t n_witnesses = 7;
    uint32_t quorum_k = 5;  // Tolerate f=2 Byzantine
    
    // Vary number of colluding witnesses
    std::vector<uint32_t> colluding_counts = {0, 1, 2, 3, 4};
    
    // Adversary configuration
    WitnessCollusionModel::Config collusion = {
        .colluding_witness_ids = {0, 1},  // First 2 witnesses
        .can_suppress_honest = false,
        .can_forge_signatures = true  // Worst case
    };
    
    // Metrics focus
    // - Honest attestation success with f colluders
    // - Attack success rate vs. number of colluders
};
```

### 8.5 Scenario 5: Scalability (Mobility Profile)

**Objective:** Measure performance under varying load.

```cpp
struct ScalabilityScenarioConfig {
    // Zone configuration
    WitnessGeometry geometry = WitnessGeometry::HEXAGONAL;
    uint32_t n_witnesses = 6;
    uint32_t quorum_k = 4;
    double zone_radius = 100.0;  // Road intersection
    
    // Prover configuration - multiple vehicles
    ProverMobility prover_mobility = ProverMobility::VEHICULAR;
    std::vector<uint32_t> n_provers = {1, 5, 10, 20, 50};
    double vehicle_speed = 13.9;  // 50 km/h
    
    // Protocol configuration
    Ptr<AdmissionPolicy> policy = CreateObject<MobilityPolicy>();
    std::vector<Time> block_intervals = {
        MilliSeconds(100),
        MilliSeconds(500),
        MilliSeconds(1000)
    };
    
    // Metrics focus
    // - Throughput vs. number of provers
    // - Latency vs. load
    // - Message collision rate
};
```

---

## 9. Implementation Structure

### 9.1 NS-3 Module Directory Structure

```
ns-3.40/
└── contrib/
    └── pol-witnessing-zone/
        ├── model/
        │   ├── pol-channel-model.h/cc           # UWB propagation
        │   ├── distance-bounding-protocol.h/cc  # DB implementation
        │   ├── environmental-sensing.h/cc       # Sensor models
        │   ├── admission-policy.h/cc            # Policy framework
        │   ├── witness-application.h/cc         # Witness node
        │   ├── prover-application.h/cc          # Prover node
        │   ├── evidence-object.h/cc             # Evidence structure
        │   ├── crypto-utils.h/cc                # Signatures, Merkle trees
        │   └── attack-models.h/cc               # Adversary implementations
        ├── helper/
        │   ├── pol-zone-helper.h/cc             # Zone deployment helper
        │   └── pol-stats-helper.h/cc            # Statistics collection
        ├── examples/
        │   ├── pol-cocoa-example.cc             # Supply chain scenario
        │   ├── pol-media-example.cc             # Media provenance scenario
        │   └── pol-mobility-example.cc          # Urban mobility scenario
        ├── test/
        │   ├── pol-distance-bounding-test.cc
        │   ├── pol-admission-policy-test.cc
        │   └── pol-attack-detection-test.cc
        ├── doc/
        │   └── pol-witnessing-zone.rst
        └── wscript                               # Build configuration
```

### 9.2 Build Configuration (wscript)

```python
def build(bld):
    module = bld.create_ns3_module('pol-witnessing-zone', ['core', 'network', 'wifi', 'lr-wpan', 'mobility', 'internet', 'applications', 'propagation'])
    
    module.source = [
        'model/pol-channel-model.cc',
        'model/distance-bounding-protocol.cc',
        'model/environmental-sensing.cc',
        'model/admission-policy.cc',
        'model/witness-application.cc',
        'model/prover-application.cc',
        'model/evidence-object.cc',
        'model/crypto-utils.cc',
        'model/attack-models.cc',
        'helper/pol-zone-helper.cc',
        'helper/pol-stats-helper.cc',
    ]
    
    headers = bld(features='ns3header')
    headers.module = 'pol-witnessing-zone'
    headers.source = [
        'model/pol-channel-model.h',
        'model/distance-bounding-protocol.h',
        'model/environmental-sensing.h',
        'model/admission-policy.h',
        'model/witness-application.h',
        'model/prover-application.h',
        'model/evidence-object.h',
        'model/crypto-utils.h',
        'model/attack-models.h',
        'helper/pol-zone-helper.h',
        'helper/pol-stats-helper.h',
    ]
    
    if bld.env.ENABLE_EXAMPLES:
        bld.recurse('examples')
    
    bld.ns3_python_bindings()
```

### 9.3 Zone Deployment Helper

```cpp
class PolZoneHelper {
public:
    struct ZoneConfig {
        Vector3D center;
        double radius;
        WitnessGeometry geometry;
        uint32_t n_witnesses;
        uint32_t quorum_k;
        Ptr<AdmissionPolicy> policy;
        Time block_interval;
        std::set<Modality> enabled_sensors;
    };
    
    // Create witnessing zone infrastructure
    NodeContainer CreateWitnessNodes(const ZoneConfig& config);
    
    // Configure network stack
    void InstallNetworkStack(NodeContainer witnesses);
    void InstallUwbDevices(NodeContainer witnesses);
    void InstallWifiDevices(NodeContainer witnesses);
    
    // Install applications
    void InstallWitnessApplications(
        NodeContainer witnesses,
        const ZoneConfig& config
    );
    
    // Create prover with optional adversary
    Ptr<Node> CreateProver(
        Vector3D initial_position,
        ProverMobility mobility,
        AdversaryModel::Config adversary = {}
    );
    
    void InstallProverApplication(
        Ptr<Node> prover,
        const ZoneConfig& config
    );
    
    // Enable tracing
    void EnableTracing(std::string prefix);
    
private:
    Ptr<WitnessingZoneTracer> m_tracer;
};
```

---

## 10. Example Simulation Script

### 10.1 Supply Chain (Cocoa) Example

```cpp
// pol-cocoa-example.cc
#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/mobility-module.h"
#include "ns3/wifi-module.h"
#include "ns3/pol-witnessing-zone-module.h"

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("PolCocoaExample");

int main(int argc, char* argv[]) {
    // Parse command line
    CommandLine cmd;
    uint32_t nWitnesses = 4;
    uint32_t quorumK = 3;
    double zoneRadius = 20.0;
    double simTime = 300.0;
    bool verbose = false;
    
    cmd.AddValue("nWitnesses", "Number of witness nodes", nWitnesses);
    cmd.AddValue("quorum", "Quorum threshold k", quorumK);
    cmd.AddValue("radius", "Zone radius (m)", zoneRadius);
    cmd.AddValue("simTime", "Simulation duration (s)", simTime);
    cmd.AddValue("verbose", "Enable verbose logging", verbose);
    cmd.Parse(argc, argv);
    
    if (verbose) {
        LogComponentEnable("PolCocoaExample", LOG_LEVEL_INFO);
        LogComponentEnable("WitnessApplication", LOG_LEVEL_DEBUG);
        LogComponentEnable("DistanceBoundingProtocol", LOG_LEVEL_DEBUG);
    }
    
    // Configure zone
    PolZoneHelper::ZoneConfig zoneConfig;
    zoneConfig.center = Vector3D(0, 0, 0);
    zoneConfig.radius = zoneRadius;
    zoneConfig.geometry = WitnessGeometry::SQUARE;
    zoneConfig.n_witnesses = nWitnesses;
    zoneConfig.quorum_k = quorumK;
    zoneConfig.policy = CreateObject<SupplyChainPolicy>();
    zoneConfig.block_interval = MilliSeconds(1000);
    zoneConfig.enabled_sensors = {
        Modality::RF_FINGERPRINT,
        Modality::TEMPERATURE
    };
    
    // Create zone helper
    PolZoneHelper zoneHelper;
    
    // Create and configure witness nodes
    NodeContainer witnesses = zoneHelper.CreateWitnessNodes(zoneConfig);
    zoneHelper.InstallNetworkStack(witnesses);
    zoneHelper.InstallUwbDevices(witnesses);
    zoneHelper.InstallWifiDevices(witnesses);
    zoneHelper.InstallWitnessApplications(witnesses, zoneConfig);
    
    // Create honest prover at center of zone
    Ptr<Node> prover = zoneHelper.CreateProver(
        Vector3D(5, 5, 1.5),  // Initial position
        ProverMobility::STATIC
    );
    zoneHelper.InstallProverApplication(prover, zoneConfig);
    
    // Schedule periodic claim submissions
    Ptr<ProverApplication> proverApp = 
        prover->GetApplication(0)->GetObject<ProverApplication>();
    
    for (double t = 1.0; t < simTime; t += 2.0) {
        Simulator::Schedule(
            Seconds(t),
            &ProverApplication::SubmitClaim,
            proverApp,
            ProverApplication::Claim{
                .prover_id = prover->GetDevice(0)->GetAddress(),
                .claimed_position = Vector3D(5, 5, 1.5),
                .claimed_time = Simulator::Now()
            }
        );
    }
    
    // Enable statistics collection
    PolStatsHelper statsHelper;
    statsHelper.Install(witnesses);
    statsHelper.Install(prover);
    
    // Enable tracing
    zoneHelper.EnableTracing("pol-cocoa");
    
    // Run simulation
    Simulator::Stop(Seconds(simTime));
    Simulator::Run();
    
    // Print results
    std::cout << "\n=== Simulation Results ===" << std::endl;
    statsHelper.PrintSummary(std::cout);
    statsHelper.ExportToCsv("pol-cocoa-results.csv");
    
    Simulator::Destroy();
    return 0;
}
```

### 10.2 Attack Evaluation Script

```cpp
// pol-attack-evaluation.cc
int main(int argc, char* argv[]) {
    CommandLine cmd;
    std::string attackType = "distance_fraud";
    double attackParam = 5.0;  // Distance offset for fraud
    cmd.AddValue("attack", "Attack type", attackType);
    cmd.AddValue("param", "Attack parameter", attackParam);
    cmd.Parse(argc, argv);
    
    // Configure adversary based on attack type
    AdversaryModel::Config adversaryConfig;
    if (attackType == "distance_fraud") {
        adversaryConfig.capabilities = {AdversaryCapability::DISTANCE_FRAUD};
        adversaryConfig.position_offset = attackParam;
    } else if (attackType == "relay") {
        adversaryConfig.capabilities = {AdversaryCapability::RELAY_ATTACK};
        adversaryConfig.relay_delay = attackParam;  // ns
    } else if (attackType == "scene_spoof") {
        adversaryConfig.capabilities = {AdversaryCapability::SCENE_SPOOFING};
    }
    
    // Create zone (same as before)
    PolZoneHelper zoneHelper;
    // ... configure zone ...
    
    // Create adversarial prover
    Ptr<Node> adversary = zoneHelper.CreateProver(
        Vector3D(zoneConfig.radius + attackParam, 0, 1.5),  // Outside zone
        ProverMobility::STATIC,
        adversaryConfig  // Adversary capabilities
    );
    
    // Run and collect attack metrics
    // ...
    
    SecurityMetrics metrics = statsHelper.GetSecurityMetrics();
    std::cout << "Attack: " << attackType << std::endl;
    std::cout << "Detection Rate: " << metrics.GetRecall() << std::endl;
    std::cout << "False Positive Rate: " 
              << (1.0 - metrics.GetPrecision()) << std::endl;
    
    return 0;
}
```

---

## 11. Analysis and Visualization

### 11.1 Python Analysis Script

```python
#!/usr/bin/env python3
# analyze_pol_results.py

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

def load_results(csv_path: str) -> pd.DataFrame:
    """Load simulation results from CSV."""
    return pd.read_csv(csv_path)

def plot_latency_distribution(df: pd.DataFrame, output_path: str):
    """Plot latency breakdown by protocol phase."""
    fig, axes = plt.subplots(1, 4, figsize=(16, 4))
    
    phases = ['db_latency_ms', 'sensing_latency_ms', 
              'reasoning_latency_ms', 'signature_latency_ms']
    titles = ['Distance Bounding', 'Environmental Sensing',
              'Policy Reasoning', 'Signature Aggregation']
    
    for ax, phase, title in zip(axes, phases, titles):
        sns.histplot(df[phase], ax=ax, kde=True)
        ax.set_title(title)
        ax.set_xlabel('Latency (ms)')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()

def plot_attack_detection(df: pd.DataFrame, output_path: str):
    """Plot attack detection rates vs. attack parameters."""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    for attack_type in df['attack_type'].unique():
        subset = df[df['attack_type'] == attack_type]
        ax.plot(subset['attack_param'], subset['detection_rate'],
                marker='o', label=attack_type)
    
    ax.set_xlabel('Attack Parameter')
    ax.set_ylabel('Detection Rate')
    ax.set_title('Attack Detection vs. Attack Strength')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.savefig(output_path, dpi=150)
    plt.close()

def plot_scalability(df: pd.DataFrame, output_path: str):
    """Plot throughput and latency vs. load."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    
    # Throughput
    ax1.errorbar(df['n_provers'], df['throughput_mean'],
                 yerr=df['throughput_std'], marker='o', capsize=5)
    ax1.set_xlabel('Number of Provers')
    ax1.set_ylabel('Throughput (attestations/s)')
    ax1.set_title('System Throughput')
    ax1.grid(True, alpha=0.3)
    
    # Latency
    ax2.errorbar(df['n_provers'], df['latency_mean'],
                 yerr=df['latency_std'], marker='s', capsize=5)
    ax2.set_xlabel('Number of Provers')
    ax2.set_ylabel('Mean Latency (ms)')
    ax2.set_title('Attestation Latency')
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()

def compute_summary_statistics(df: pd.DataFrame) -> dict:
    """Compute summary statistics for paper."""
    return {
        'mean_latency_ms': df['total_latency_ms'].mean(),
        'std_latency_ms': df['total_latency_ms'].std(),
        'p95_latency_ms': df['total_latency_ms'].quantile(0.95),
        'attestation_success_rate': df['admitted'].mean(),
        'mean_evidence_size_bytes': df['evidence_size_bytes'].mean(),
        'mean_localization_error_m': df['localization_error_m'].mean(),
    }

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('results_dir', type=str)
    parser.add_argument('--output-dir', type=str, default='plots')
    args = parser.parse_args()
    
    results_dir = Path(args.results_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    
    # Load and analyze baseline results
    baseline_df = load_results(results_dir / 'pol-cocoa-results.csv')
    plot_latency_distribution(baseline_df, output_dir / 'latency_dist.png')
    
    # Load and analyze attack results
    attack_df = load_results(results_dir / 'pol-attack-results.csv')
    plot_attack_detection(attack_df, output_dir / 'attack_detection.png')
    
    # Print summary
    stats = compute_summary_statistics(baseline_df)
    print("=== Summary Statistics ===")
    for key, value in stats.items():
        print(f"{key}: {value:.3f}")
```

### 11.2 Batch Experiment Runner

```bash
#!/bin/bash
# run_experiments.sh

NS3_DIR="$HOME/ns-3.40"
OUTPUT_DIR="$HOME/pol-results"
mkdir -p "$OUTPUT_DIR"

# Baseline experiments (vary parameters)
echo "Running baseline experiments..."
for n_witnesses in 4 5 6 7; do
    for quorum in $(seq $((n_witnesses/2 + 1)) $n_witnesses); do
        echo "  n=$n_witnesses, k=$quorum"
        $NS3_DIR/ns3 run "pol-cocoa-example \
            --nWitnesses=$n_witnesses \
            --quorum=$quorum \
            --simTime=300" \
            > "$OUTPUT_DIR/baseline_n${n_witnesses}_k${quorum}.log" 2>&1
        mv pol-cocoa-results.csv "$OUTPUT_DIR/baseline_n${n_witnesses}_k${quorum}.csv"
    done
done

# Attack experiments
echo "Running attack experiments..."
for attack in distance_fraud relay scene_spoof; do
    for param in 1 2 5 10 20; do
        echo "  attack=$attack, param=$param"
        $NS3_DIR/ns3 run "pol-attack-evaluation \
            --attack=$attack \
            --param=$param \
            --simTime=300" \
            > "$OUTPUT_DIR/attack_${attack}_${param}.log" 2>&1
    done
done

# Scalability experiments
echo "Running scalability experiments..."
for n_provers in 1 5 10 20 50; do
    echo "  n_provers=$n_provers"
    $NS3_DIR/ns3 run "pol-mobility-example \
        --nProvers=$n_provers \
        --simTime=300" \
        > "$OUTPUT_DIR/scale_${n_provers}.log" 2>&1
done

echo "Experiments complete. Results in $OUTPUT_DIR"
```

---

## 12. Expected Results and Validation

### 12.1 Baseline Performance (Supply Chain)

| Metric | Expected Value | Acceptance Criteria |
|--------|----------------|---------------------|
| Mean attestation latency | 400-600 ms | < 1000 ms (block interval) |
| Distance bounding phase | 50-100 ms | < 200 ms |
| Sensing phase | 100-200 ms | < 500 ms |
| Reasoning phase | 100-200 ms | < 500 ms |
| Signature phase | 50-100 ms | < 200 ms |
| Attestation success rate | > 99% | > 95% for honest provers |
| Evidence object size | 500-1000 bytes | < 2 KB |
| Localization error (LOS) | 0.1-0.3 m | < 1 m |

### 12.2 Security Metrics

| Attack Type | Detection Rate | False Positive Rate |
|-------------|----------------|---------------------|
| Distance fraud (5m) | > 95% | < 5% |
| Distance fraud (10m) | > 99% | < 5% |
| Relay attack (10ns) | > 90% | < 5% |
| Scene spoofing | > 80% | < 10% |
| Collusion (f=1, n=4) | N/A | System still secure |
| Collusion (f=2, n=4) | N/A | System compromised |

### 12.3 Scalability Metrics

| Provers | Throughput | Mean Latency | Collision Rate |
|---------|------------|--------------|----------------|
| 1 | 1.0 att/s | 400 ms | 0% |
| 5 | 4.5 att/s | 450 ms | < 5% |
| 10 | 8.0 att/s | 550 ms | < 10% |
| 20 | 12.0 att/s | 700 ms | < 15% |
| 50 | 20.0 att/s | 900 ms | < 25% |

---

## 13. Dependencies and Installation

### 13.1 NS-3 Installation

```bash
# Clone NS-3
git clone https://gitlab.com/nsnam/ns-3-dev.git ns-3.40
cd ns-3.40
git checkout ns-3.40

# Build NS-3 with required modules
./ns3 configure --enable-examples --enable-tests \
    --enable-modules=core,network,wifi,lr-wpan,mobility,internet,applications,propagation
./ns3 build
```

### 13.2 PoL Module Installation

```bash
# Copy module to contrib
cp -r pol-witnessing-zone ns-3.40/contrib/

# Rebuild NS-3
cd ns-3.40
./ns3 configure
./ns3 build
```

### 13.3 Python Dependencies

```bash
pip install pandas numpy matplotlib seaborn scipy
```

---

## 14. Limitations and Future Work

### 14.1 Current Limitations

1. **Simplified sensor models:** Environmental sensing uses statistical models rather than realistic signal processing
2. **Idealized cryptography:** Signature and commitment operations use fixed delays rather than actual implementations
3. **No actual ML inference:** Policy reasoning with learned models is simulated with probabilistic decisions
4. **Single-zone topology:** Does not model inter-zone handoffs or hierarchical witnessing

### 14.2 Future Extensions

1. **Realistic UWB ranging:** Integrate IEEE 802.15.4z-compliant ranging models
2. **Hardware-in-the-loop:** Connect to real UWB/BLE transceivers via NS-3 emulation
3. **Multi-zone scenarios:** Model vehicle handoff between adjacent witnessing zones
4. **Privacy-preserving variants:** Add zero-knowledge proof overhead models
5. **Economic incentive layer:** Model staking/rewards for witness participation

---

## 15. References

1. Brito, E. (2025). Decentralized Proof-of-Location for Content Provenance: Towards Capture-Time Authenticity.
2. Brito, E., et al. (2025). A Taxonomy and Methodology for Proof-of-Location Systems. EDOC 2025.
3. Brito, E., et al. (2025). Decentralized Proof-of-Location systems for trust, scalability, and privacy in digital societies. Scientific Reports 15(1).
4. FOAM (2018). FOAM Whitepaper.
5. IEEE 802.15.4z (2020). Enhanced Ultra Wideband (UWB) Physical Layers.

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-01-18 | Claude | Initial specification |

