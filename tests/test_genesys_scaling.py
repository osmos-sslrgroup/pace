import pytest
import sys
import os

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from scaling_engine import adjust_ph, analyse, recommend, ions_from_feed
from antiscalant_database import ANTISCALANTS, UNTREATED_LIMITS
import scaling_api


def test_antiscalant_database_specs():
    assert "Genesys LF" in ANTISCALANTS
    assert "Genesys RC" in ANTISCALANTS
    assert "Genesys SI" in ANTISCALANTS

    lf = ANTISCALANTS["Genesys LF"]
    assert lf["selection_role"] == "fouling"
    assert "lsi_max" in lf["limits"]
    assert "SiO2" in lf["limits"]
    assert "CaSO4" in lf["limits"]


def test_scaling_engine_adjust_ph():
    feed_dict = {
        "calcium": 120.0, "magnesium": 45.0, "sodium": 200.0,
        "chloride": 300.0, "sulfate": 150.0, "bicarbonate": 180.0,
        "ph": 7.8, "temperature": 25.0
    }
    ions = ions_from_feed(feed_dict)
    
    # Depress pH to 6.5 using H2SO4
    res_h2so4 = adjust_ph(ions, raw_ph=7.8, target_ph=6.5, chemical="H2SO4", temp_c=25.0)
    assert res_h2so4["ph"] == 6.5
    assert res_h2so4["dose_mg_l"] > 0
    assert res_h2so4["ions"]["SO4"] > ions["SO4"]
    assert res_h2so4["ions"]["HCO3"] < ions["HCO3"]
    assert res_h2so4["co2_mg_l"] > 0

    # Depress pH to 6.5 using HCl
    res_hcl = adjust_ph(ions, raw_ph=7.8, target_ph=6.5, chemical="HCl", temp_c=25.0)
    assert res_hcl["ph"] == 6.5
    assert res_hcl["dose_mg_l"] > 0
    assert res_hcl["ions"]["Cl"] > ions["Cl"]


def test_scaling_engine_product_selection_and_dose():
    feed = {
        "temperature": 25.0, "ph": 7.5,
        "calcium": 150.0, "magnesium": 60.0, "sodium": 400.0,
        "chloride": 650.0, "sulfate": 350.0, "bicarbonate": 200.0,
        "silica": 25.0, "barium": 0.05, "strontium": 1.5, "fluoride": 1.0
    }
    
    # Normal feed at 75% recovery -> auto recommends Genesys LF
    analysis = analyse(feed, recovery_pct=75.0, antiscalant="auto", feed_flow_m3h=50.0, sweep=True)
    assert "selected" in analysis
    sel = analysis["selected"]
    assert sel["product"] in ("Genesys LF", "Genesys RC", "Genesys SI")
    assert sel["dose"]["total_feed_dose_mg_l"] > 0.0
    assert sel["dose"]["kg_per_day"] > 0.0
    assert "treated_pct" in analysis
    assert "untreated_pct" in analysis
    assert "max_recovery" in analysis
    assert len(analysis["max_recovery"]) > 0

    # High silica feed -> should select or properly limit with Genesys SI
    feed_high_si = dict(feed, silica=80.0)
    analysis_si = analyse(feed_high_si, recovery_pct=75.0, antiscalant="auto")
    assert analysis_si["selected"]["product"] == "Genesys SI"


def test_scaling_api_direct_calls():
    # Verify API functions without TestClient loop
    products = scaling_api.list_antiscalants()
    assert isinstance(products, list)
    assert len(products) == 3

    feed_req = scaling_api.AntiscalantInput(
        recovery_pct=75.0,
        feed_flow_m3h=50.0,
        antiscalant="auto",
        feed_water={
            "calcium": 100.0, "magnesium": 40.0, "sodium": 200.0,
            "bicarbonate": 150.0, "sulfate": 100.0, "chloride": 300.0,
            "silica": 20.0, "ph": 7.5, "temperature": 25.0
        }
    )
    result = scaling_api.antiscalant_analysis(feed_req)
    assert result["selected"]["product"] in ("Genesys LF", "Genesys RC", "Genesys SI")
    assert result["inputs"]["recovery_pct"] == 75.0
