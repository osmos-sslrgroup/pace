import pytest
import sys
import os

# Add backend directory to path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from calc_engine import ROEngine, normalize_elements_per_vessel
from system_engine import SystemEngine, _total_elements, _epv_out


def test_normalize_elements_per_vessel():
    # Single int
    assert normalize_elements_per_vessel(6, 2) == [6, 6]
    # Single string
    assert normalize_elements_per_vessel("6", 2) == [6, 6]
    # List of ints
    assert normalize_elements_per_vessel([6, 3], 2) == [6, 3]
    # Comma-separated string
    assert normalize_elements_per_vessel("6, 3", 2) == [6, 3]
    # Semicolon-separated string
    assert normalize_elements_per_vessel("6; 4", 2) == [6, 4]
    # Short list repeated
    assert normalize_elements_per_vessel([7], 3) == [7, 7, 7]
    # Extra values truncated
    assert normalize_elements_per_vessel([6, 5, 4], 2) == [6, 5]

    # Out of range values raise ValueError
    with pytest.raises(ValueError):
        normalize_elements_per_vessel(0, 2)
    with pytest.raises(ValueError):
        normalize_elements_per_vessel(9, 2)
    with pytest.raises(ValueError):
        normalize_elements_per_vessel("6, 10", 2)


def test_total_elements_and_epv_out():
    assert _total_elements([4, 2], [6, 3], 2) == 4 * 6 + 2 * 3
    assert _total_elements([4, 2], 6, 2) == 6 * 6
    assert _epv_out(6, 2) == 6
    assert _epv_out([6, 6], 2) == 6
    assert _epv_out([6, 3], 2) == [6, 3]


def test_ro_engine_multistage_per_stage_elements():
    engine = ROEngine()
    feed_ions = {
        "Ca": 100.0, "Mg": 50.0, "Na": 300.0, "K": 10.0,
        "Cl": 600.0, "SO4": 200.0, "HCO3": 150.0, "SiO2": 20.0
    }
    
    # 2 stages: 4 vessels in stage 1 with 6 elements, 2 vessels in stage 2 with 3 elements
    res = engine.simulate_system(
        feed_flow_m3h=50.0,
        feed_pressure_bar=18.0,
        feed_ions=feed_ions,
        temp_c=25.0,
        membrane_model="SWRO-8040-400",
        stages=2,
        vessels_per_stage=[4, 2],
        elements_per_vessel=[6, 3]
    )

    summary = res["summary"]
    assert summary["elements_per_vessel"] == [6, 3]
    assert summary["total_elements"] == 4 * 6 + 2 * 3 # 30 elements
    assert len(res["stages"]) == 2
    assert res["stages"][0]["elements_per_vessel"] == 6
    assert res["stages"][1]["elements_per_vessel"] == 3
    # Check total number of element records: (4*6 + 2*3) = wait, element entries are one representative per stage position
    # Stage 1 has 6 elements, Stage 2 has 3 elements -> 9 element records
    assert len(res["elements"]) == 9


def test_system_engine_with_per_stage_elements():
    engine = SystemEngine()
    input_data = {
        "technology_train": "RO",
        "feed_water": {
            "temperature": 25.0, "ph": 7.5,
            "calcium": 100.0, "magnesium": 50.0, "sodium": 300.0,
            "chloride": 600.0, "sulfate": 200.0, "bicarbonate": 150.0,
            "silica": 20.0, "tds": 1420.0
        },
        "target_flow_m3h": 50.0,
        "target_recovery_pct": 75.0,
        "ro_membrane": "SWRO-8040-400",
        "stages": 2,
        "vessels_per_stage": [4, 2],
        "elements_per_vessel": "6, 3",
        "economic_params": {}
    }

    result = engine.calculate_system(input_data)
    assert result["elements_per_vessel"] == [6, 3]
    assert result["stages_count"] == 2
    # Check summary
    ro_res = result["ro_results"]
    assert ro_res["summary"]["total_elements"] == 30
