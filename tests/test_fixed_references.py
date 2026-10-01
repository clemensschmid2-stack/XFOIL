import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from scripts import fixed_references as refs
from scripts import verify_xfoil_parity as xfoil


def test_committed_reference_inventory_and_hashes():
    executable, manifest = refs.xfoil_reference()
    assert executable.is_file()
    assert manifest['files']

def fixture(tmp_path, data=b'fixed executable'):
    (tmp_path/'binary').write_bytes(data)
    receipt=dict(format='vds-fixed-reference-v1',files={'binary':hashlib.sha256(data).hexdigest()})
    (tmp_path/'manifest.json').write_text(json.dumps(receipt))
    return receipt


def test_reference_is_verified_without_rebuild(tmp_path):
    expected=fixture(tmp_path)
    assert refs.verify_files(tmp_path)==expected


@pytest.mark.parametrize('change',['missing','tampered'])
def test_missing_or_changed_reference_fails(tmp_path,change):
    fixture(tmp_path)
    if change=='missing': (tmp_path/'binary').unlink()
    else: (tmp_path/'binary').write_bytes(b'changed')
    with pytest.raises(ValueError,match='reference|Reference'):
        refs.verify_files(tmp_path)


def test_reference_manifest_cannot_escape_directory(tmp_path):
    manifest=fixture(tmp_path)
    manifest['files']={'../outside':'not a hash'}
    (tmp_path/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='unsafe|inventory'):
        refs.verify_files(tmp_path)


def test_xfoil_only_builds_candidate_after_reference_validation(tmp_path,monkeypatch):
    calls=[]
    monkeypatch.setattr(xfoil,'xfoil_reference',lambda: (tmp_path/'fixed.exe',{'source_hashes':{}}))
    def compiler(source,*args):
        calls.append(source)
        raise RuntimeError('candidate compiler sentinel')
    monkeypatch.setattr(xfoil,'compile_build',compiler)
    with pytest.raises(RuntimeError,match='candidate compiler sentinel'):
        xfoil.verify(SimpleNamespace(output=tmp_path/'out',builds=None,compiler=tmp_path,timeout=1))
    assert calls==[xfoil.SOURCE]


def test_xfoil_missing_reference_never_attempts_compilation(tmp_path,monkeypatch):
    def missing(): raise ValueError('Missing reference')
    monkeypatch.setattr(xfoil,'xfoil_reference',missing)
    monkeypatch.setattr(xfoil,'compile_build',lambda *a: pytest.fail('must not compile'))
    with pytest.raises(ValueError,match='Missing reference'):
        xfoil.verify(SimpleNamespace(output=tmp_path/'out',builds=None))


def test_unexpected_reference_dll_fails(tmp_path):
    fixture(tmp_path)
    (tmp_path/'untracked.dll').write_bytes(b'could affect loading')
    with pytest.raises(ValueError,match='inventory'):
        refs.verify_files(tmp_path)


@pytest.mark.parametrize('checked_behavior', ['pass', 'mismatch', 'blocked', 'missing'])
def test_full_gate_requires_bounds_candidate(tmp_path, monkeypatch, checked_behavior):
    previous = tmp_path/'previous'
    previous.mkdir()
    binaries = {'candidate': {'path': 'normal.exe', 'sha256': 'hash'}}
    if checked_behavior != 'missing':
        binaries['checked'] = {'path': 'checked.exe', 'sha256': 'hash'}
    (previous/'summary.json').write_text(json.dumps(dict(
        archive_sha256=xfoil.ARCHIVE_SHA256,
        source_hashes={'candidate': {}, 'official': {}},
        compiler={'sha256': 'hash'},
        binaries=binaries)))
    monkeypatch.setattr(xfoil, 'source_identity', lambda path: {})
    monkeypatch.setattr(xfoil, 'digest', lambda path: 'hash')
    monkeypatch.setattr(xfoil, 'xfoil_reference',
                        lambda: (Path('reference.exe'), {'source_hashes': {}}))
    monkeypatch.setattr(xfoil, 'compile_build', lambda *a: pytest.fail('must reuse'))
    calls = []
    def run(executable, case, directory, timeout):
        calls.append(str(executable))
        if str(executable) == 'checked.exe' and checked_behavior == 'blocked':
            raise OSError(4551, 'Application control blocked execution')
        lift = float(str(executable) == 'checked.exe' and checked_behavior == 'mismatch')
        return dict(case=xfoil.asdict(case), nodes=[[0., 0.]]*case.panels,
                    polar=[[0., lift, 0., 0., 0.]], elapsed_seconds=0.)
    monkeypatch.setattr(xfoil, 'run_case', run)
    args = SimpleNamespace(output=tmp_path/'output', builds=previous,
                           compiler=tmp_path, timeout=1)
    if checked_behavior in ('blocked', 'missing'):
        with pytest.raises((OSError, RuntimeError), match='blocked|bounds-checked builds'):
            xfoil.verify(args)
        report = json.loads((tmp_path/'output/summary.json').read_text())
        assert report['status'] == 'FAIL'
        if checked_behavior == 'missing':
            assert not calls
        return
    assert xfoil.verify(args) == (1 if checked_behavior == 'mismatch' else 0)
    report = json.loads((tmp_path/'output/summary.json').read_text())
    assert set(calls) == {'normal.exe', 'reference.exe', 'checked.exe'}
    assert calls.count('checked.exe') == 16
    assert len(report['cases']) == 8
    assert len(report['capacity']) == 8
    assert len(report['refinement']) == 2
    assert set(report['binaries']) == {'candidate', 'checked', 'official'}
    assert report['status'] == ('FAIL' if checked_behavior == 'mismatch' else 'PASS')
