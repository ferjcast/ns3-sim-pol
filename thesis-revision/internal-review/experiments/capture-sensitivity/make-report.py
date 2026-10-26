#!/usr/bin/env python3
"""Inspect all recorded results and generate a separate LaTeX study report."""
import csv
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import importlib.util
import json
import math
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
DATA = HERE/'results'
PLOTS = HERE/'plot-data'
RULES = ['single_preselected', '1_of_4', '2_of_4', '3_of_4', '4_of_4']
LABELS = ['One preselected', 'Any one of four', '2 of 4', '3 of 4', '4 of 4']
COLOURS = ['researchgrey', 'researchcyan!70!black', 'researchgrey!65!black', 'researchteal', 'researchteal!55!black']
MARKERS = ['o', 'triangle*', 'diamond*', '*', 'square*']
rows = list(csv.DictReader((DATA/'results.csv').open()))
manifest = json.loads((DATA/'manifest.json').read_text())
checks = json.loads((DATA/'checks.json').read_text())


def matches(row, filters):
    for key, value in filters.items():
        if isinstance(value, bool):
            if row[key] != str(value):
                return False
        elif isinstance(value, (int, float)):
            if not math.isclose(float(row[key]), value, rel_tol=1e-10, abs_tol=1e-10):
                return False
        elif row[key] != value:
            return False
    return True


def one(**filters):
    found = [row for row in rows if matches(row, filters)]
    assert len(found) == 1, (filters, len(found))
    return found[0]


def reference(truth, rule, correlation=0):
    return one(block='errors', stage='range_rf_visual', truth_present=truth, rule=rule,
               fp=.1, fn=.1, error_common=correlation)


def percent(row, field='admit_rate', digits=2):
    value = (Decimal(row['admitted'])*100/Decimal(row['trials']) if field == 'admit_rate'
             else Decimal(row[field])*100)
    return str(value.quantize(Decimal(10)**-digits, rounding=ROUND_HALF_UP))


def interval(row, digits=2):
    return f"{percent(row, digits=digits)} [{percent(row, 'ci95_low', digits)}, {percent(row, 'ci95_high', digits)}]"


def write_plot(name, values):
    with (PLOTS/name).open('w') as f:
        out = csv.DictWriter(f, fieldnames=['x', 'rate', 'low', 'high'])
        out.writeheader()
        for x, row, metric in values:
            rate = float(row[metric]) if metric == 'admit_rate' else int(row[metric])/int(row['trials'])
            low = rate-float(row['ci95_low']) if metric == 'admit_rate' else 0
            high = float(row['ci95_high'])-rate if metric == 'admit_rate' else 0
            out.writerow(dict(x=x*100 if name.startswith('availability') else x,
                              rate=100*rate, low=100*max(0, low), high=100*max(0, high)))


def plot(axis, series):
    out = [r'\begin{center}\begin{tikzpicture}', r'\begin{axis}['+axis+']']
    for index, (filename, label, colour, dashed, intervals) in enumerate(series):
        error = ',error bars/.cd,y dir=both,y explicit' if intervals else ''
        marker = MARKERS[index % len(MARKERS)]
        fill = 'white' if marker == 'o' else colour
        style = (f'color={colour},thick,mark={marker},mark size=1.8pt,'
                 f'mark options={{solid,draw={colour},fill={fill}}}'+(',dashed' if dashed else '')+error)
        fields = 'x=x,y=rate'+(',y error minus=low,y error plus=high' if intervals else '')
        out += [f'\\addplot[{style}] table[col sep=comma,{fields}] {{plot-data/{filename}}};',
                '\\addlegendentry{'+label+'}']
    out += [r'\end{axis}\end{tikzpicture}\end{center}']
    return '\n'.join(out)


