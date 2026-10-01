"""Compare the committed XFOIL 6.996 executable with isolated candidate builds.

Never installs binaries or touches production run directories. Archive identity is
mandatory; all compiler output, commands, coordinates and polar rows are retained.
"""
from __future__ import annotations
import argparse
from dataclasses import dataclass, asdict
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixed_references import xfoil_reference

ROOT = Path(__file__).resolve().parents[1]
URL = "https://web.mit.edu/drela/Public/web/xfoil/xfoil6.996.tgz"
ARCHIVE_SHA256 = "0feb71b58070d8514d830fcb0b609a10a11399d362493d7b9bbfb7343dff3f23"
SOURCE = ROOT


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_identity(source):
    return {str(p.relative_to(source)): digest(p)
            for folder in ('src', 'plotlib', 'osrc')
            for p in sorted((source / folder).rglob('*'))
            if p.is_file() and p.suffix.lower() in ('.f', '.c', '.h', '.inc')}


def compile_build(source, output, compiler, checked=False):
    command = [sys.executable, str(ROOT / 'scripts/build_xfoil.py'),
               '--source', str(source), '--build-dir', str(output),
               '--gfortran', str(compiler / 'gfortran.exe'), '--gcc', str(compiler / 'gcc.exe')]
    if checked:
        command.append('--bounds-check')
    output.mkdir(parents=True)
    with (output / 'build.log').open('w') as log:
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
    return output / 'install/xfoil.exe'


@dataclass(frozen=True)
class Case:
    name: str
    foil: str = '0012'
    reynolds: float = 1e6
    panels: int = 240
    end: float = 6.
    step: float = 2.
    flap: float = 0.
    mach: float = 0.
    trip: float = 1.
    filtered: bool = False
    native_naca: bool = False


def case_script(case):
    lines = ['PLOP', 'G', '', f'NACA {case.foil}' if case.native_naca else 'LOAD foil.dat']
    if case.filtered:
        lines += ['MDES', 'FILT', 'EXEC', '']
    if case.flap:
        lines += ['GDES', f'FLAP 0.75 999 {case.flap}', '0.5', 'EXEC', '']
    lines += ['PPAR', f'N {case.panels}', '', '', 'PANE', 'PSAV nodes.dat',
              'OPER', 'TYPE 1', f'VISC {case.reynolds}', f'MACH {case.mach}',
              'VPAR', 'N 9', f'XTR {case.trip} {case.trip}', '', 'ITER 200',
              'PACC', 'polar.txt', '', f'ASEQ 0 {case.end} {case.step}',
              'PACC', '', 'QUIT', '']
    return '\n'.join(lines)


def foil_coordinates(code):
    # Fixed input discretization: upstream NACA uses IQX/3 source points, so
    # NACA commands would change the geometry when the capacity is enlarged.
    m, p, t = int(code[0]) / 100., int(code[1]) / 10., int(code[2:]) / 100.
    upper, lower = [], []
    for i in range(201):
        x = (1-math.cos(math.pi*i/200))/2
        yt = 5*t*(.2969*math.sqrt(x)-.126*x-.3516*x*x+.2843*x**3-.1015*x**4)
        yc = slope = 0.
        if m:
            if x < p:
                yc, slope = m/p**2*(2*p*x-x*x), 2*m/p**2*(p-x)
            else:
                yc, slope = m/(1-p)**2*((1-2*p)+2*p*x-x*x), 2*m/(1-p)**2*(p-x)
        angle = math.atan(slope)
        upper.append((x-yt*math.sin(angle), yc+yt*math.cos(angle)))
        lower.append((x+yt*math.sin(angle), yc-yt*math.cos(angle)))
    return list(reversed(upper))+lower[1:]


def read_rows(path, columns):
    rows = []
    for line in path.read_text().splitlines():
        tokens = line.split()
        if len(tokens) != columns:
            continue
        try:
            row = [float(value) for value in tokens]
        except ValueError:
            continue
        if not all(math.isfinite(value) for value in row):
            raise RuntimeError(f'Non-finite output in {path}')
        rows.append(row)
    if not rows:
        raise RuntimeError(f'No numeric rows in {path}')
    return rows


