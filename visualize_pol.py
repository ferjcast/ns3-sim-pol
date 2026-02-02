import matplotlib.pyplot as plt
import numpy as np
import sys
import os

# Add current directory to path just in case
sys.path.append(os.getcwd())

from pol_simulation import (
    ZoneConfig, SupplyChainPolicy, PolSimulation, Vector3, 
    ZoneConfig, SupplyChainPolicy, PolSimulation, Vector3, 
    ObjectType, AttackType
)
import itertools
from shapely.geometry import Point
from shapely.ops import unary_union
from matplotlib.patches import Polygon as MatplotlibPolygon
import matplotlib.patches as mpatches

def run_visualization_scenario():
    print("Setting up simulation scenario...")
    # Config
    # To have a valid 3-witness intersection with 20m sensing range, witnesses must be closer.
    # Placement Radius = 12.0m (Witnesses at ~8.5m from center)
    config_radius = 12.0
    config = ZoneConfig(radius=config_radius, n_witnesses=4, quorum_k=3)
    
    # We use a larger max_distance for policy to allow covering the whole intersection
    policy = SupplyChainPolicy(max_distance=25.0) 
    
    sim = PolSimulation(config, policy)
    sim.create_witnesses()
    
    # Add scene objects - Visual context
    sim.add_scene_object("obj1", ObjectType.CAR, "red", Vector3(5, 5, 0))
    sim.add_scene_object("obj2", ObjectType.TRUCK, "blue", Vector3(-5, 10, 0))
    sim.add_scene_object("obj3", ObjectType.CONTAINER, "orange", Vector3(0, -8, 0))
    
    # Create prover starting outside
    start_pos = Vector3(-25, -22, 1.5)
    prover = sim.create_prover(start_pos)
    
    # Define movement
    def move_process(env, prover):
        # Move from (-25,-22) to (30,33) over 60 seconds (shifted +3 on Y to avoid overlap)
        duration = 60.0
        start = np.array([-25.0, -22.0])
        end = np.array([30.0, 33.0])
        
        while env.now < duration:
            progress = env.now / duration
            curr = start + (end - start) * progress
            # Update prover position
            prover.position.x = float(curr[0])
            prover.position.y = float(curr[1])
            yield env.timeout(0.5) # Update every 0.5s

    sim.env.process(move_process(sim.env, prover))
    
    # Run claims
    sim.run_periodic_claims(prover, interval=1.5, duration=60.0)
    
    # Run
    print("Running simulation...")
    sim.run(60.0)
    print("Simulation complete.")
    
    return sim, prover

