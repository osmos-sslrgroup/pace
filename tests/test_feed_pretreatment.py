import pytest
import sys
import os

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from system_engine import SystemEngine, _location, _loc_from_text, _resolve_conditioning
from server_impl import ConditioningConfig, SystemCalcInput, PassConfig, ElementsPerVessel


def test_location_detection():
    """Verify _location parses all keys, flags, free text, and chemical fallbacks."""
    # Free text detection
    assert _loc_from_text("Feed Pre-treatment") == "pre"
    assert _loc_from_text("RO feed") == "pre"
    assert _loc_from_text("Inlet raw water") == "pre"
    assert _loc_from_text("Product permeate") == "post"
    assert _loc_from_text("Post-treatment") == "post"
    assert _loc_from_text("Interstage (between passes)") == "interstage"
    assert _loc_from_text("Pass 2 feed") == "interstage"

    # Flag and key detection
    assert _location({"apply_to_feed": True}) == "pre"
    assert _location({"feed_pretreatment": "true"}) == "pre"
    assert _location({"apply_to_permeate": True}) == "post"
    assert _location({"apply_to_interstage": True}) == "interstage"
    assert _location({"dosing_point": "RO feed"}) == "pre"
    assert _location({"location": "pre"}) == "pre"


def test_resolve_conditioning_chemical_fallback():
    """Verify that flat conditioning without location follows chemical rules."""
    # Acid defaults to pre (RO feed)
    c_acid = _resolve_conditioning({"conditioning": {"enabled": True, "chemical": "HCl", "target_ph": 6.2}}, two_pass=False)
    assert c_acid["pre"]
    assert c_acid["pre"]["chemical"] == "HCl"
    assert c_acid["pre"]["target_ph"] == 6.2
    assert not c_acid["post"]

    # Caustic on single-pass defaults to post
    c_base_1p = _resolve_conditioning({"conditioning": {"enabled": True, "chemical": "NaOH", "target_ph": 8.0}}, two_pass=False)
    assert c_base_1p["post"]
    assert c_base_1p["post"]["chemical"] == "NaOH"
    assert not c_base_1p["pre"]

    # Caustic on two-pass defaults to interstage
    c_base_2p = _resolve_conditioning({"conditioning": {"enabled": True, "chemical": "NaOH", "target_ph": 8.5}}, two_pass=True)
    assert c_base_2p["interstage"]
    assert c_base_2p["interstage"]["chemical"] == "NaOH"


def test_feed_pretreatment_simulation():
    """Run SystemEngine with acid pre-treatment and verify raw vs treated streams."""
    engine = SystemEngine()
    payload = {
        "technology_train": "RO",
        "feed_water": {
            "temperature": 25.0,
            "ph": 7.8,
            "calcium": 120.0,
            "magnesium": 40.0,
            "sodium": 250.0,
            "potassium": 10.0,
            "chloride": 400.0,
            "sulfate": 200.0,
            "bicarbonate": 240.0,
            "silica": 25.0,
        },
        "target_flow_m3h": 20.0,
        "target_recovery_pct": 75.0,
        "ro_membrane": "BW30-400",
        "stages": 1,
        "vessels_per_stage": [4],
        "elements_per_vessel": 6,
        "conditioning": {
            "enabled": True,
            "chemical": "H2SO4",
            "target_ph": 6.5,
            "location": "pre"
        }
    }

    result = engine.calculate_system(payload)
    assert result is not None
    assert "feed_conditioning" in result
    assert result["feed_conditioning"] is not None
    assert result["feed_conditioning"]["chemical"] == "H2SO4"
    assert result["feed_conditioning"]["dose_mg_l"] > 0
    # Treated RO feed pH
    assert abs(result["ro_feed_ph"] - 6.5) < 0.2
    assert abs(result["feed_conditioning"]["ph_out"] - 6.5) < 0.2
    # Pure raw feed preserved in feed_water_used
    assert result["feed_water_used"]["ph"] == 7.8


def test_server_pydantic_schema_extra_allowed():
    """Verify server schemas accept location fields and extra parameters without stripping."""
    cond = ConditioningConfig(
        enabled=True,
        chemical="HCl",
        target_ph=6.0,
        location="pre",
        extra_arbitrary_key="preserved"
    )
    dump = cond.model_dump()
    assert dump["location"] == "pre"
    assert dump.get("extra_arbitrary_key") == "preserved"

    sys_input = SystemCalcInput(
        technology_train="RO",
        feed_water={"temperature": 25.0, "ph": 7.5, "raw_ph": 7.5, "feed_ph": 6.5},
        target_flow_m3h=20.0,
        target_recovery_pct=75.0,
        ro_membrane="BW30-400",
        stages=1,
        vessels_per_stage=[2],
        elements_per_vessel=6,
        recycle_flow_m3h=5.0,
        permeate_degasser={"enabled": True},
        feed_conditioning={"enabled": True, "chemical": "HCl", "target_ph": 6.0, "location": "pre"}
    )
    dump_sys = sys_input.model_dump()
    assert dump_sys.get("recycle_flow_m3h") == 5.0
    assert dump_sys.get("permeate_degasser") == {"enabled": True}
    assert dump_sys.get("feed_conditioning")["location"] == "pre"
