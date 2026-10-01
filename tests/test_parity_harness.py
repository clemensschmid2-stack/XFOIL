"""The native parity gate must fail on missing or invalid numerical evidence."""
import math
import pytest

from scripts.verify_xfoil_parity import Case, case_script, compare_rows, read_rows


def test_parity_rejects_missing_rows_and_columns():
    with pytest.raises(ValueError):
        compare_rows([[0., 1.]], [])
    with pytest.raises(ValueError):
        compare_rows([[0., 1.]], [[0.]])


@pytest.mark.parametrize('value', [math.nan, math.inf, -math.inf, 1.001])
def test_parity_rejects_nonfinite_and_changed_values(value):
    assert compare_rows([[1.]], [[value]])


def test_parser_rejects_nonfinite_output(tmp_path):
    polar = tmp_path / 'polar.txt'
    polar.write_text('0 nan\n')
    with pytest.raises(RuntimeError, match='Non-finite'):
        read_rows(polar, 2)


def test_negative_sweep_and_capacity_are_explicit():
    script = case_script(Case('negative', panels=1000, end=-4., step=-2., flap=-10.))
    assert 'N 1000\n' in script
    assert 'ASEQ 0 -4.0 -2.0' in script
    assert 'FLAP 0.75 999 -10.0' in script