def run_case(executable, case, directory, timeout):
    directory.mkdir(parents=True)
    (directory / 'foil.dat').write_text('NACA '+case.foil+'\n' + ''.join(f'{x:.16g} {y:.16g}\n' for x, y in foil_coordinates(case.foil)))
    script = case_script(case)
    (directory / 'input.txt').write_text(script)
    start = time.monotonic()
    env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
    with (directory / 'run.log').open('w') as log:
        completed = subprocess.run([str(executable)], input=script, text=True,
                                   stdout=log, stderr=subprocess.STDOUT, cwd=directory,
                                   env=env, timeout=timeout)
    log = (directory / 'run.log').read_text(errors='replace')
    if completed.returncode or any(s in log.lower() for s in
            ('fortran runtime error', 'array overflow', 'increase iqx', 'too many panels', 'segmentation fault')):
        raise RuntimeError(f'Native failure (exit {completed.returncode}): {directory / "run.log"}')
    nodes = read_rows(directory / 'nodes.dat', 2)
    if abs(len(nodes) - case.panels) > 2:
        raise RuntimeError(f'Panel request silently clamped: {case.panels} -> {len(nodes)}')
    rows = read_rows(directory / 'polar.txt', 9)
    expected = [i * case.step for i in range(round(case.end / case.step) + 1)]
    if [row[0] for row in rows] != expected:
        raise RuntimeError(f'Missing/extra converged angles: {directory}')
    return dict(case=asdict(case), nodes=nodes, polar=rows,
                elapsed_seconds=time.monotonic()-start)


def compare_rows(reference, candidate, atol=1e-12):
    if len(reference) != len(candidate):
        raise ValueError('Different row counts')
    errors = []
    for i, (left, right) in enumerate(zip(reference, candidate)):
        if len(left) != len(right):
            raise ValueError('Different column counts')
        for j, (a, b) in enumerate(zip(left, right)):
            if not math.isfinite(a) or not math.isfinite(b) or abs(a-b) > atol:
                errors.append(dict(row=i, column=j, expected=a, actual=b))
    return errors