def main():
    PLOTS.mkdir(exist_ok=True)
    assert len(rows) == 3620
    analytical = [r for r in rows if r['analytical_expected']]
    max_z = 0
    for r in analytical:
        p = float(r['analytical_expected']); n = int(r['trials'])
        rate = float(r['admit_rate'])
        if p in (0, 1):
            assert rate == p
        else:
            max_z = max(max_z, abs(rate-p)/math.sqrt(p*(1-p)/n))
    # Independently inspect the achieved marginal probabilities and correlations.
    spec = importlib.util.spec_from_file_location('sensitivity', HERE/'run-study.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    bank = module.vectors(manifest['trials_per_condition'], manifest['design']['seed'])
    for name, value in bank.items():
        assert hashlib.sha256(value.tobytes()).hexdigest() == manifest['input_sha256'][name]
    correlations = []
    for c in [0, .25, .5, .75, 1]:
        errors = np.where(bank['error_mode_u'] < c, bank['error_shared_u'], bank['error_local_u']) < .1
        empirical = float(np.corrcoef(errors.astype(float), rowvar=False)[np.triu_indices(4, 1)].mean())
        assert abs(empirical-c) < .02
        assert np.max(np.abs(errors.mean(axis=0)-.1)) < .01
        correlations.append(dict(target=c, achieved_pairwise_mean=empirical,
                                 witness_error_rates=errors.mean(axis=0).tolist()))

    independent_table = []
    for rule, label in zip(RULES, LABELS):
        valid, invalid = reference(True, rule), reference(False, rule)
        independent_table.append(f'{label} & {interval(valid)} & {interval(invalid, 3)} \\\\')

    error_plots = []
    for truth in [False, True]:
        series = []
        for rule, label, colour in zip(RULES, LABELS, COLOURS):
            filename = f'correlation-{truth}-{rule}.csv'
            write_plot(filename, [(c, reference(truth, rule, c), 'admit_rate') for c in [0, .25, .5, .75, 1]])
            series.append((filename, label, colour, False, True))
        axis = r'xlabel={Shared recognition-error fraction $c$},xmin=0,xmax=1,'
        axis += (r'ylabel={Invalid-context admission (\%)},ymode=log,ymin=0.003,ymax=60,ytick={0.01,0.1,1,10},yticklabels={0.01,0.1,1,10}' if not truth
                 else r'ylabel={Valid-context admission (\%)},ymin=60,ymax=101')
        error_plots.append(plot(axis, series))

    availability_plots = []
    for metric in ['admit_rate', 'inconclusive']:
        series = []
        for cm, label, colour in [(0, 'Independent missingness', 'researchteal'),
                                  (1, 'Shared missingness', 'researchgrey')]:
            filename = f'availability-{metric}-{cm}.csv'
            values = [(missing, one(block='availability', stage='range_rf_visual', truth_present=True,
                                    rule='3_of_4', missing=missing, missing_common=cm, error_common=0), metric)
                      for missing in [0, .1, .25, .5]]
            write_plot(filename, values)
            series.append((filename, label, colour, cm == 1, metric == 'admit_rate'))
        axis = r'xlabel={Missing observations per witness (\%)},xmin=0,xmax=50,ymin=0,ymax=100,'
        axis += (r'ylabel={Valid-context admission (\%)}' if metric == 'admit_rate' else r'ylabel={Inconclusive (\%)}')
        availability_plots.append(plot(axis, series))

    dishonest_table = []
    for f in [0, 1, 2]:
        values = [one(block='dishonest', stage='range_rf_visual', truth_present=False, rule='3_of_4',
                      dishonest=f, error_common=c) for c in [0, .5, 1]]
        dishonest_table.append(str(f)+' & '+' & '.join(percent(r) for r in values)+r' \\')

    boundary_plots = []
    for error in [0, .1]:
        series = []
        for sigma, colour in [(.05, 'researchgrey'), (.5, 'researchteal'), (1, 'researchcyan!70!black')]:
            filename = f'boundary-{error}-{sigma}.csv'
            values = [(off, one(block='boundary', stage='range_rf_visual', truth_present=True,
                                 rule='3_of_4', boundary_offset=off, range_sd=sigma, fn=error), 'admit_rate')
                      for off in [-2, -1, -.5, -.25, -.1, 0, .1, .25, .5, 1, 2]]
            write_plot(filename, values)
            series.append((filename, f'Range SD {sigma:g} m', colour, False, True))
        boundary_plots.append(plot(
            r'xlabel={Position relative to biased third-witness boundary (m)},ylabel={Truthful-context admission (\%)},'
            r'xmin=-2,xmax=2,ymin=0,ymax=101,title={Recognition error probability '+str(error)+'}', series))

    visibility_table = []
    for xy in manifest['design']['visibility_sweep']['positions_xy']:
        values = [one(block='visibility', stage='range_rf_visual', truth_present=True, rule='3_of_4',
                      x=xy[0], y=xy[1], fov=fov, visual_range=vr)
                  for vr in [20, 50] for fov in [60, 120, 360]]
        visibility_table.append(f"({xy[0]}, {xy[1]}) & "+' & '.join(r['visible_witnesses'] for r in values)+r' \\')

    ref3, bad3 = reference(True, '3_of_4'), reference(False, '3_of_4')
    common3 = reference(False, '3_of_4', 1)
    availability = one(block='availability', stage='range_rf_visual', truth_present=True, rule='3_of_4',
                       missing=.1, missing_common=0, error_common=0)
    visibility = one(block='visibility', stage='range_rf_visual', truth_present=True, rule='3_of_4',
                     x=20, y=5, fov=120, visual_range=50)
    baseline = one(block='errors', stage='range_rf', truth_present=False, rule='3_of_4')
    audit = dict(max_analytical_deviation_standard_errors=max_z, observed_correlations=correlations,
                 reference_valid=ref3, reference_invalid=bad3, shared_error_invalid=common3,
                 missing_observations_valid=availability, limited_fov_example=visibility,
                 geometric_rf_baseline_invalid=baseline)
    verification = json.loads((DATA/'verification.json').read_text())
    assert verification['exact_repeat_match'] and verification['thesis_unchanged']
    for name, digest in verification['verified_output_sha256'].items():
        assert hashlib.sha256((DATA/name).read_bytes()).hexdigest() == digest
    guard_path = HERE/'thesis-guard.json'
    assert hashlib.sha256(guard_path.read_bytes()).hexdigest() == verification['guard_sha256']
    integration_path = HERE/'integration.json'
    integration = json.loads(integration_path.read_text()) if integration_path.exists() else {}
    if not integration.get('integration_authorized', False):
        for name, digest in json.loads(guard_path.read_text()).items():
            assert hashlib.sha256((HERE.parents[2]/name).read_bytes()).hexdigest() == digest
    audit['verification'] = verification
    profile = manifest['design']['profile']
    a = profile['placement_radius_m']/math.sqrt(2)
    y = manifest['design']['boundary_sweep']['path_y_m']
    nominal_boundary = math.sqrt(profile['range_limit_m']**2-(y-a)**2
                                 -(profile['witness_height_m']-profile['prover_height_m'])**2)-a
    audit['unbiased_geometric_boundary_offset_m'] = nominal_boundary-manifest['third_witness_boundary_x_m']
    (DATA/'inspection.json').write_text(json.dumps(audit, indent=2)+'\n')

    status = ('Selected results are included in thesis Section 6.4.4; this report retains the complete study.'
              if integration.get('status') == 'included_in_thesis' else
              'These results were assessed separately before manuscript integration.')
    tex = r'''\documentclass[11pt,a4paper]{article}
\usepackage[margin=22mm]{geometry}
\usepackage[T1]{fontenc}
\usepackage{newtxtext,newtxmath}
\usepackage{booktabs,pgfplots,hyperref,xurl}
\definecolor{researchteal}{HTML}{009CA6}
\definecolor{researchcyan}{HTML}{59DCE1}
\definecolor{researchgrey}{HTML}{606575}
\pgfplotsset{compat=1.18,every axis/.append style={width=.93\linewidth,height=6.1cm,
  grid=major,major grid style={gray!15},tick label style={font=\small},label style={font=\small},
  legend style={font=\scriptsize,draw=none,at={(0.5,1.04)},anchor=south,legend columns=3}}}
\hypersetup{colorlinks=true,urlcolor=teal!70!black}
\setlength{\parindent}{0pt}\setlength{\parskip}{5pt}
\title{Capture-admission sensitivity study}
\author{Controlled sensitivity analysis and reproduction checks}
\date{26 October 2026}
\begin{document}\maketitle
\textbf{Status.} '''+status+r'''

\section*{Question and design}
When does a quorum improve contextual admission, and when does that advantage disappear?
The frozen grid has 278 parameter conditions, each evaluated with 100,000 independent synthetic
snapshot trials for object-present and object-absent context. The same latent random inputs are
reused across rules and conditions for paired comparison; they are not 55.6 million independent scenes.

The four witnesses retain the supplied visual profile: placement radius 20 m, range limit 40 m,
height 3 m, and prover height 1.5 m. Range and RF observations use the inspected source equations
and retained RF correction. Sensor errors and missing observations are declared hypothetical
inputs. There is no camera, image recognition, measured error calibration, rendered occlusion,
physical relay attack, temporal process, or network evaluation.

The single-witness reference selects one witness uniformly before each trial's observations.
``Any one of four'' means a positive report from any eligible witness, a different and more
permissive rule. Every rule sees the same range, RF and contextual samples.

\section*{Reference result: independent 10\% errors}
Each witness has false-positive and missed-detection probabilities 0.1, with no missing
observations or dishonest witnesses. Entries are admission percentages with pointwise 95\% Wilson
intervals. The latter quantify Monte Carlo uncertainty within this model, not uncertainty about real sensors.
\begin{center}\small\begin{tabular}{lrr}\toprule
Rule & Valid context (\%) & Invalid context (\%)\\\midrule
'''+'\n'.join(independent_table)+r'''
\bottomrule\end{tabular}\end{center}
The range-plus-RF baseline admits '''+percent(baseline)+r'''\% of the invalid-context trials:
proximity and RF do not evaluate whether the object is present. The 3-of-4 contextual policy admits
'''+percent(ref3)+r'''\% of valid-context trials and '''+percent(bad3)+r'''\% of invalid-context trials.
These are conditional model results, not measured recognition or authentication performance.

From the thesis root, with NumPy 2.5.2, SimPy 4.1.1, Python 3.12 and an authorised source checkout:
\begin{quote}\footnotesize\begin{verbatim}
PYTHONHASHSEED=0 python3 \
 internal-review/experiments/capture-sensitivity/run-study.py \
 --source /path/to/ns3-sim-pol --output /tmp/sensitivity
\end{verbatim}\end{quote}

\clearpage\section*{Shared recognition errors}
With probability $c$, all witnesses use one shared recognition-error draw; otherwise each uses
an independent draw. Marginal error probabilities stay at 0.1. For homogeneous witnesses the raw
pairwise error correlation is $c$; range and RF gating can introduce other decision dependencies.
Other joint error distributions with the same pairwise correlation can produce different quorum rates.
'''+'\n'.join(error_plots)+r'''
For 3-of-4, invalid-context admission rises from '''+percent(bad3)+r'''\% to
'''+percent(common3)+r'''\% as errors become fully shared. At full sharing, several observations
contain essentially one recognition decision. Correlation does not worsen every rule in every
direction: it reduces the false-positive union for ``any one'', and reduces the chance of at least
one missed detection for ``all four''. The full results retain these effects.

\clearpage\section*{Unavailable observations and dishonest reports}
An invisible or missing patch produces UNKNOWN. Admission remains fail-closed. We additionally
label a trial inconclusive when unknown reports from otherwise eligible witnesses could change
the decision; a definitive rejection cannot be rescued by those unknown reports.

The following 3-of-4 curves keep recognition errors independent at 0.1 and vary only the missing
observation process. With shared missingness, the entire observation set is missing together;
independent missingness can instead fragment the set. Equal marginal availability therefore
does not imply equal quorum availability.
'''+'\n'.join(availability_plots)+r'''
\textbf{Dishonest witnesses.} The first $f$ witnesses always report positive. Ranges remain
unforgeable within this model. The table gives invalid-context admission (\%) for 3-of-4.
\begin{center}\small\begin{tabular}{rrrr}\toprule
$f$ & Independent errors & Half shared & Fully shared\\\midrule
'''+'\n'.join(dishonest_table)+r'''
\bottomrule\end{tabular}\end{center}
With two dishonest positives, one further false positive suffices. Independence then creates
two opportunities for that error, explaining why shared errors can lower admission in this
particular compromised configuration. This is not a Byzantine-security proof.

\clearpage\section*{Coverage boundary and range uncertainty}
The path is $y=5$ m. Zero on the horizontal axis is where the third witness's mean biased range
equals 40 m: $x='''+f"{manifest['third_witness_boundary_x_m']:.4f}"+r'''$ m. The lower panel adds independent
0.1 recognition error; the upper panel isolates ranging with perfect contextual observations.
The unbiased geometric 40 m contour lies a further '''+f"{audit['unbiased_geometric_boundary_offset_m']:.3f}"+r''' m along this path.
'''+'\n'.join(boundary_plots)+r'''
These curves describe admission of truthful contextual claims at those positions. Outside the
configured service region, non-admission is expected and is not automatically a false rejection.
Range uncertainty softens the boundary in both directions. Near a three-witness contour,
there may be only three useful observers, so even independent missed detections reduce
availability more than at the four-observer interior point.

\clearpage\section*{Viewpoint and observability}
Each witness points toward the zone centre. Visibility requires the queried ground-level patch
to lie within both its 3-D visual range and horizontal field of view. This is geometry, not an
image-rendering model. The table gives the number of visible witnesses for every specified patch.
\begin{center}\small\begin{tabular}{lrrrrrr}\toprule
 & \multicolumn{3}{c}{Visual range 20 m} & \multicolumn{3}{c}{Visual range 50 m}\\
Patch $(x,y)$ m & $60^\circ$ & $120^\circ$ & $360^\circ$ & $60^\circ$ & $120^\circ$ & $360^\circ$\\\midrule
'''+'\n'.join(visibility_table)+r'''
\bottomrule\end{tabular}\end{center}
The zero entries at the centre with a 20 m visual range follow from 3-D distance:
ground-to-witness separation is $\sqrt{20^2+3^2}>20$ m. They are a declared threshold effect,
not evidence of a defective camera. At patch $(20,5)$ with a $120^\circ$ field of view and 50 m
visual range, only '''+visibility['visible_witnesses']+r''' witnesses see the patch. The 3-of-4 valid-context
admission is '''+percent(visibility)+r'''\%. Witness placement and orientation therefore require
coverage planning beyond the radio-proximity condition.

\section*{What the experiment establishes}
The policy exhibits quantifiable trade-offs between invalid-context admission, valid-context
admission, and observability under stated assumptions. Independent observations can help a quorum;
shared errors, missing viewpoints, and dishonest reports can remove that benefit. Increasing
the threshold can suppress invalid admission while reducing availability. These are conditional
sensitivity findings with explicit failure conditions.

The visual predicate only asks whether a red car is present in a patch. It never inspects a
submitted asset. This study cannot establish that a photograph depicts the observed object or
was captured there; asset binding and physical sensing remain separate validation obligations.

\section*{Checks and reproducibility}
All '''+str(checks['analytical_checks'])+r''' conditional analytical checks passed. The maximum deviation from the
conditional analytical expectation was '''+f'{max_z:.2f}'+r''' Monte Carlo standard errors, within the predefined
diagnostic tolerance of seven. This is an implementation check, not a goodness-of-fit test for
real sensors. All '''+str(checks['source_replay_decisions'])+r''' sampled source-policy/quorum replays and
'''+str(checks['monotone_checks'])+r''' nested-quorum checks passed. The corrected RF score passed its regression checks.

The complete grid, every result row, paired contrasts, and 100 batch counts per row are retained
in \path{results/}. The design is \path{design.json}; the manifest records source, correction,
driver, design, random-input hashes and dependency versions. Pointwise intervals follow the
\href{https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm}{NIST Wilson-interval description}.
The inputs are independent synthetic snapshots, with no inferred real-world confidence bound.
A second execution reproduced all five raw output files byte for byte. Before integration,
hash checks confirmed that all 31 protected thesis and response files, including both PDFs,
were unchanged. That pre-integration record is retained as historical provenance.
The scripts \path{verify-study.py} and \path{make-report.py} check the repeat and generate this report.

\end{document}
'''
    (HERE/'report.tex').write_text(tex)
    print(json.dumps(dict(max_analytical_deviation_standard_errors=max_z,
                          reference_valid_percent=percent(ref3), reference_invalid_percent=percent(bad3),
                          fully_shared_invalid_percent=percent(common3)), indent=2))


if __name__ == '__main__':
    main()
