"""
Membrane Database for PACE Calculation Module
Contains specifications for RO, NF, and UF elements.
"""

from typing import Dict, Any
import warnings

# ---------------------------------------------------------------------------
# Ion transport and hydraulic parameters for RO — CALIBRATED against Toray DS2
# (v4, 13 Nov 2026, Toray DS2 v2.2.3, membrane DB 20160)
#
# Calibration matrix (25 C, new membrane, no acid, no recycle):
#   BW TM720D-400: 500, 1,000, 5,000, 10,000 mg/L (1 stage, 50 %), 2,000 mg/L 2 stages at pH 6.5 / 7.5 / 8.5
#   SW TM820M-400: 5,000, 35,000 (45 %), 45,000 mg/L (35 %)
# Blind tests (not used for fitting): BW 2,000 mg/L 1 stage; SW 15,000 and 35,000 (40 %).
#
# Toray DS2 keeps the ratio of every strong ion's passage to Na constant over the
# whole TDS range; Na passage rises with salinity.  In ro_engine.py:
#   sigma_i = 1 - f_i * (1 - 0.9995)          (f_i = permeability vs Na, constant)
#   charged ions x ((pi_wall + pi_c)/(1 + pi_c))^n      ("salt_salinity_n")
#   SiO2, B have their own exponents in the same expression
#   strong-ion passage x exp(k*(pH - 7.5)) above pH 7.5       ("salt_ph_k", BW)
#   permeate HCO3/CO3/pH from CO2 + electroneutrality (no fitted factor)
# Values marked (*) had no feed in the calibration runs.
# ---------------------------------------------------------------------------
_SIGMA_REF = 0.9995

BW_F_REL = {
    "Na": 1.00000,
    "Cl": 0.81902,
    "K": 1.05149,
    "Ca": 0.81151,
    "Mg": 0.21524,
    "Sr": 0.81151,
    "Ba": 0.81151,
    "Fe": 0.81151,
    "Mn": 0.81151,
    "SO4": 0.28643,
    "NO3": 8.54708,
    "F": 3.72613,
    "SiO2": 1.80294,
    "NH4": 1.20000,
    "Br": 1.00000,
    "PO4": 0.20000,
    "Al": 0.20000,
    "HCO3": 1.20000,
}
SW_F_REL = {
    "Na": 1.00000,
    "Cl": 0.93121,
    "K": 1.39974,
    "Ca": 0.25811,
    "Mg": 0.25820,
    "Sr": 0.25811,
    "Ba": 0.25811,
    "Fe": 0.25811,
    "Mn": 0.25811,
    "SO4": 0.29173,
    "NO3": 1.56514,
    "F": 1.56157,
    "SiO2": 1.62502,
    "NH4": 1.20000,
    "Br": 1.00000,
    "PO4": 0.20000,
    "Al": 0.20000,
    "HCO3": 1.20000,
}
# (*) not calibrated: Sr/Ba/Fe/Mn (= Ca), NH4, Br, PO4, Al; HCO3 used only if no CO2 in feed

def _sigma_table(f_rel: Dict[str, float], boron_sigma: float) -> Dict[str, float]:
    tbl = {ion: 1.0 - f * (1.0 - _SIGMA_REF) for ion, f in f_rel.items()}
    tbl["B"] = boron_sigma   # neutral B(OH)3
    tbl["CO2"] = 0.0         # dissolved gas passes freely
    tbl["CO3"] = 1.0         # permeate CO3 is set by carbonate equilibrium
    return tbl

BW_SIGMA = _sigma_table(BW_F_REL, boron_sigma=0.887288)
SW_SIGMA = _sigma_table(SW_F_REL, boron_sigma=0.976404)

# Family parameters.
#   A_salinity       : A x 1/(1 + (pi_wall/pi0)^m)  (fitted on DS2 element flux / NDP)
#   salt_salinity_n  : see above (SW fit is effectively exp(0.0096 * pi_wall))
#   dp_factor        : x Schock-Miquel pressure drop (DS2 element dP)
#   k_factor         : x mass-transfer coefficient (DS2 element beta)
#   E_Aw/E_B/ion_E   : temperature constants (<= 25 C, > 25 C), K. v5: fitted on DS2
#                      new-membrane runs at 15 and 35 C (BW 2,000 mg/L; SW 35,000 mg/L);
#                      ion_E is relative to Na.
#   spi / flux decline: ageing, DS2 convention: B x (1+SPI)^age, A x (1-decline)^age.
#                      Decline reproduces the DS2 flow allowance falling 0.923 -> 0.848 (BW)
#                      and 0.956 -> 0.880 (SW) over 3 yr. Pass flow_factor = DS2 allowance
#                      of the NEW membrane for the water type (age 0 value).
FAMILY_PARAMS = {
    "BWRO": {
        "E_Aw_over_R": (3302.0, 2746.0),
        "E_B_over_R": (5275.0, 4747.0),
        "ion_E_over_R": {"Ca": (-61, 52), "Mg": (-45, 9), "Cl": (-89, 102), "SO4": (-69, 46), "SiO2": (-530, -897), "K": (-50, 70), "NO3": (63, 352), "F": (-6, 166), "B": (418, 650)},
        "A_salinity": (71.0041, 1.5341),
        "salt_salinity_n": {"Na": 0.435343, "pi_c": 0.098137, "SiO2": 0.099447, "B": 0.063946},
        "salt_ph_k": (0.2700, 7.5),
        "dp_factor": 0.3744,
        "k_factor": 1.0299,
        "spi_pct_per_yr": 10.0,
        "flux_decline_pct_per_yr": 2.790,
    },
    "SWRO": {
        "E_Aw_over_R": (2889.0, 2468.0),
        "E_B_over_R": (5791.0, 5309.0),
        "ion_E_over_R": {"Ca": (35, -73), "Mg": (27, -76), "K": (-4, 28), "Sr": (-21, -3), "Cl": (-4, -1), "SO4": (-22, -23), "SiO2": (107, 193), "B": (1592, 1370), "NO3": (5, 29), "F": (59, 50)},
        "A_salinity": (192.3769, 0.7133),
        "salt_salinity_n": {"Na": 1007.866632, "pi_c": 105106.747766, "SiO2": 705.504687, "B": -287.594436},
        "salt_ph_k": None,
        "dp_factor": 0.5829,
        "k_factor": 1.2069,
        "spi_pct_per_yr": 7.0,
        "flux_decline_pct_per_yr": 2.720,
    },
}

