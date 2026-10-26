#!/usr/bin/env python3
"""
Analytical Probability Heatmap for PoL Witnessing Zone

This script computes the admission probability at each point in the zone
using the analytical noise model, without running Monte Carlo simulations.

Model:
  Measured Distance = True Distance × 1.01 + 0.1 + N(0, 0.05)
  
Admission requires k>=3 witnesses to measure distance <= 20m.
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.patches import Circle
import math
from itertools import combinations

# Configuration
PLACEMENT_RADIUS = 12.0  # Witness placement radius
MAX_DISTANCE = 20.0      # Policy threshold
QUORUM_K = 3             # Required votes
N_WITNESSES = 4

# Noise model parameters
BIAS_MULTIPLIER = 1.01
BIAS_OFFSET = 0.1
NOISE_STD = 0.05


def get_witness_positions(placement_radius: float) -> np.ndarray:
    """Get witness positions in square geometry."""
    half = placement_radius / np.sqrt(2)
    return np.array([
        [-half, -half],  # W0
        [half, -half],   # W1
        [half, half],    # W2
        [-half, half],   # W3
    ])


def distance_to_witnesses(x: float, y: float, witnesses: np.ndarray) -> np.ndarray:
    """Compute distance from point (x, y) to each witness."""
    # Add z-height difference (prover at 1.5m, witnesses at 0m)
    z_diff = 1.5
    distances = np.sqrt((witnesses[:, 0] - x)**2 + (witnesses[:, 1] - y)**2 + z_diff**2)
    return distances


def normal_cdf(x: float, mu: float, sigma: float) -> float:
    """Normal CDF using math.erf (no scipy needed)."""
    z = (x - mu) / (sigma * math.sqrt(2))
    return 0.5 * (1 + math.erf(z))


def prob_accept_single(true_distance: float) -> float:
    """
    Probability that a single witness accepts given true distance.
    
    P(Measured <= MAX_DISTANCE) where Measured ~ N(mu, sigma)
    mu = true_distance * 1.01 + 0.1
    sigma = 0.05
    """
    mu = true_distance * BIAS_MULTIPLIER + BIAS_OFFSET
    sigma = NOISE_STD
    # P(X <= threshold) = CDF(threshold)
    return normal_cdf(MAX_DISTANCE, mu, sigma)


def prob_quorum_admit(accept_probs: np.ndarray, k: int) -> float:
    """
    Probability that at least k witnesses accept.
    
    Uses exact combinatorial calculation for heterogeneous Bernoulli trials.
    """
    n = len(accept_probs)
    total_prob = 0.0
    
    # Sum over all subsets of size >= k
    for num_accept in range(k, n + 1):
        # Sum over all combinations of num_accept witnesses accepting
        for accepting_indices in combinations(range(n), num_accept):
            prob = 1.0
            for i in range(n):
                if i in accepting_indices:
                    prob *= accept_probs[i]
                else:
                    prob *= (1 - accept_probs[i])
            total_prob += prob
    
    return total_prob


def compute_probability_grid(grid_size: int = 200, extent: float = 15.0):
    """Compute admission probability for a grid of points."""
    witnesses = get_witness_positions(PLACEMENT_RADIUS)
    
    x = np.linspace(-extent, extent, grid_size)
    y = np.linspace(-extent, extent, grid_size)
    X, Y = np.meshgrid(x, y)
    
    prob_grid = np.zeros_like(X)
    
    for i in range(grid_size):
        for j in range(grid_size):
            distances = distance_to_witnesses(X[i, j], Y[i, j], witnesses)
            accept_probs = np.array([prob_accept_single(d) for d in distances])
            prob_grid[i, j] = prob_quorum_admit(accept_probs, QUORUM_K)
    
    return X, Y, prob_grid, witnesses


def plot_heatmap(X, Y, prob_grid, witnesses, output_file: str = "probability_heatmap.png"):
    """Generate the probability heatmap visualization."""
    fig, ax = plt.subplots(figsize=(10, 10))
    
    # Plot heatmap
    cmap = plt.cm.RdYlGn  # Red (0%) -> Yellow (50%) -> Green (100%)
    im = ax.pcolormesh(X, Y, prob_grid, cmap=cmap, shading='auto', vmin=0, vmax=1)
    
    # Add colorbar
    cbar = plt.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label('Admission Probability', fontsize=15)
    cbar.ax.tick_params(labelsize=13)
    
    # Plot witness positions
    ax.scatter(witnesses[:, 0], witnesses[:, 1], c='blue', s=150, marker='^', 
               edgecolors='white', linewidths=2, zorder=5, label='Witnesses')
    
    # Label witnesses
    for i, (wx, wy) in enumerate(witnesses):
        ax.annotate(f'W{i}', (wx, wy), xytext=(5, 5), textcoords='offset points',
                    fontsize=13, fontweight='bold', color='white')
    
    # Draw 20m range circles around each witness (faintly)
    for i, (wx, wy) in enumerate(witnesses):
        label = 'Sensor Range (20m)' if i == 0 else None  # Only label once
        circle = Circle((wx, wy), MAX_DISTANCE, fill=False, color='blue', 
                        linestyle='--', alpha=0.3, linewidth=1, label=label)
        ax.add_patch(circle)
    
    # Mark key positions
    # Baseline position (honest prover inside zone)
    ax.plot(5, 5, '*', color='lime', markersize=18, markeredgecolor='black', 
            markeredgewidth=1.5, zorder=6)
    ax.annotate('Baseline\n(5, 5)', (5, 5), xytext=(10, 15), 
                textcoords='offset points', fontsize=13, fontweight='bold',
                color='black', ha='left',
                path_effects=[pe.withStroke(linewidth=2, foreground='white')])
    
    # Edge Case position
    ax.plot(9.28, 0, 'o', color='orange', markersize=12, markeredgecolor='black', 
            markeredgewidth=2, zorder=6)
    ax.annotate('Edge Case\n(9.28, 0)', (9.28, 0), xytext=(15, 20), 
                textcoords='offset points', fontsize=13, fontweight='bold',
                color='black', ha='left',
                path_effects=[pe.withStroke(linewidth=2, foreground='white')])
    
    # Distance Fraud position (attacker at 30, 30 — outside plot)
    # Show an indicator at the corner of the plot pointing toward (30,30)
    ax.plot(13, 13, 'X', color='red', markersize=14, markeredgecolor='white', 
            markeredgewidth=1.5, zorder=6)
    ax.annotate('Distance Fraud\n(13, 13)', (13, 13), xytext=(-15, -10), 
                textcoords='offset points', fontsize=13, fontweight='bold',
                color='black', ha='right',
                arrowprops=dict(arrowstyle='->', color='black', lw=2),
                path_effects=[pe.withStroke(linewidth=2, foreground='white')])
    
    # Contour lines for 10%, 50%, 90% probability
    contour_levels = [0.1, 0.5, 0.9]
    CS = ax.contour(X, Y, prob_grid, levels=contour_levels, colors=['red', 'orange', 'green'],
                    linewidths=2, linestyles=['--', '-', '--'])
    ax.clabel(CS, inline=True, fontsize=13, fmt='%.0f%%', 
              manual=[(8, 0), (9, 0), (10, 0)])
    
    # Axis settings
    ax.set_xlim(-15, 15)
    ax.set_ylim(-15, 15)
    ax.set_xlabel('X Position (m)', fontsize=15)
    ax.set_ylabel('Y Position (m)', fontsize=15)
    ax.tick_params(axis='both', labelsize=13)
    # ax.set_title('PoL Admission Probability Heatmap\n(Analytical Model: k≥3/4 witnesses within 20m)', 
    #              fontsize=14, fontweight='bold')
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)
    ax.legend(loc='upper left', fontsize=13)
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.savefig(output_file.replace('.png', '.pdf'), bbox_inches='tight')
    print(f"Saved heatmap to {output_file} and {output_file.replace('.png', '.pdf')}")
    
    return fig, ax


def main():
    print("Computing analytical probability heatmap...")
    print(f"Configuration: {N_WITNESSES} witnesses, Quorum k={QUORUM_K}, Max Distance={MAX_DISTANCE}m")
    print(f"Noise Model: Measured = {BIAS_MULTIPLIER}×D + {BIAS_OFFSET} + N(0, {NOISE_STD})")
    print()
    
    X, Y, prob_grid, witnesses = compute_probability_grid(grid_size=200, extent=15.0)
    
    # Print some statistics
    print(f"Probability at center (0,0): {prob_grid[100, 100]:.4f}")
    print(f"Probability at edge case (9.28, 0): {prob_grid[100, int(100 + 9.28 * 200/30)]:.4f}")
    print()
    
    plot_heatmap(X, Y, prob_grid, witnesses)
    print("Done!")


if __name__ == "__main__":
    main()
