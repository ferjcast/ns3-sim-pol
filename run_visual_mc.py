from pol_simulation import *
import numpy as np

def run_visual_mc(iterations=100):
    print(f"Running {iterations} MC iterations for Visual Policy...")
    
    # Storage for results
    valid_results = []
    invalid_results = []
    
    # 1. Valid Context (Red Car Present)
    print("Simulating Scenario: Visual (Red Car Present)...")
    for _ in range(iterations):
        config = ZoneConfig(n_witnesses=4, quorum_k=3, radius=20.0)
        policy = VisualVerificationPolicy(
            max_distance=40.0,
            rf_threshold=0.5,
            required_queries=["is there a red car?"],
            require_all_true=True
        )
        sim = PolSimulation(config, policy)
        sim.add_scene_object("car1", ObjectType.CAR, "red", Vector3(5, 5, 0), size=4.0)
        sim.add_scene_object("truck1", ObjectType.TRUCK, "blue", Vector3(-5, 10, 0), size=6.0)
        sim.create_witnesses()
        sim.set_visual_queries(["is there a red car?"])
        prover = sim.create_prover(Vector3(5, 5, 1.5))
        sim.run_periodic_claims(prover, interval=2.0, duration=60.0)
        sim.run(60.0)
        valid_results.append(sim.get_results()['performance']['success_rate'])

    # 2. Invalid Context (Red Car Missing)
    print("Simulating Scenario: Visual (No Red Car)...")
    for _ in range(iterations):
        config = ZoneConfig(n_witnesses=4, quorum_k=3, radius=20.0)
        policy = VisualVerificationPolicy(
            max_distance=40.0,
            rf_threshold=0.5,
            required_queries=["is there a red car?"],
            require_all_true=True
        )
        sim = PolSimulation(config, policy)
        # ONLY BLUE TRUCK
        sim.add_scene_object("truck1", ObjectType.TRUCK, "blue", Vector3(-5, 10, 0), size=6.0)
        sim.create_witnesses()
        sim.set_visual_queries(["is there a red car?"])
        prover = sim.create_prover(Vector3(5, 5, 1.5))
        sim.run_periodic_claims(prover, interval=2.0, duration=60.0)
        sim.run(60.0)
        invalid_results.append(sim.get_results()['performance']['success_rate'])

    # Stats
    v_mean = np.mean(valid_results)
    v_std = np.std(valid_results)
    
    i_mean = np.mean(invalid_results)
    i_std = np.std(invalid_results)
    
    print("-" * 50)
    print(f"Visual (Valid):   Mean={v_mean:.3f}, Std={v_std:.3f}")
    print(f"Visual (Invalid): Mean={i_mean:.3f}, Std={i_std:.3f}")
    print("-" * 50)

if __name__ == "__main__":
    run_visual_mc()