def plot_results(sim, prover):
    print("Generating plot...")
    fig, ax = plt.subplots(figsize=(12, 12))
    
    # Plot Zone Definition (Quorum Intersection using Shapely)
    witness_sensing_range = 20.0
    
    # Create circles for each witness
    circles = []
    for w in sim.witnesses:
        p = Point(w.position.x, w.position.y)
        circles.append(p.buffer(witness_sensing_range))
        
        # Plot individual witness circle
        circle_patch = plt.Circle((w.position.x, w.position.y), witness_sensing_range, 
                           fill=False, linestyle=':', color='blue', alpha=0.3)
        ax.add_patch(circle_patch)

    # Calculate k-intersection
    # The zone is the union of all intersections of at least k witnesses
    intersections = []
    k = sim.config.quorum_k
    
    for combo in itertools.combinations(circles, k):
        # Start with the first circle in the combo
        intersection = combo[0]
        for circle in combo[1:]:
            intersection = intersection.intersection(circle)
        
        if not intersection.is_empty:
            intersections.append(intersection)
            
    # The effective zone is the union of all these k-intersections
    effective_zone = unary_union(intersections)
    
    # Plot effective zone
    if not effective_zone.is_empty:
        if effective_zone.geom_type == 'Polygon':
            polys = [effective_zone]
        elif effective_zone.geom_type == 'MultiPolygon':
            polys = effective_zone.geoms
        else:
            polys = []
            
        for poly in polys:
            x, y = poly.exterior.xy
            ax.fill(x, y, color='#2ca02c', alpha=0.2)
            # Add simple border
            ax.plot(x, y, color='#2ca02c', linewidth=1)

    # Add dummy patch for legend
    zone_patch = mpatches.Patch(color='#2ca02c', alpha=0.2, label=f'Effective Zone (k>={sim.config.quorum_k})')
    # Add dummy line for witness sensing range
    witness_range_line = plt.Line2D([0], [0], color='blue', linestyle=':', alpha=0.3, label=f'Sensor Range ({witness_sensing_range}m)')
    
    # Update legend handles later
    extra_handles = [zone_patch, witness_range_line]
    
    # Plot Witnesses
    wx = [w.position.x for w in sim.witnesses]
    wy = [w.position.y for w in sim.witnesses]
    ax.scatter(wx, wy, c='blue', marker='s', s=300, zorder=5, label='Witness Nodes')
    
    # Annotate witnesses
    for i, (x, y) in enumerate(zip(wx, wy)):
        ax.annotate(f"W{i}", (x, y), xytext=(5, 5), textcoords='offset points', fontweight='bold')
    

    # Plot Scene Objects
    ox = [o.position.x for o in sim.sensing.visual_sensor.scene_objects]
    oy = [o.position.y for o in sim.sensing.visual_sensor.scene_objects]
    ax.scatter(ox, oy, c='purple', marker='*', s=400, zorder=4, label='Visual Objects')
    
    # Annotate objects
    for obj in sim.sensing.visual_sensor.scene_objects:
        ax.annotate(f"{obj.color} {obj.obj_type.value}", 
                   (obj.position.x, obj.position.y), 
                   xytext=(5, -15), textcoords='offset points', ha='center', fontsize=12, fontweight='bold')

    # Plot Path/Attestations
    valid_x, valid_y = [], []
    invalid_x, invalid_y = [], []
    
    # Sort attestations by time to draw line
    sorted_attestations = sorted(prover.attestations, key=lambda a: a.timestamp)
    
    # Draw continuous trajectory with color coding (Dense Geometric approach)
    # We simulate the path geometrically to ensure a solid line
    
    # Path definition (Shifted +3 Y to match simulation and avoid clutter)
    start_viz = np.array([-25.0, -22.0])
    end_viz = np.array([30.0, 33.0])
    steps = 200
    
    path_points = []
    for i in range(steps + 1):
        t = i / steps
        pt = start_viz + t * (end_viz - start_viz)
        path_points.append(pt)
        
    # Plot simple path (black dashed)
    path_arr = np.array(path_points)
    ax.plot(path_arr[:,0], path_arr[:,1], color='black', linestyle='--', linewidth=2.0, label='Prover Trajectory', alpha=0.7)
                


    # Add labels and styling
    ax.set_aspect('equal')
    ax.set_xlim(-25, 35)
    ax.set_ylim(-25, 35)
    ax.grid(True, linestyle=':', alpha=0.6)
    
    # Combine standard handles with our custom ones
    handles, labels = ax.get_legend_handles_labels()
    handles.extend(extra_handles)
    ax.legend(handles=handles, loc='upper left', framealpha=0.9, fancybox=True, shadow=True, fontsize=10)
    
    # Title removed for report
    # ax.set_title(...)
    
    ax.set_xlabel("X Position (meters)")
    ax.set_ylabel("Y Position (meters)")
    ax.set_xlim(-17, 17)
    ax.set_ylim(-17, 17)
    plt.savefig('pol_visualization.pdf', bbox_inches='tight')
    plt.savefig('pol_visualization.png', dpi=100, bbox_inches='tight')
    print(f"Saved visualization to pol_visualization.pdf and pol_visualization.png")

if __name__ == "__main__":
    try:
        sim, prover = run_visualization_scenario()
        plot_results(sim, prover)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