def verify(args):
    work = args.output.resolve()
    work.mkdir(parents=True, exist_ok=False)
    report = dict(status='RUNNING', official_url=URL, archive_sha256=ARCHIVE_SHA256,
                  precision='real64', cases=[], refinement=[], capacity=[])
    report_path = work / 'summary.json'
    def save():
        report_path.write_text(json.dumps(report, indent=2, allow_nan=False))
    save()
    try:
        reference, pinned = xfoil_reference()
        report['reference_manifest'] = pinned
        if args.builds:
            previous = json.loads((args.builds / 'summary.json').read_text())
            if previous.get('archive_sha256') != ARCHIVE_SHA256:
                raise RuntimeError('Reused reference is not the pinned archive')
            if previous['source_hashes']['candidate'] != source_identity(SOURCE):
                raise RuntimeError('Candidate source changed; rebuild required')
            if previous['compiler']['sha256'] != digest(args.compiler / 'gfortran.exe'):
                raise RuntimeError('Compiler changed; rebuild required')
            if not all(name in previous.get('binaries', {}) for name in ('candidate', 'checked')):
                raise RuntimeError('Both normal and bounds-checked builds are required; rerun without --builds')
            for record in (previous['binaries'][name] for name in ('candidate','checked')):
                if digest(Path(record['path'])) != record['sha256']:
                    raise RuntimeError('Reused binary hash mismatch')
            candidate, checked = (Path(previous['binaries'][name]['path'])
                                  for name in ('candidate', 'checked'))
            for key in ('source_hashes', 'binaries', 'compiler'):
                report[key] = previous[key]
        else:
            print('Building candidate and bounds-checked candidate', flush=True)
            candidate_identity = source_identity(SOURCE)
            candidate = compile_build(SOURCE, work / 'candidate-build', args.compiler)
            checked = compile_build(SOURCE, work / 'checked-build', args.compiler, True)
            if source_identity(SOURCE) != candidate_identity:
                raise RuntimeError('Candidate source changed during build')
            report['source_hashes'] = dict(official=pinned['source_hashes'], candidate=candidate_identity)
            report['binaries'] = {name: dict(path=str(path), sha256=digest(path))
                                  for name, path in [('official', reference), ('candidate', candidate), ('checked', checked)]}
            report['compiler'] = dict(path=str(args.compiler), sha256=digest(args.compiler / 'gfortran.exe'))
        report['source_hashes']['official'] = pinned['source_hashes']
        report['binaries']['official'] = dict(path=str(reference), sha256=digest(reference))
        cases = [Case('symmetric_positive'), Case('symmetric_negative', end=-6., step=-2.),
                 Case('cambered_low_re', foil='4412', reynolds=1e5, end=4.),
                 Case('cambered_high_re', foil='4412', reynolds=3e6, mach=.15),
                 Case('flap_positive', foil='4412', flap=10., filtered=True, end=4.),
                 Case('flap_negative', foil='4412', flap=-10., end=-4., step=-2.),
                 Case('forced_transition', trip=.1), Case('official_solver_limit', panels=500, end=4.)]
        failures = 0
        for case in cases:
            print(f'Official parity: {case.name}', flush=True)
            expected = run_case(reference, case, work / case.name / 'official', args.timeout)
            actual = run_case(candidate, case, work / case.name / 'candidate', args.timeout)
            bounds = run_case(checked, case, work / case.name / 'checked', args.timeout)
            errors = compare_rows(expected['polar'], actual['polar'])
            errors += compare_rows(expected['nodes'], actual['nodes'])
            errors += compare_rows(actual['polar'], bounds['polar'])
            failures += len(errors)
            report['cases'].append(dict(name=case.name, status='FAIL' if errors else 'PASS',
                                        differences=errors, rows=len(expected['polar'])))
            save()
        # Above official capacity, use native bounds checks and a panel-refinement
        # study. These are explicitly not official-reference comparisons.
        for foil in ('0012', '4412'):
            results = []
            for panels in (595, 800, 1000):
                case = Case(f'refinement_{foil}_{panels}', foil=foil, panels=panels, end=4.)
                print(f'Capacity/refinement: {case.name}', flush=True)
                actual = run_case(candidate, case, work / case.name / 'candidate', args.timeout)
                bounds = run_case(checked, case, work / case.name / 'checked', args.timeout)
                errors = compare_rows(actual['polar'], bounds['polar'])
                failures += len(errors)
                report['capacity'].append(dict(name=case.name, requested=panels, actual=len(actual['nodes']),
                    status='FAIL' if errors else 'PASS', differences=errors,
                    elapsed_seconds=actual['elapsed_seconds']))
                results.append(actual)
            # Engineering regression tolerances, not an aerodynamic accuracy claim.
            tolerances = [0., .01, .0005, .0005, .005]
            changes = []
            for a, b in zip(results, results[1:]):
                maximum = [max(abs(x[j]-y[j]) for x, y in zip(a['polar'], b['polar'])) for j in range(5)]
                failed = any(x > tol for x, tol in zip(maximum, tolerances))
                failures += int(failed)
                changes.append(dict(from_panels=a['case']['panels'], to_panels=b['case']['panels'],
                                    max_absolute_changes=maximum, status='FAIL' if failed else 'PASS'))
            report['refinement'].append(dict(foil=foil, tolerances=tolerances, comparisons=changes))
            save()
        for case in (Case('flapped_capacity', foil='4412', panels=1000, flap=10., filtered=True, end=4.),
                     Case('native_naca_capacity', panels=1000, native_naca=True, end=4.)):
            print(f'Capacity: {case.name}', flush=True)
            actual = run_case(candidate, case, work / case.name / 'candidate', args.timeout)
            bounds = run_case(checked, case, work / case.name / 'checked', args.timeout)
            errors = compare_rows(actual['polar'], bounds['polar'])
            failures += len(errors)
            report['capacity'].append(dict(name=case.name, requested=case.panels,
                actual=len(actual['nodes']), status='FAIL' if errors else 'PASS', differences=errors))
        report.update(status='FAIL' if failures else 'PASS', failures=failures)
        save()
        return 1 if failures else 0
    except Exception as error:
        report.update(status='FAIL', error=str(error))
        save()
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='new isolated directory')
    parser.add_argument('--compiler', type=Path, default=Path('C:/msys64/mingw64/bin'))
    parser.add_argument('--timeout', type=int, default=180)
    parser.add_argument('--builds', type=Path, help='reuse hash-verified builds from a preceding report')
    raise SystemExit(verify(parser.parse_args()))