class MembraneDatabase:
    # RO/NF Elements
    RO_MEMBRANES = {
        "BW30-400": {
            "type": "BWRO",
            "manufacturer": "DuPont",
            "active_area_m2": 37.2, # 400 sq ft
            "permeability_A": 3.5357,  # v4: datasheet fit x DS2 basis (Toray ratio); v3.1 3.4017
            "permeability_B": 3.2529e-08,  # v4: datasheet fit x DS2 basis (Toray ratio); v3.1 3.5473e-08
            "feed_spacer_mil": 34,
            "max_pressure_bar": 41.0,
            "max_feed_flow_m3h": 15.9,
            "min_conc_flow_m3h": 3.0,
            "max_recovery_pct": 15.0,
            "length_m": 1.016,
            "diameter_m": 0.201,
            # Ion-specific Spiegler-Kedem Reflection Coefficients (sigma)
            "sigma": dict(BW_SIGMA)
        },
        "SW30HRLE-400": {
            "type": "SWRO",
            "manufacturer": "DuPont",
            "active_area_m2": 37.2,
            "permeability_A": 1.6371,  # v4: datasheet fit x DS2 basis (Toray ratio); v3.1 1.8700
            "permeability_B": 9.0360e-09,  # v4: datasheet fit x DS2 basis (Toray ratio); v3.1 8.0961e-09
            "feed_spacer_mil": 28,
            "max_pressure_bar": 82.7,
            "max_feed_flow_m3h": 17.0,
            "min_conc_flow_m3h": 3.0,
            "max_recovery_pct": 12.0,
            "length_m": 1.016,
            "diameter_m": 0.201,
            "sigma": dict(SW_SIGMA)
        },
        "CPA5-LD": {
            "type": "BWRO",
            "manufacturer": "Hydranautics",
            "active_area_m2": 37.2,
            "permeability_A": 3.5260,  # v4: datasheet fit x DS2 basis (Toray ratio); v3.1 3.3975
            "permeability_B": 2.1678e-08,  # v4: datasheet fit x DS2 basis (Toray ratio); v3.1 2.1895e-08
            "feed_spacer_mil": 34,
            "max_pressure_bar": 41.4,
            "max_feed_flow_m3h": 17.0,
            "min_conc_flow_m3h": 3.2,
            "max_recovery_pct": 15.0,
            "length_m": 1.016,
            "diameter_m": 0.201,
            "sigma": dict(BW_SIGMA)
        },
"HPA-4040": {
            "type": "BWRO",
            "manufacturer": "Permionics",
            "description": "Low fouling RO element with extended area for brackish water",
            "size": "4x40",
            "active_area_m2": 9.3,         # 100 ft2
            "permeability_A": 3.2096,  # v4: datasheet fit x DS2 basis (Toray ratio); v3.1 3.0900
            "permeability_B": 2.4029e-08,  # v4: datasheet fit x DS2 basis (Toray ratio); v3.1 2.6133e-08
            "feed_spacer_mil": 31,         # typical for 4040 BWRO
            "max_pressure_bar": 41.4,      # 600 psi
            "max_feed_flow_m3h": 4.09,     # 18 gpm
            "min_conc_flow_m3h": 0.91,     # 4 gpm
            "max_recovery_pct": 15.0,
            "max_dp_per_element_bar": 1.03, # 15 psi
            "length_m": 1.016,             # 40 inches
            "diameter_m": 0.102,           # 4 inches
            "nominal_rejection": 0.996,
            "min_rejection": 0.995,
            "max_temp_c": 45.0,
            "ph_range": [2.0, 11.0],
            "cip_ph_range": [1.0, 13.0],
            "max_turbidity_ntu": 1.0,
            "max_sdi_15": 5.0,
            "max_chlorine_mgL": 0.1,
            "test_conditions": {
                "solute_ppm": 2000,
                "pressure_bar": 15.5,
                "temp_c": 25.0,
                "recovery_pct": 15.0
            },
            # Design flux guidelines by water source (from datasheet Page 2)
            # Values in LMH (converted from GFD: 1 GFD = 1.6985 LMH)
            "design_flux_guidelines": {
                "wastewater_conventional":   {"sdi_max": 5, "flux_min_lmh": 13.6, "flux_max_lmh": 20.4},
                "wastewater_uf_pretreated":  {"sdi_max": 3, "flux_min_lmh": 17.0, "flux_max_lmh": 23.8},
                "seawater_open_intake":      {"sdi_max": 5, "flux_min_lmh": 11.9, "flux_max_lmh": 17.0},
                "seawater_beach_well":       {"sdi_max": 3, "flux_min_lmh": 13.6, "flux_max_lmh": 20.4},
                "surface_water_sdi5":        {"sdi_max": 5, "flux_min_lmh": 20.4, "flux_max_lmh": 27.2},
                "surface_water_sdi3":        {"sdi_max": 3, "flux_min_lmh": 22.1, "flux_max_lmh": 28.9},
                "well_water":                {"sdi_max": 3, "flux_min_lmh": 22.1, "flux_max_lmh": 28.9},
                "ro_permeate":               {"sdi_max": 1, "flux_min_lmh": 35.7, "flux_max_lmh": 51.0}
            },
            # Saturation limits from datasheet
            "saturation_limits": {
                "LSI": 1.5,           # with antiscalant
                "SDSI": 0.5,
                "CaSO4_pct": 230,
                "SrSO4_pct": 800,
                "BaSO4_pct": 6000,
                "SiO2_pct": 100
            },
            "sigma": dict(BW_SIGMA)
        },
        "HPA-RO-8040-LF-WW": {
            "type": "BWRO",
            "manufacturer": "Permionics",
            "active_area_m2": 37.2,
            "permeability_A": 3.3484,  # v4: datasheet fit x DS2 basis (Toray ratio); v3.1 3.2250
            "permeability_B": 1.7982e-08,  # v4: datasheet fit x DS2 basis (Toray ratio); v3.1 1.9703e-08
            "feed_spacer_mil": 31,
            "max_pressure_bar": 41.4,
            "max_feed_flow_m3h": 16.0,
            "min_conc_flow_m3h": 4.5,
            "max_recovery_pct": 15.0,
            "length_m": 1.016,
            "diameter_m": 0.201,
            "nominal_rejection": 0.997,
            "min_rejection": 0.996,
            "flags": ['LF'],
            "max_temp_c": 45.0,
            "ph_range": [2.0, 11.0],
            "cip_ph_range": [1.0, 13.0],
            "max_turbidity_ntu": 1.0,
            "max_sdi_15": 5.0,
            "max_chlorine_mgL": 0.1,
            "design_flux_guidelines": {
                "wastewater_conventional": {'sdi_max': 5, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "wastewater_uf_pretreated": {'sdi_max': 3, 'flux_min_lmh': 17.0, 'flux_max_lmh': 23.8},
                "seawater_open_intake": {'sdi_max': 5, 'flux_min_lmh': 11.9, 'flux_max_lmh': 17.0},
                "seawater_beach_well": {'sdi_max': 3, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "surface_water_sdi5": {'sdi_max': 5, 'flux_min_lmh': 20.4, 'flux_max_lmh': 27.2},
                "surface_water_sdi3": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "well_water": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "ro_permeate": {'sdi_max': 1, 'flux_min_lmh': 35.7, 'flux_max_lmh': 51.0},
            },
            "saturation_limits": {
                "LSI": 1.5,
                "SDSI": 0.5,
                "CaSO4_pct": 230,
                "SrSO4_pct": 800,
                "BaSO4_pct": 6000,
                "SiO2_pct": 100,
            },
            "sigma": dict(BW_SIGMA),
        },
        "HPA-RO-8040": {
            "type": "BWRO",
            "manufacturer": "Permionics",
            "active_area_m2": 37.2,
            "permeability_A": 3.5000,  # v4: datasheet fit x DS2 basis (Toray ratio); v3.1 3.3727
            "permeability_B": 1.8747e-08,  # v4: datasheet fit x DS2 basis (Toray ratio); v3.1 2.0548e-08
            "feed_spacer_mil": 31,
            "max_pressure_bar": 41.4,
            "max_feed_flow_m3h": 16.0,
            "min_conc_flow_m3h": 4.5,
            "max_recovery_pct": 15.0,
            "length_m": 1.016,
            "diameter_m": 0.201,
            "nominal_rejection": 0.997,
            "min_rejection": 0.996,
            "flags": [],
            "max_temp_c": 45.0,
            "ph_range": [2.0, 11.0],
            "cip_ph_range": [1.0, 13.0],
            "max_turbidity_ntu": 1.0,
            "max_sdi_15": 5.0,
            "max_chlorine_mgL": 0.1,
            "design_flux_guidelines": {
                "wastewater_conventional": {'sdi_max': 5, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "wastewater_uf_pretreated": {'sdi_max': 3, 'flux_min_lmh': 17.0, 'flux_max_lmh': 23.8},
                "seawater_open_intake": {'sdi_max': 5, 'flux_min_lmh': 11.9, 'flux_max_lmh': 17.0},
                "seawater_beach_well": {'sdi_max': 3, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "surface_water_sdi5": {'sdi_max': 5, 'flux_min_lmh': 20.4, 'flux_max_lmh': 27.2},
                "surface_water_sdi3": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "well_water": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "ro_permeate": {'sdi_max': 1, 'flux_min_lmh': 35.7, 'flux_max_lmh': 51.0},
            },
            "saturation_limits": {
                "LSI": 1.5,
                "SDSI": 0.5,
                "CaSO4_pct": 230,
                "SrSO4_pct": 800,
                "BaSO4_pct": 6000,
                "SiO2_pct": 100,
            },
            "sigma": dict(BW_SIGMA),
        },
        "HPA-RO-LPM-8040-440": {
            "type": "BWRO",
            "manufacturer": "Permionics",
            "active_area_m2": 40.9,
            "permeability_A": 3.482,
            "permeability_B": 2.54e-08,
            "feed_spacer_mil": 28,
            "max_pressure_bar": 41.4,
            "max_feed_flow_m3h": 16.0,
            "min_conc_flow_m3h": 4.5,
            "max_recovery_pct": 15.0,
            "length_m": 1.016,
            "diameter_m": 0.201,
            "nominal_rejection": 0.997,
            "min_rejection": 0.996,
            "flags": ['LPM'],
            "max_temp_c": 45.0,
            "ph_range": [2.0, 11.0],
            "cip_ph_range": [1.0, 13.0],
            "max_turbidity_ntu": 1.0,
            "max_sdi_15": 5.0,
            "max_chlorine_mgL": 0.1,
            "design_flux_guidelines": {
                "wastewater_conventional": {'sdi_max': 5, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "wastewater_uf_pretreated": {'sdi_max': 3, 'flux_min_lmh': 17.0, 'flux_max_lmh': 23.8},
                "seawater_open_intake": {'sdi_max': 5, 'flux_min_lmh': 11.9, 'flux_max_lmh': 17.0},
                "seawater_beach_well": {'sdi_max': 3, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "surface_water_sdi5": {'sdi_max': 5, 'flux_min_lmh': 20.4, 'flux_max_lmh': 27.2},
                "surface_water_sdi3": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "well_water": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "ro_permeate": {'sdi_max': 1, 'flux_min_lmh': 35.7, 'flux_max_lmh': 51.0},
            },
            "saturation_limits": {
                "LSI": 1.5,
                "SDSI": 0.5,
                "CaSO4_pct": 230,
                "SrSO4_pct": 800,
                "BaSO4_pct": 6000,
                "SiO2_pct": 100,
            },
            "sigma": dict(BW_SIGMA),
        },
        "HPARO-8040-BW-400": {
            "type": "BWRO",
            "manufacturer": "Permionics",
            "active_area_m2": 37.2,
            "permeability_A": 3.5268,  # v4: datasheet fit x DS2 basis (Toray ratio); v3.1 3.3988
            "permeability_B": 1.8882e-08,  # v4: datasheet fit x DS2 basis (Toray ratio); v3.1 2.0697e-08
            "feed_spacer_mil": 31,
            "max_pressure_bar": 41.4,
            "max_feed_flow_m3h": 16.0,
            "min_conc_flow_m3h": 4.5,
            "max_recovery_pct": 15.0,
            "length_m": 1.016,
            "diameter_m": 0.201,
            "nominal_rejection": 0.997,
            "min_rejection": 0.996,
            "flags": [],
            "max_temp_c": 45.0,
            "ph_range": [2.0, 11.0],
            "cip_ph_range": [1.0, 13.0],
            "max_turbidity_ntu": 1.0,
            "max_sdi_15": 5.0,
            "max_chlorine_mgL": 0.1,
            "design_flux_guidelines": {
                "wastewater_conventional": {'sdi_max': 5, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "wastewater_uf_pretreated": {'sdi_max': 3, 'flux_min_lmh': 17.0, 'flux_max_lmh': 23.8},
                "seawater_open_intake": {'sdi_max': 5, 'flux_min_lmh': 11.9, 'flux_max_lmh': 17.0},
                "seawater_beach_well": {'sdi_max': 3, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "surface_water_sdi5": {'sdi_max': 5, 'flux_min_lmh': 20.4, 'flux_max_lmh': 27.2},
                "surface_water_sdi3": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "well_water": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "ro_permeate": {'sdi_max': 1, 'flux_min_lmh': 35.7, 'flux_max_lmh': 51.0},
            },
            "saturation_limits": {
                "LSI": 1.5,
                "SDSI": 0.5,
                "CaSO4_pct": 230,
                "SrSO4_pct": 800,
                "BaSO4_pct": 6000,
                "SiO2_pct": 100,
            },
            "sigma": dict(BW_SIGMA),
        },
        "HPARO-8040-LF": {
            "type": "BWRO",
            "manufacturer": "Permionics",
            "active_area_m2": 37.2,
            "permeability_A": 3.213,
            "permeability_B": 1.42e-08,
            "feed_spacer_mil": 31,
            "max_pressure_bar": 41.4,
            "max_feed_flow_m3h": 16.0,
            "min_conc_flow_m3h": 4.5,
            "max_recovery_pct": 15.0,
            "length_m": 1.016,
            "diameter_m": 0.201,
            "nominal_rejection": 0.998,
            "min_rejection": 0.997,
            "flags": ['LF'],
            "max_temp_c": 45.0,
            "ph_range": [2.0, 11.0],
            "cip_ph_range": [1.0, 13.0],
            "max_turbidity_ntu": 1.0,
            "max_sdi_15": 5.0,
            "max_chlorine_mgL": 0.1,
            "design_flux_guidelines": {
                "wastewater_conventional": {'sdi_max': 5, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "wastewater_uf_pretreated": {'sdi_max': 3, 'flux_min_lmh': 17.0, 'flux_max_lmh': 23.8},
                "seawater_open_intake": {'sdi_max': 5, 'flux_min_lmh': 11.9, 'flux_max_lmh': 17.0},
                "seawater_beach_well": {'sdi_max': 3, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "surface_water_sdi5": {'sdi_max': 5, 'flux_min_lmh': 20.4, 'flux_max_lmh': 27.2},
                "surface_water_sdi3": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "well_water": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "ro_permeate": {'sdi_max': 1, 'flux_min_lmh': 35.7, 'flux_max_lmh': 51.0},
            },
            "saturation_limits": {
                "LSI": 1.5,
                "SDSI": 0.5,
                "CaSO4_pct": 230,
                "SrSO4_pct": 800,
                "BaSO4_pct": 6000,
                "SiO2_pct": 100,
            },
            "sigma": dict(BW_SIGMA),
        },
        "HPARO-8040-LF2": {
            "type": "BWRO",
            "manufacturer": "Permionics",
            "active_area_m2": 37.2,
            "permeability_A": 3.52,
            "permeability_B": 1.55e-08,
            "feed_spacer_mil": 31,
            "max_pressure_bar": 41.4,
            "max_feed_flow_m3h": 16.0,
            "min_conc_flow_m3h": 4.5,
            "max_recovery_pct": 15.0,
            "length_m": 1.016,
            "diameter_m": 0.201,
            "nominal_rejection": 0.998,
            "min_rejection": 0.997,
            "flags": ['LF'],
            "max_temp_c": 45.0,
            "ph_range": [2.0, 11.0],
            "cip_ph_range": [1.0, 13.0],
            "max_turbidity_ntu": 1.0,
            "max_sdi_15": 5.0,
            "max_chlorine_mgL": 0.1,
            "design_flux_guidelines": {
                "wastewater_conventional": {'sdi_max': 5, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "wastewater_uf_pretreated": {'sdi_max': 3, 'flux_min_lmh': 17.0, 'flux_max_lmh': 23.8},
                "seawater_open_intake": {'sdi_max': 5, 'flux_min_lmh': 11.9, 'flux_max_lmh': 17.0},
                "seawater_beach_well": {'sdi_max': 3, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "surface_water_sdi5": {'sdi_max': 5, 'flux_min_lmh': 20.4, 'flux_max_lmh': 27.2},
                "surface_water_sdi3": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "well_water": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "ro_permeate": {'sdi_max': 1, 'flux_min_lmh': 35.7, 'flux_max_lmh': 51.0},
            },
            "saturation_limits": {
                "LSI": 1.5,
                "SDSI": 0.5,
                "CaSO4_pct": 230,
                "SrSO4_pct": 800,
                "BaSO4_pct": 6000,
                "SiO2_pct": 100,
            },
            "sigma": dict(BW_SIGMA),
        },
        "HPARO-8040-PRO-400": {
            "type": "BWRO",
            "manufacturer": "Permionics",
            "active_area_m2": 37.2,
            "permeability_A": 3.229,
            "permeability_B": 3.19e-08,
            "feed_spacer_mil": 31,
            "max_pressure_bar": 41.4,
            "max_feed_flow_m3h": 16.0,
            "min_conc_flow_m3h": 4.5,
            "max_recovery_pct": 15.0,
            "length_m": 1.016,
            "diameter_m": 0.201,
            "nominal_rejection": 0.996,
            "min_rejection": 0.995,
            "flags": [],
            "max_temp_c": 45.0,
            "ph_range": [2.0, 11.0],
            "cip_ph_range": [1.0, 13.0],
            "max_turbidity_ntu": 1.0,
            "max_sdi_15": 5.0,
            "max_chlorine_mgL": 0.1,
            "design_flux_guidelines": {
                "wastewater_conventional": {'sdi_max': 5, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "wastewater_uf_pretreated": {'sdi_max': 3, 'flux_min_lmh': 17.0, 'flux_max_lmh': 23.8},
                "seawater_open_intake": {'sdi_max': 5, 'flux_min_lmh': 11.9, 'flux_max_lmh': 17.0},
                "seawater_beach_well": {'sdi_max': 3, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "surface_water_sdi5": {'sdi_max': 5, 'flux_min_lmh': 20.4, 'flux_max_lmh': 27.2},
                "surface_water_sdi3": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "well_water": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "ro_permeate": {'sdi_max': 1, 'flux_min_lmh': 35.7, 'flux_max_lmh': 51.0},
            },
            "saturation_limits": {
                "LSI": 1.5,
                "SDSI": 0.5,
                "CaSO4_pct": 230,
                "SrSO4_pct": 800,
                "BaSO4_pct": 6000,
                "SiO2_pct": 100,
            },
            "sigma": dict(BW_SIGMA),
        },
        "SWRO-8040-400": {
            "type": "SWRO",
            "manufacturer": "Permionics",
            "active_area_m2": 37.5,
            "permeability_A": 1.4004,  # v4: datasheet fit x DS2 basis (Toray ratio); v3.1 1.5961
            "permeability_B": 1.0221e-08,  # v4: datasheet fit x DS2 basis (Toray ratio); v3.1 9.0308e-09
            "feed_spacer_mil": 28,
            "max_pressure_bar": 82.7,  # was 55.2 (BW limit); confirm vs Permionics SW datasheet
            "max_feed_flow_m3h": 16.0,
            "min_conc_flow_m3h": 4.5,
            "max_recovery_pct": 15.0,
            "length_m": 1.016,
            "diameter_m": 0.201,
            "nominal_rejection": 0.998,
            "min_rejection": 0.997,
            "flags": [],
            "max_temp_c": 45.0,
            "ph_range": [2.0, 11.0],
            "cip_ph_range": [1.0, 13.0],
            "max_turbidity_ntu": 1.0,
            "max_sdi_15": 5.0,
            "max_chlorine_mgL": 0.1,
            "design_flux_guidelines": {
                "wastewater_conventional": {'sdi_max': 5, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "wastewater_uf_pretreated": {'sdi_max': 3, 'flux_min_lmh': 17.0, 'flux_max_lmh': 23.8},
                "seawater_open_intake": {'sdi_max': 5, 'flux_min_lmh': 11.9, 'flux_max_lmh': 17.0},
                "seawater_beach_well": {'sdi_max': 3, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "surface_water_sdi5": {'sdi_max': 5, 'flux_min_lmh': 20.4, 'flux_max_lmh': 27.2},
                "surface_water_sdi3": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "well_water": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "ro_permeate": {'sdi_max': 1, 'flux_min_lmh': 35.7, 'flux_max_lmh': 51.0},
            },
            "saturation_limits": {
                "LSI": 1.5,
                "SDSI": 0.5,
                "CaSO4_pct": 230,
                "SrSO4_pct": 800,
                "BaSO4_pct": 6000,
                "SiO2_pct": 100,
            },
            "sigma": dict(SW_SIGMA),
        },
        "SWRO-FR-8040-400": {
            "type": "SWRO",
            "manufacturer": "Permionics",
            "active_area_m2": 37.2,
            "permeability_A": 1.3294,  # v4: datasheet fit x DS2 basis (Toray ratio); v3.1 1.5265
            "permeability_B": 1.1440e-08,  # v4: datasheet fit x DS2 basis (Toray ratio); v3.1 9.9856e-09
            "feed_spacer_mil": 34,
            "max_pressure_bar": 82.7,  # was 55.2 (BW limit); confirm vs Permionics SW datasheet
            "max_feed_flow_m3h": 16.0,
            "min_conc_flow_m3h": 4.5,
            "max_recovery_pct": 15.0,
            "length_m": 1.016,
            "diameter_m": 0.201,
            "nominal_rejection": 0.998,
            "min_rejection": 0.997,
            "flags": ['FR'],
            "max_temp_c": 45.0,
            "ph_range": [2.0, 11.0],
            "cip_ph_range": [1.0, 13.0],
            "max_turbidity_ntu": 1.0,
            "max_sdi_15": 5.0,
            "max_chlorine_mgL": 0.1,
            "design_flux_guidelines": {
                "wastewater_conventional": {'sdi_max': 5, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "wastewater_uf_pretreated": {'sdi_max': 3, 'flux_min_lmh': 17.0, 'flux_max_lmh': 23.8},
                "seawater_open_intake": {'sdi_max': 5, 'flux_min_lmh': 11.9, 'flux_max_lmh': 17.0},
                "seawater_beach_well": {'sdi_max': 3, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "surface_water_sdi5": {'sdi_max': 5, 'flux_min_lmh': 20.4, 'flux_max_lmh': 27.2},
                "surface_water_sdi3": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "well_water": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "ro_permeate": {'sdi_max': 1, 'flux_min_lmh': 35.7, 'flux_max_lmh': 51.0},
            },
            "saturation_limits": {
                "LSI": 1.5,
                "SDSI": 0.5,
                "CaSO4_pct": 230,
                "SrSO4_pct": 800,
                "BaSO4_pct": 6000,
                "SiO2_pct": 100,
            },
            "sigma": dict(SW_SIGMA),
        },
        "SWRO-HLE-8040-400": {
            "type": "SWRO",
            "manufacturer": "Permionics",
            "active_area_m2": 37.2,
            "permeability_A": 1.5239,  # v4: datasheet fit x DS2 basis (Toray ratio); v3.1 1.7388
            "permeability_B": 1.1083e-08,  # v4: datasheet fit x DS2 basis (Toray ratio); v3.1 9.7906e-09
            "feed_spacer_mil": 28,
            "max_pressure_bar": 82.7,  # was 55.2 (BW limit); confirm vs Permionics SW datasheet
            "max_feed_flow_m3h": 16.0,
            "min_conc_flow_m3h": 4.5,
            "max_recovery_pct": 15.0,
            "length_m": 1.016,
            "diameter_m": 0.201,
            "nominal_rejection": 0.998,
            "min_rejection": 0.997,
            "flags": ['HLE'],
            "max_temp_c": 45.0,
            "ph_range": [2.0, 11.0],
            "cip_ph_range": [1.0, 13.0],
            "max_turbidity_ntu": 1.0,
            "max_sdi_15": 5.0,
            "max_chlorine_mgL": 0.1,
            "design_flux_guidelines": {
                "wastewater_conventional": {'sdi_max': 5, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "wastewater_uf_pretreated": {'sdi_max': 3, 'flux_min_lmh': 17.0, 'flux_max_lmh': 23.8},
                "seawater_open_intake": {'sdi_max': 5, 'flux_min_lmh': 11.9, 'flux_max_lmh': 17.0},
                "seawater_beach_well": {'sdi_max': 3, 'flux_min_lmh': 13.6, 'flux_max_lmh': 20.4},
                "surface_water_sdi5": {'sdi_max': 5, 'flux_min_lmh': 20.4, 'flux_max_lmh': 27.2},
                "surface_water_sdi3": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "well_water": {'sdi_max': 3, 'flux_min_lmh': 22.1, 'flux_max_lmh': 28.9},
                "ro_permeate": {'sdi_max': 1, 'flux_min_lmh': 35.7, 'flux_max_lmh': 51.0},
            },
            "saturation_limits": {
                "LSI": 1.5,
                "SDSI": 0.5,
                "CaSO4_pct": 230,
                "SrSO4_pct": 800,
                "BaSO4_pct": 6000,
                "SiO2_pct": 100,
            },
            "sigma": dict(SW_SIGMA),
        },
        # --- Calibration reference elements (Toray), fitted to Toray DS2 at age 0 ---
        "TM720D-400": {
            "type": "BWRO",
            "manufacturer": "Toray (calibration reference)",
            "active_area_m2": 37.3,
            "permeability_A": 3.65196,        # LMH/bar at 25 C, new element
            "permeability_B": 1.23422e-08,   # m/s at 25 C, new element (Na)
            "feed_spacer_mil": 28,          # effective value that reproduces DS2 beta
            "max_pressure_bar": 41.4,
            "max_feed_flow_m3h": 17.0,
            "min_conc_flow_m3h": 3.4,
            "max_recovery_pct": 15.0,
            "length_m": 1.016,
            "diameter_m": 0.201,
            "sigma": dict(BW_SIGMA),
        },
        "TM820M-400": {
            "type": "SWRO",
            "manufacturer": "Toray (calibration reference)",
            "active_area_m2": 37.3,
            "permeability_A": 1.53740,
            "permeability_B": 8.28489e-09,
            "feed_spacer_mil": 31,
            "max_pressure_bar": 82.7,
            "max_feed_flow_m3h": 17.0,
            "min_conc_flow_m3h": 3.4,
            "max_recovery_pct": 15.0,
            "length_m": 1.016,
            "diameter_m": 0.201,
            "sigma": dict(SW_SIGMA),
        },
    }

    # UF Modules
    UF_MODULES = {
        "PERMA-UF-i0875s40": {
            "type": "UF",
            "manufacturer": "Permionics",
            "membrane_area_m2": 40.0,
            "fiber_id_mm": 0.8,
            "max_filtration_flux_lmh": 200.0,
            "design_flux_lmh": 40.0,
            "clean_tmp_max_bar": 1.2,
            "fouled_tmp_max_bar": 2.1,
            "max_tmp_bar": 2.5,
            "backwash_flux_lmh": 150.0,
            "backwash_duration_s": 45,
            "air_scour_flow_m3h": 12.0,
            "min_forward_flush_m3h": 1.5,
            "permeability_Lp20": 400.0,
            "unit_cost_inr": 100000.0,
            "feed_pump_kw_per_module": 0.75,
            "backwash_pump_kw_per_module": 1.1,
        },
        "PERMA-UF-iH0860": {
            "type": "UF",
            "manufacturer": "Permionics",
            "membrane_area_m2": 40.0,
            "fiber_id_mm": 0.8,
            "max_filtration_flux_lmh": 200.0,
            "design_flux_lmh": 40.0,
            "clean_tmp_max_bar": 1.2,
            "fouled_tmp_max_bar": 2.1,
            "max_tmp_bar": 2.5,
            "backwash_flux_lmh": 150.0,
            "backwash_duration_s": 45,
            "air_scour_flow_m3h": 12.0,
            "min_forward_flush_m3h": 1.5,
            "permeability_Lp20": 400.0,
            "unit_cost_inr": 100000.0,
            "feed_pump_kw_per_module": 0.75,
            "backwash_pump_kw_per_module": 1.1,
        },
        "PERMA-UF-0697": {
            "type": "UF",
            "manufacturer": "Permionics",
            "membrane_area_m2": 50.0,
            "fiber_id_mm": 0.8,
            "max_filtration_flux_lmh": 120.0,
            "design_flux_lmh": 30.0,
            "clean_tmp_max_bar": 1.2,
            "fouled_tmp_max_bar": 2.1,
            "max_tmp_bar": 2.5,
            "backwash_flux_lmh": 150.0,
            "backwash_duration_s": 45,
            "air_scour_flow_m3h": 12.0,
            "min_forward_flush_m3h": 1.5,
            "permeability_Lp20": 400.0,
            "unit_cost_inr": 100000.0,
            "feed_pump_kw_per_module": 0.75,
            "backwash_pump_kw_per_module": 1.1,
        },
        "PERMA-UF-i1066": {
            "type": "UF",
            "manufacturer": "Permionics",
            "membrane_area_m2": 50.0,
            "fiber_id_mm": 0.8,
            "max_filtration_flux_lmh": 200.0,
            "design_flux_lmh": 40.0,
            "clean_tmp_max_bar": 1.2,
            "fouled_tmp_max_bar": 2.1,
            "max_tmp_bar": 2.5,
            "backwash_flux_lmh": 150.0,
            "backwash_duration_s": 45,
            "air_scour_flow_m3h": 12.0,
            "min_forward_flush_m3h": 1.5,
            "permeability_Lp20": 400.0,
            "unit_cost_inr": 100000.0,
            "feed_pump_kw_per_module": 0.75,
            "backwash_pump_kw_per_module": 1.1,
        },
        "PERMA-UF-2860T": {
            "type": "UF",
            "manufacturer": "Permionics",
            "membrane_area_m2": 51.0,
            "fiber_id_mm": 0.8,
            "max_filtration_flux_lmh": 120.0,
            "design_flux_lmh": 35.0,
            "clean_tmp_max_bar": 1.2,
            "fouled_tmp_max_bar": 2.1,
            "max_tmp_bar": 2.5,
            "backwash_flux_lmh": 150.0,
            "backwash_duration_s": 45,
            "air_scour_flow_m3h": 12.0,
            "min_forward_flush_m3h": 1.5,
            "permeability_Lp20": 400.0,
            "unit_cost_inr": 100000.0,
            "feed_pump_kw_per_module": 0.75,
            "backwash_pump_kw_per_module": 1.1,
        },
        "PERMA-UF-i0975": {
            "type": "UF",
            "manufacturer": "Permionics",
            "membrane_area_m2": 55.0,
            "fiber_id_mm": 0.8,
            "max_filtration_flux_lmh": 200.0,
            "design_flux_lmh": 40.0,
            "clean_tmp_max_bar": 1.2,
            "fouled_tmp_max_bar": 2.1,
            "max_tmp_bar": 2.5,
            "backwash_flux_lmh": 150.0,
            "backwash_duration_s": 45,
            "air_scour_flow_m3h": 12.0,
            "min_forward_flush_m3h": 1.5,
            "permeability_Lp20": 400.0,
            "unit_cost_inr": 100000.0,
            "feed_pump_kw_per_module": 0.75,
            "backwash_pump_kw_per_module": 1.1,
        },
        "PERMA-UF-0776": {
            "type": "UF",
            "manufacturer": "Permionics",
            "membrane_area_m2": 56.0,
            "fiber_id_mm": 0.8,
            "max_filtration_flux_lmh": 135.0,
            "design_flux_lmh": 30.0,
            "clean_tmp_max_bar": 1.2,
            "fouled_tmp_max_bar": 2.1,
            "max_tmp_bar": 2.5,
            "backwash_flux_lmh": 150.0,
            "backwash_duration_s": 45,
            "air_scour_flow_m3h": 12.0,
            "min_forward_flush_m3h": 1.5,
            "permeability_Lp20": 400.0,
            "unit_cost_inr": 100000.0,
            "feed_pump_kw_per_module": 0.75,
            "backwash_pump_kw_per_module": 1.1,
        },
        "PERMA-UF-i1066X": {
            "type": "UF",
            "manufacturer": "Permionics",
            "membrane_area_m2": 60.0,
            "fiber_id_mm": 0.8,
            "max_filtration_flux_lmh": 200.0,
            "design_flux_lmh": 40.0,
            "clean_tmp_max_bar": 1.2,
            "fouled_tmp_max_bar": 2.1,
            "max_tmp_bar": 2.5,
            "backwash_flux_lmh": 150.0,
            "backwash_duration_s": 45,
            "air_scour_flow_m3h": 12.0,
            "min_forward_flush_m3h": 1.5,
            "permeability_Lp20": 400.0,
            "unit_cost_inr": 100000.0,
            "feed_pump_kw_per_module": 0.75,
            "backwash_pump_kw_per_module": 1.1,
        },
        "PERMA-UF-i0876s": {
            "type": "UF",
            "manufacturer": "Permionics",
            "membrane_area_m2": 64.0,
            "fiber_id_mm": 0.8,
            "max_filtration_flux_lmh": 200.0,
            "design_flux_lmh": 40.0,
            "clean_tmp_max_bar": 1.2,
            "fouled_tmp_max_bar": 2.1,
            "max_tmp_bar": 2.5,
            "backwash_flux_lmh": 150.0,
            "backwash_duration_s": 45,
            "air_scour_flow_m3h": 12.0,
            "min_forward_flush_m3h": 1.5,
            "permeability_Lp20": 400.0,
            "unit_cost_inr": 100000.0,
            "feed_pump_kw_per_module": 0.75,
            "backwash_pump_kw_per_module": 1.1,
        },
        "PERMA-UF-0697X": {
            "type": "UF",
            "manufacturer": "Permionics",
            "membrane_area_m2": 65.0,
            "fiber_id_mm": 0.8,
            "max_filtration_flux_lmh": 120.0,
            "design_flux_lmh": 30.0,
            "clean_tmp_max_bar": 1.2,
            "fouled_tmp_max_bar": 2.1,
            "max_tmp_bar": 2.5,
            "backwash_flux_lmh": 150.0,
            "backwash_duration_s": 45,
            "air_scour_flow_m3h": 12.0,
            "min_forward_flush_m3h": 1.5,
            "permeability_Lp20": 400.0,
            "unit_cost_inr": 100000.0,
            "feed_pump_kw_per_module": 0.75,
            "backwash_pump_kw_per_module": 1.1,
        },
        "PERMA-UF-iP70": {
            "type": "UF",
            "manufacturer": "Permionics",
            "membrane_area_m2": 70.0,
            "fiber_id_mm": 0.8,
            "max_filtration_flux_lmh": 200.0,
            "design_flux_lmh": 40.0,
            "clean_tmp_max_bar": 1.2,
            "fouled_tmp_max_bar": 2.1,
            "max_tmp_bar": 2.5,
            "backwash_flux_lmh": 150.0,
            "backwash_duration_s": 45,
            "air_scour_flow_m3h": 12.0,
            "min_forward_flush_m3h": 1.5,
            "permeability_Lp20": 400.0,
            "unit_cost_inr": 100000.0,
            "feed_pump_kw_per_module": 0.75,
            "backwash_pump_kw_per_module": 1.1,
        },
        "PERMA-UF-2880T": {
            "type": "UF",
            "manufacturer": "Permionics",
            "membrane_area_m2": 77.0,
            "fiber_id_mm": 0.8,
            "max_filtration_flux_lmh": 120.0,
            "design_flux_lmh": 35.0,
            "clean_tmp_max_bar": 1.2,
            "fouled_tmp_max_bar": 2.1,
            "max_tmp_bar": 2.5,
            "backwash_flux_lmh": 150.0,
            "backwash_duration_s": 45,
            "air_scour_flow_m3h": 12.0,
            "min_forward_flush_m3h": 1.5,
            "permeability_Lp20": 400.0,
            "unit_cost_inr": 100000.0,
            "feed_pump_kw_per_module": 0.75,
            "backwash_pump_kw_per_module": 1.1,
        },
        "PERMA-UF-2880": {
            "type": "UF",
            "manufacturer": "Permionics",
            "membrane_area_m2": 77.0,
            "fiber_id_mm": 0.8,
            "max_filtration_flux_lmh": 120.0,
            "design_flux_lmh": 30.0,
            "clean_tmp_max_bar": 1.2,
            "fouled_tmp_max_bar": 2.1,
            "max_tmp_bar": 2.5,
            "backwash_flux_lmh": 150.0,
            "backwash_duration_s": 45,
            "air_scour_flow_m3h": 12.0,
            "min_forward_flush_m3h": 1.5,
            "permeability_Lp20": 400.0,
            "unit_cost_inr": 100000.0,
            "feed_pump_kw_per_module": 0.75,
            "backwash_pump_kw_per_module": 1.1,
        },
        "PERMA-UF-P77": {
            "type": "UF",
            "manufacturer": "Permionics",
            "membrane_area_m2": 77.0,
            "fiber_id_mm": 0.8,
            "max_filtration_flux_lmh": 120.0,
            "design_flux_lmh": 30.0,
            "clean_tmp_max_bar": 1.2,
            "fouled_tmp_max_bar": 2.1,
            "max_tmp_bar": 2.5,
            "backwash_flux_lmh": 150.0,
            "backwash_duration_s": 45,
            "air_scour_flow_m3h": 12.0,
            "min_forward_flush_m3h": 1.5,
            "permeability_Lp20": 400.0,
            "unit_cost_inr": 100000.0,
            "feed_pump_kw_per_module": 0.75,
            "backwash_pump_kw_per_module": 1.1,
        },
        "PERMA-UF-2880X": {
            "type": "UF",
            "manufacturer": "Permionics",
            "membrane_area_m2": 80.0,
            "fiber_id_mm": 0.8,
            "max_filtration_flux_lmh": 120.0,
            "design_flux_lmh": 30.0,
            "clean_tmp_max_bar": 1.2,
            "fouled_tmp_max_bar": 2.1,
            "max_tmp_bar": 2.5,
            "backwash_flux_lmh": 150.0,
            "backwash_duration_s": 45,
            "air_scour_flow_m3h": 12.0,
            "min_forward_flush_m3h": 1.5,
            "permeability_Lp20": 400.0,
            "unit_cost_inr": 100000.0,
            "feed_pump_kw_per_module": 0.75,
            "backwash_pump_kw_per_module": 1.1,
        },
        "PERMA-UF-i1077": {
            "type": "UF",
            "manufacturer": "Permionics",
            "membrane_area_m2": 80.0,
            "fiber_id_mm": 0.8,
            "max_filtration_flux_lmh": 180.0,
            "design_flux_lmh": 50.0,
            "clean_tmp_max_bar": 1.2,
            "fouled_tmp_max_bar": 2.1,
            "max_tmp_bar": 2.5,
            "backwash_flux_lmh": 150.0,
            "backwash_duration_s": 45,
            "air_scour_flow_m3h": 12.0,
            "min_forward_flush_m3h": 1.5,
            "permeability_Lp20": 400.0,
            "unit_cost_inr": 100000.0,
            "feed_pump_kw_per_module": 0.75,
            "backwash_pump_kw_per_module": 1.1,
        },
        "PERMA-UF-iP80": {
            "type": "UF",
            "manufacturer": "Permionics",
            "membrane_area_m2": 80.0,
            "fiber_id_mm": 0.8,
            "max_filtration_flux_lmh": 200.0,
            "design_flux_lmh": 40.0,
            "clean_tmp_max_bar": 1.2,
            "fouled_tmp_max_bar": 2.1,
            "max_tmp_bar": 2.5,
            "backwash_flux_lmh": 150.0,
            "backwash_duration_s": 45,
            "air_scour_flow_m3h": 12.0,
            "min_forward_flush_m3h": 1.5,
            "permeability_Lp20": 400.0,
            "unit_cost_inr": 100000.0,
            "feed_pump_kw_per_module": 0.75,
            "backwash_pump_kw_per_module": 1.1,
        },
        "PERMA-UF-i1183": {
            "type": "UF",
            "manufacturer": "Permionics",
            "membrane_area_m2": 81.0,
            "fiber_id_mm": 0.8,
            "max_filtration_flux_lmh": 180.0,
            "design_flux_lmh": 50.0,
            "clean_tmp_max_bar": 1.2,
            "fouled_tmp_max_bar": 2.1,
            "max_tmp_bar": 2.5,
            "backwash_flux_lmh": 150.0,
            "backwash_duration_s": 45,
            "air_scour_flow_m3h": 12.0,
            "min_forward_flush_m3h": 1.5,
            "permeability_Lp20": 400.0,
            "unit_cost_inr": 100000.0,
            "feed_pump_kw_per_module": 0.75,
            "backwash_pump_kw_per_module": 1.1,
        },
        "PERMA-UF-1075T": {
            "type": "UF",
            "manufacturer": "Permionics",
            "membrane_area_m2": 120.0,
            "fiber_id_mm": 0.8,
            "max_filtration_flux_lmh": 135.0,
            "design_flux_lmh": 35.0,
            "clean_tmp_max_bar": 1.2,
            "fouled_tmp_max_bar": 2.1,
            "max_tmp_bar": 2.5,
            "backwash_flux_lmh": 150.0,
            "backwash_duration_s": 45,
            "air_scour_flow_m3h": 12.0,
            "min_forward_flush_m3h": 1.5,
            "permeability_Lp20": 400.0,
            "unit_cost_inr": 100000.0,
            "feed_pump_kw_per_module": 0.75,
            "backwash_pump_kw_per_module": 1.1,
        },
        "PERMA-UF-0992": {
            "type": "UF",
            "manufacturer": "Permionics",
            "membrane_area_m2": 60.0,
            "fiber_id_mm": 0.8,
            "max_filtration_flux_lmh": 180.0,
            "design_flux_lmh": 30.0,
            "clean_tmp_max_bar": 1.2,
            "fouled_tmp_max_bar": 2.1,
            "max_tmp_bar": 2.5,
            "backwash_flux_lmh": 150.0,
            "backwash_duration_s": 45,
            "air_scour_flow_m3h": 12.0,
            "min_forward_flush_m3h": 1.5,
            "permeability_Lp20": 400.0,
            "unit_cost_inr": 100000.0,
            "feed_pump_kw_per_module": 0.75,
            "backwash_pump_kw_per_module": 1.1,
        },
    }

    # v4 (13-Nov-2026): permeability_A/B of the catalogue elements below are fitted to
    # these datasheet ratings with the calibrated engine, then multiplied by the ratio
    # (DS2-calibrated value / datasheet-fitted value) found for the Toray reference
    # elements, so that every element is on the Toray DS2 projection basis:
    #   BWRO  A x 1.0411, B x 0.9530   (TM720D-400)
    #   SWRO  A x 1.1046, B x 0.8900   (TM820M-400)
    # Verified manufacturer datasheet ratings
    VERIFIED_DATASHEETS = {
        "TM720D-400": {
            "test_solution": "2,000 ppm NaCl", "test_pressure_psi": 225.0, "test_pressure_bar": 15.51,
            "test_recovery_pct": 15.0, "test_temp_c": 25.0, "permeate_flow_m3d": 41.6,
            "nominal_rejection_pct": 99.80, "min_rejection_pct": 99.50, "is_estimate": False
        },
        "TM820M-400": {
            "test_solution": "32,000 ppm NaCl", "test_pressure_psi": 800.0, "test_pressure_bar": 55.16,
            "test_recovery_pct": 8.0, "test_temp_c": 25.0, "permeate_flow_m3d": 26.5,
            "nominal_rejection_pct": 99.80, "min_rejection_pct": 99.50, "is_estimate": False
        },
        "BW30-400": {
            "test_solution": "2,000 ppm NaCl", "test_pressure_psi": 225.0, "test_pressure_bar": 15.51,
            "test_recovery_pct": 15.0, "test_temp_c": 25.0, "permeate_flow_m3d": 40.0,
            "nominal_rejection_pct": 99.50, "min_rejection_pct": 99.30, "is_estimate": False
        },
        "SW30HRLE-400": {
            "test_solution": "32,000 ppm NaCl", "test_pressure_psi": 800.0, "test_pressure_bar": 55.16,
            "test_recovery_pct": 8.0, "test_temp_c": 25.0, "permeate_flow_m3d": 28.4,
            "nominal_rejection_pct": 99.80, "min_rejection_pct": 99.65, "is_estimate": False
        },
        "CPA5-LD": {
            "test_solution": "1,500 ppm NaCl", "test_pressure_psi": 225.0, "test_pressure_bar": 15.51,
            "test_recovery_pct": 15.0, "test_temp_c": 25.0, "permeate_flow_m3d": 41.6,
            "nominal_rejection_pct": 99.70, "min_rejection_pct": 99.50, "is_estimate": False
        },
        "HPA-4040": {
            "test_solution": "2,000 ppm NaCl", "test_pressure_psi": 225.0, "test_pressure_bar": 15.51,
            "test_recovery_pct": 15.0, "test_temp_c": 25.0, "permeate_flow_m3d": 9.1,
            "nominal_rejection_pct": 99.60, "min_rejection_pct": 99.40, "is_estimate": False
        },
        "HPA-RO-8040": {
            "test_solution": "2,000 ppm NaCl", "test_pressure_psi": 225.0, "test_pressure_bar": 15.51,
            "test_recovery_pct": 15.0, "test_temp_c": 25.0, "permeate_flow_m3d": 39.7,
            "nominal_rejection_pct": 99.70, "min_rejection_pct": 99.60, "is_estimate": False
        },
        "HPA-RO-8040-LF-WW": {
            "test_solution": "2,000 ppm NaCl", "test_pressure_psi": 225.0, "test_pressure_bar": 15.51,
            "test_recovery_pct": 15.0, "test_temp_c": 25.0, "permeate_flow_m3d": 38.0,
            "nominal_rejection_pct": 99.70, "min_rejection_pct": 99.60, "is_estimate": False
        },
        "HPARO-8040-BW-400": {
            "test_solution": "2,000 ppm NaCl", "test_pressure_psi": 225.0, "test_pressure_bar": 15.51,
            "test_recovery_pct": 15.0, "test_temp_c": 25.0, "permeate_flow_m3d": 40.0,
            "nominal_rejection_pct": 99.70, "min_rejection_pct": 99.60, "is_estimate": False
        },
        "SWRO-8040-400": {
            "test_solution": "32,000 ppm NaCl", "test_pressure_psi": 800.0, "test_pressure_bar": 55.16,
            "test_recovery_pct": 8.0, "test_temp_c": 25.0, "permeate_flow_m3d": 24.6,
            "nominal_rejection_pct": 99.75, "min_rejection_pct": 99.50, "is_estimate": False
        },
        "SWRO-FR-8040-400": {
            "test_solution": "32,000 ppm NaCl", "test_pressure_psi": 800.0, "test_pressure_bar": 55.16,
            "test_recovery_pct": 8.0, "test_temp_c": 25.0, "permeate_flow_m3d": 22.7,
            "nominal_rejection_pct": 99.70, "min_rejection_pct": 99.50, "is_estimate": False
        },
        "SWRO-HLE-8040-400": {
            "test_solution": "32,000 ppm NaCl", "test_pressure_psi": 800.0, "test_pressure_bar": 55.16,
            "test_recovery_pct": 8.0, "test_temp_c": 25.0, "permeate_flow_m3d": 26.5,
            "nominal_rejection_pct": 99.75, "min_rejection_pct": 99.50, "is_estimate": False
        },
    }

    @classmethod
    def get_ro_membrane(cls, name: str) -> Dict[str, Any]:
        """Retrieve and normalize an RO/NF membrane record by model name."""
        if name not in cls.RO_MEMBRANES:
            # Previously this silently returned BW30-400 (DuPont) results.
            warnings.warn(f"Membrane model '{name}' not found in database; "
                          f"falling back to BW30-400. Results are NOT for '{name}'.")
        catalog_key = name if name in cls.RO_MEMBRANES else "BW30-400"
        raw_mem = cls.RO_MEMBRANES.get(name, cls.RO_MEMBRANES["BW30-400"])
        return cls._normalize_membrane(raw_mem, catalog_key=catalog_key)

    @classmethod
    def _normalize_membrane(cls, raw_mem: Dict[str, Any], catalog_key: str = "") -> Dict[str, Any]:
        """
        Normalizes any catalog element into the 8.1 Membrane Datasheet Schema shape.
        """
        mem = raw_mem.copy()
        model_name = mem.get("model") or catalog_key
        if model_name and not mem.get("model"):
            mem["model"] = model_name
        
        # 1. membrane_class
        mem["membrane_class"] = mem.get("type", "BWRO")
        
        # 1b. Calibrated temperature / ageing constants by family (BWRO / SWRO)
        for key, val in FAMILY_PARAMS.get(mem["membrane_class"], {}).items():
            mem.setdefault(key, val)

        # 2. operating_limits
        op_limits = mem.get("operating_limits", {})
        op_limits.setdefault("max_pressure", mem.get("max_pressure_bar"))
        op_limits.setdefault("max_temp", mem.get("max_temp_c"))
        op_limits.setdefault("ph_range", mem.get("ph_range"))
        op_limits.setdefault("cip_ph_range", mem.get("cip_ph_range"))
        op_limits.setdefault("max_chlorine", mem.get("max_chlorine_mgL"))
        op_limits.setdefault("max_sdi", mem.get("max_sdi_15"))
        mem["operating_limits"] = op_limits

        # 3. surface_class
        surf_class = mem.get("surface_class", {})
        flags = mem.get("flags", [])
        surf_class.setdefault("fouling_resistant_claim", "LF" in flags or "FR" in flags or "low fouling" in str(mem.get("description", "")).lower())
        surf_class.setdefault("hydrophilic", False)
        surf_class.setdefault("material", mem.get("material", "PA"))
        mem["surface_class"] = surf_class

        # 4. active_area, nominal_rejection, nominal_flow
        mem.setdefault("active_area", mem.get("active_area_m2"))
        mem.setdefault("nominal_rejection", mem.get("nominal_rejection"))
        mem.setdefault("nominal_flow", mem.get("max_feed_flow_m3h")) # Assuming max feed flow is a proxy if nominal flow missing

        # 5. design_flux_table and saturation_limits (already used in HPA-4040, map from guidelines)
        mem.setdefault("design_flux_table", mem.get("design_flux_guidelines", {}))
        default_sat = {
            "LSI": 1.5,
            "SDSI": 0.5,
            "CaSO4_pct": 230,
            "SrSO4_pct": 800,
            "BaSO4_pct": 6000,
            "SiO2_pct": 100
        }
        mem["saturation_limits"] = mem.get("saturation_limits") or default_sat

        # 6. Spacer thickness and hydraulic diameter (CHANGE 15)
        spacer_mil = mem.get("feed_spacer_mil", 31)
        t_fs = spacer_mil * 2.54e-5
        eps = 0.90
        dh_calc = (4.0 * eps) / ((2.0 / t_fs) + ((1.0 - eps) * 8.0 / t_fs))
        mem.setdefault("hydraulic_diameter_m", round(dh_calc, 6))

        # 7. Datasheet block (CHANGE 6)
        is_swro = mem.get("type") == "SWRO" or "SW" in mem.get("description", "")
        test_sol = "32,000 ppm NaCl" if is_swro else "2,000 ppm NaCl"
        test_p_bar = 55.16 if is_swro else 15.51
        test_p_psi = 800.0 if is_swro else 225.0
        nom_rej = mem.get("nominal_rejection")
        if nom_rej is None:
            nom_rej = 0.997 if not is_swro else 0.998
        min_rej = mem.get("min_rejection")
        if min_rej is None:
            min_rej = 0.995 if not is_swro else 0.997

        if mem.get("datasheet"):
            pass
        elif model_name in cls.VERIFIED_DATASHEETS:
            mem["datasheet"] = dict(cls.VERIFIED_DATASHEETS[model_name])
        else:
            rec_est = 8.0 if is_swro else 15.0
            default_datasheet = {
                "test_solution": test_sol,
                "test_pressure_bar": test_p_bar,
                "test_pressure_psi": test_p_psi,
                "test_recovery_pct": rec_est,
                "test_temp_c": 25.0,
                "nominal_rejection_pct": round(nom_rej * 100.0, 2),
                "min_rejection_pct": round(min_rej * 100.0, 2),
                "permeate_flow_m3d": round((mem.get("max_feed_flow_m3h") or 16.0) * (rec_est / 100.0) * 24.0, 1),
                "is_estimate": True,
                "permeate_flow_is_estimate": True,
            }
            mem["datasheet"] = default_datasheet

        return mem

    @classmethod
    def get_uf_module(cls, name: str) -> Dict[str, Any]:
        """Retrieve a UF module record by model name with default fallback."""
        return cls.UF_MODULES.get(name, cls.UF_MODULES["PERMA-UF-i0875s40"])

    @classmethod
    def list_ro_membranes(cls):
        """Return a summary listing of all catalog RO/NF membranes and their datasheet specifications."""
        return [
            {
                "id": k,
                "name": k,
                "type": v.get("type"),
                "manufacturer": v.get("manufacturer"),
                "area": v.get("active_area_m2"),
                "feed_spacer_mil": v.get("feed_spacer_mil"),
                "nominal_rejection": v.get("nominal_rejection"),
                "max_pressure_bar": v.get("max_pressure_bar"),
                "max_feed_flow_m3h": v.get("max_feed_flow_m3h"),
                "min_conc_flow_m3h": v.get("min_conc_flow_m3h"),
                "max_recovery_pct": v.get("max_recovery_pct"),
                "length_m": v.get("length_m"),
                "diameter_m": v.get("diameter_m"),
                "material": v.get("material", "Polyamide Composite"),
                "datasheet": cls.get_ro_membrane(k).get("datasheet", {})
            }
            for k, v in cls.RO_MEMBRANES.items()
        ]

    @classmethod
    def list_uf_modules(cls):
        """Return a list of available UF modules with ID, name, and surface area."""
        return [{"id": k, "name": k, "area": v["membrane_area_m2"]} for k, v in cls.UF_MODULES.items()]
        