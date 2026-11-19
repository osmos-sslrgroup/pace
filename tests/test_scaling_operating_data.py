import sys
import os
import pytest

# Ensure backend directory is in python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
from server import calculate_scaling, FeedWaterData

def test_scaling_default_operating_data():
    """Test default scaling calculation with recovery = 75% (CF = 4.0)."""
    feed = FeedWaterData(
        calcium=120.0,
        magnesium=45.0,
        sodium=250.0,
        chloride=300.0,
        sulfate=200.0,
        bicarbonate=240.0,
        temperature=20.0,
        ph=7.5,
        raw_ph=7.5,
        feed_ph=7.5,
        recovery_pct=75.0,
        pressure_bar=20.0,
        acid_type="H2SO4",
        calculate_concentrate=True
    )
    res = calculate_scaling(feed)
    assert res is not None
    assert "calcite_si" in res
    assert "gypsum_si" in res
    assert res["cf"] == 4.0
    assert res["acid_dose_mg_l"] == 0.0
    assert res["stream_evaluated"] == "concentrate"
    assert isinstance(res["calcite_si"], float)
    assert isinstance(res["gypsum_si"], float)

def test_scaling_acid_dosing_h2so4():
    """Test stoichiometric H2SO4 dosing when feed pH is adjusted downwards."""
    feed_unadjusted = FeedWaterData(
        calcium=120.0,
        magnesium=45.0,
        sodium=250.0,
        chloride=300.0,
        sulfate=200.0,
        bicarbonate=240.0,
        temperature=20.0,
        ph=7.8,
        raw_ph=7.8,
        feed_ph=7.8,
        recovery_pct=75.0,
        acid_type="H2SO4"
    )
    res_raw = calculate_scaling(feed_unadjusted)

    feed_acidified = FeedWaterData(
        calcium=120.0,
        magnesium=45.0,
        sodium=250.0,
        chloride=300.0,
        sulfate=200.0,
        bicarbonate=240.0,
        temperature=20.0,
        ph=7.8,
        raw_ph=7.8,
        feed_ph=6.8,  # depress pH by 1.0 unit
        recovery_pct=75.0,
        acid_type="H2SO4"
    )
    res_acid = calculate_scaling(feed_acidified)

    # Acid dose should be strictly positive
    assert res_acid["acid_dose_mg_l"] > 10.0
    assert res_acid["acid_type"] == "H2SO4"
    assert res_acid["feed_ph"] == 6.8
    assert res_acid["raw_ph"] == 7.8
    # Acidification must suppress Calcite Saturation Index
    assert res_acid["calcite_si"] < res_raw["calcite_si"]
    # Added sulfate should slightly increase gypsum SI
    assert res_acid["gypsum_si"] >= res_raw["gypsum_si"]

def test_scaling_acid_dosing_hcl():
    """Test stoichiometric HCl dosing when feed pH is adjusted downwards."""
    feed_hcl = FeedWaterData(
        calcium=100.0,
        magnesium=30.0,
        sodium=200.0,
        chloride=200.0,
        sulfate=150.0,
        bicarbonate=200.0,
        temperature=20.0,
        ph=7.6,
        raw_ph=7.6,
        feed_ph=6.6,
        recovery_pct=75.0,
        acid_type="HCl"
    )
    res = calculate_scaling(feed_hcl)
    assert res["acid_dose_mg_l"] > 5.0
    assert res["acid_type"] == "HCl"
    assert res["feed_ph"] == 6.6

def test_scaling_recovery_sensitivity():
    """Test that higher recovery (higher CF) increases saturation indices."""
    feed_low_rec = FeedWaterData(
        calcium=100.0,
        magnesium=30.0,
        sodium=200.0,
        chloride=200.0,
        sulfate=200.0,
        bicarbonate=180.0,
        temperature=20.0,
        ph=7.2,
        raw_ph=7.2,
        feed_ph=7.2,
        recovery_pct=50.0  # CF = 2.0
    )
    res_low = calculate_scaling(feed_low_rec)

    feed_high_rec = FeedWaterData(
        calcium=100.0,
        magnesium=30.0,
        sodium=200.0,
        chloride=200.0,
        sulfate=200.0,
        bicarbonate=180.0,
        temperature=20.0,
        ph=7.2,
        raw_ph=7.2,
        feed_ph=7.2,
        recovery_pct=80.0  # CF = 5.0
    )
    res_high = calculate_scaling(feed_high_rec)

    assert res_low["cf"] == 2.0
    assert res_high["cf"] == 5.0
    # Higher concentration factor increases mineral saturation
    assert res_high["calcite_si"] > res_low["calcite_si"]
    assert res_high["gypsum_si"] > res_low["gypsum_si"]
