#!/usr/bin/env python3
"""Redraw the baseline analytical map and check it against the supplied source.

This is a ranging-only probability map, not a new sensor or security experiment.
The original artwork and upstream implementation remain unchanged.
"""
import argparse
import hashlib
import importlib.util
import itertools
import json
import math
import os
from pathlib import Path
import platform

os.environ.setdefault('MPLCONFIGDIR', '/tmp/thesis-capture-mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D
from matplotlib.ticker import PercentFormatter
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TEAL, CYAN, SLATE = '#009CA6', '#59DCE1', '#606575'
HALF = 12/math.sqrt(2)
WITNESSES = np.array([[-HALF, -HALF, 3], [HALF, -HALF, 3],
                      [HALF, HALF, 3], [-HALF, HALF, 3]])


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def probabilities(x, y):
    """Return four range-test probabilities for a prover at height 1.5 m."""
    x, y = np.broadcast_arrays(np.asarray(x), np.asarray(y))
    d = np.sqrt((x[..., None]-WITNESSES[:, 0])**2
                +(y[..., None]-WITNESSES[:, 1])**2+1.5**2)
    z = (20-(1.01*d+.1))/(.05*math.sqrt(2))
    erf = np.vectorize(math.erf, otypes=[float])(z)
    return .5*(1+erf)


def quorum_probability(p):
    result = np.prod(p, axis=-1)
    for missing in range(4):
        others = [i for i in range(4) if i != missing]
        result += (1-p[..., missing])*np.prod(p[..., others], axis=-1)
    return np.clip(result, 0, 1)


def enumerate_probability(p):
    total = 0.
    for bits in itertools.product([0, 1], repeat=4):
        if sum(bits) >= 3:
            total += math.prod(value if bit else 1-value for value, bit in zip(p, bits))
    return total


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='Authorised source checkout')
    args = parser.parse_args()
    upstream_path = args.source/'probability_heatmap.py'
    expected = '0a8a680539aff92c0850ec8356c09de4b82b4924e08608cf73a9e4e8d603564e'
    assert sha(upstream_path) == expected, 'Inspect changed upstream model before redrawing'
    spec = importlib.util.spec_from_file_location('upstream_heatmap', upstream_path)
    upstream = importlib.util.module_from_spec(spec); spec.loader.exec_module(upstream)
    np.testing.assert_allclose(upstream.get_witness_positions(12), WITNESSES[:, :2])
    rng = np.random.default_rng(2026102602)
    points = [(0., 0.), (5., 5.), (9.28, 0.), (13., 13.), (15., 15.), (18., 0.), (30., 30.)]
    points += [tuple(p) for p in rng.uniform(-15, 15, (100, 2))]
    for x, y in points:
        p = probabilities(x, y)
        value = float(quorum_probability(p))
        np.testing.assert_allclose(value, enumerate_probability(p), rtol=1e-12, atol=1e-13)
        distances = upstream.distance_to_witnesses(x, y, WITNESSES[:, :2])
        reference = upstream.prob_quorum_admit(np.array([upstream.prob_accept_single(d) for d in distances]), 3)
        np.testing.assert_allclose(value, reference, rtol=1e-12, atol=1e-13)
    coords = np.linspace(-15, 15, 1201)
    xgrid, ygrid = np.meshgrid(coords, coords)
    grid = quorum_probability(probabilities(xgrid, ygrid))
    assert np.all(np.isfinite(grid)) and np.all((grid >= 0) & (grid <= 1))
    np.testing.assert_allclose(grid, grid.T, rtol=0, atol=2e-13)
    np.testing.assert_allclose(grid, grid[::-1, ::-1], rtol=0, atol=2e-13)
    (HERE/'results').mkdir(exist_ok=True)
    data_path = HERE/'results/capture-proximity-grid.npz'
    zoom_x = np.linspace(9.0, 9.6, 401)
    zoom_y = np.linspace(-.22, .22, 301)
    zx, zy = np.meshgrid(zoom_x, zoom_y)
    zoom_grid = quorum_probability(probabilities(zx, zy))
    assert np.all(np.isfinite(zoom_grid)) and np.all((zoom_grid >= 0) & (zoom_grid <= 1))
    np.testing.assert_allclose(zoom_grid, zoom_grid[::-1, :], rtol=0, atol=2e-13)
    np.savez_compressed(data_path, x=coords, y=coords, probability=grid,
                        zoom_x=zoom_x, zoom_y=zoom_y, zoom_probability=zoom_grid)

    plt.rcParams.update({
        'font.family': 'serif', 'font.serif': ['Liberation Serif', 'DejaVu Serif'],
        'font.size': 11, 'mathtext.fontset': 'stix', 'pdf.fonttype': 42,
        'axes.edgecolor': SLATE, 'axes.labelcolor': '#282B32',
        'xtick.color': SLATE, 'ytick.color': SLATE, 'axes.linewidth': .7,
    })
    fig = plt.figure(figsize=(6.8, 4.8))
    ax = fig.add_axes([.08, .14, .55, .81])
    cmap = LinearSegmentedColormap.from_list('thesis_proximity',
        ['#F4F8F8', '#C8EFEF', CYAN, TEAL, '#00565B'])
    dx = coords[1]-coords[0]
    image = ax.imshow(grid, origin='lower',
        extent=(coords[0]-dx/2, coords[-1]+dx/2, coords[0]-dx/2, coords[-1]+dx/2),
        interpolation='nearest', cmap=cmap, vmin=0, vmax=1, rasterized=True)
    levels = [.1, .5, .9]
    styles = ['dotted', 'solid', 'dashed']
    # Emphasise one explicitly identified probability contour on the overview.
    # The other levels are separated in an external detail panel.
    outline = ax.contour(coords, coords, grid, levels=[.5], colors=['#30343E'], linewidths=1.45)
    outline.set_path_effects([pe.Stroke(linewidth=3.2, foreground='white'), pe.Normal()])
    ax.scatter(WITNESSES[:, 0], WITNESSES[:, 1], marker='^', s=50,
               color=SLATE, edgecolors='white', linewidths=.85, zorder=5)
    for i, (x, y, _) in enumerate(WITNESSES):
        ax.annotate(f'$W_{i}$', (x, y), xytext=(-5, 5) if i == 0 else (5, 5),
                    ha='right' if i == 0 else 'left', textcoords='offset points',
                    color='white', fontsize=11.5, weight='bold', zorder=6)
    ax.scatter([5], [5], marker='o', s=33, facecolors='white', edgecolors=SLATE, linewidths=1.1, zorder=7)
    ax.annotate('Interior\n(5, 5)', (5, 5), xytext=(9, -4), textcoords='offset points',
                ha='left', va='center', color='white', fontsize=10, zorder=8)
    ax.scatter([9.28], [0], marker='D', s=30, facecolors='white', edgecolors=SLATE, linewidths=1.1, zorder=7)
    boundary_probability = float(quorum_probability(probabilities(9.28, 0)))
    ax.annotate(f'Near edge\n(9.28, 0)\n{100*boundary_probability:.1f}%', (9.28, 0), xytext=(-9, -7), textcoords='offset points',
                ha='right', va='top', fontsize=9.5, color='white',
                arrowprops=dict(arrowstyle='-', lw=.7, color='white'), zorder=8)
    ax.set(xlim=(-15, 15), ylim=(-15, 15), xlabel='$x$ (m)', ylabel='$y$ (m)')
    ax.set_xticks(np.arange(-15, 16, 5)); ax.set_yticks(np.arange(-15, 16, 5))
    ax.tick_params(length=3, width=.7, labelsize=10)
    ax.set_aspect('equal')
    ax.set_title('Zone overview', fontsize=11, pad=6, color='#282B32')
    color_axis = fig.add_axes([.74, .16, .235, .035])
    bar = fig.colorbar(image, cax=color_axis, orientation='horizontal')
    bar.set_ticks([0, .5, 1])
    bar.ax.xaxis.set_major_formatter(PercentFormatter(xmax=1, decimals=0))
    bar.ax.tick_params(labelsize=9.5, length=2)
    bar.set_label('Proximity admission', labelpad=4, fontsize=10)
    bar.outline.set_edgecolor(SLATE); bar.outline.set_linewidth(.6)
    zoom = fig.add_axes([.74, .60, .24, .26])
    zdx, zdy = zoom_x[1]-zoom_x[0], zoom_y[1]-zoom_y[0]
    zoom.imshow(zoom_grid, origin='lower', extent=(zoom_x[0]-zdx/2, zoom_x[-1]+zdx/2,
                                               zoom_y[0]-zdy/2, zoom_y[-1]+zdy/2),
                interpolation='nearest', cmap=cmap, vmin=0, vmax=1, aspect='auto', rasterized=True)
    detail = zoom.contour(zoom_x, zoom_y, zoom_grid, levels=levels, colors=['#30343E']*3,
                          linestyles=styles, linewidths=[.85, 1.25, .85])
    detail.set_path_effects([pe.Stroke(linewidth=2.15, foreground='white'), pe.Normal()])
    zoom.scatter([9.28], [0], marker='D', s=18, facecolors='white', edgecolors=SLATE, linewidths=.8, zorder=12)
    zoom.set(xlim=(9.0, 9.6), ylim=(-.22, .22))
    zoom.set_xticks([9.0, 9.3, 9.6]); zoom.set_yticks([-.2, 0, .2])
    zoom.tick_params(labelsize=9.5, length=2, pad=2)
    zoom.set_xlabel('$x$ (m)', fontsize=10, labelpad=2)
    zoom.set_ylabel('$y$ (m)', fontsize=10, labelpad=2)
    zoom.set_title('Edge detail', fontsize=11, pad=5, color='#282B32')
    for spine in zoom.spines.values():
        spine.set_edgecolor(SLATE); spine.set_linewidth(.85)
    handles = [Line2D([0], [0], color='#30343E', lw=1.45 if level == .5 else .85, ls=style, label=f'{100*level:.0f}%')
               for level, style in zip(levels, styles)]
    fig.legend(handles=handles, title='Probability contours', ncol=1, loc='upper left',
               bbox_to_anchor=(.725, .47), frameon=False, fontsize=9.5, title_fontsize=9.5,
               handlelength=2.8, borderaxespad=0)
    output = ROOT/'assets/figures/capture-proximity-map.pdf'
    fig.savefig(output, bbox_inches='tight', pad_inches=.035, dpi=300)
    plt.close(fig)
    record = {
        'purpose': 'Analytical ranging-only replacement for Figure 22; no RF or visual gates.',
        'model': {'placement_radius_m': 12, 'witnesses': WITNESSES.tolist(), 'prover_height_m': 1.5,
                  'quorum': 3, 'range_limit_m': 20, 'range_mean': '1.01*d + 0.10 metres', 'range_sd_m': .05},
        'grid': {'points_per_axis': len(coords), 'extent_m': [-15, 15], 'step_m': float(dx)},
        'edge_detail': {'x_extent_m': [9.0, 9.6], 'y_extent_m': [-.22, .22],
                        'grid_shape': list(zoom_grid.shape),
                        'layout': 'Separate smaller side panel outside the overview; no map overlay.',
                        'overview_outline': '50% contour with a contrasting white halo',
                        'detail_contours': ['10%', '50%', '90%']},
        'checks': {'source_and_independent_enumeration_points': len(points), 'bounded_finite_grid': True,
                   'diagonal_and_central_symmetry': True, 'bounded_symmetric_edge_detail': True},
        'point_probabilities': {f'({x:g},{y:g})': float(quorum_probability(probabilities(x, y))) for x, y in points[:7]},
        'contours': [{'probability': level, 'label': f'{100*level:.0f}%'} for level in levels],
        'fraud_annotation': 'None; fraud scenarios are described in the text.',
        'palette': {'teal': TEAL, 'cyan': CYAN, 'slate': SLATE},
        'source_model_sha256': sha(upstream_path), 'script_sha256': sha(Path(__file__)),
        'grid_sha256': sha(data_path), 'figure_sha256': sha(output),
        'python': platform.python_version(), 'numpy': np.__version__, 'matplotlib': matplotlib.__version__,
    }
    (HERE/'results/proximity-map-checks.json').write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps({'checks': record['checks'], 'point_probabilities': record['point_probabilities']}, indent=2))


if __name__ == '__main__':
    main()
