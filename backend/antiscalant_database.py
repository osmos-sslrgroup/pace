"""
PACE Antiscalant Product Database
=================================
Genesys International antiscalants (product data sheets, Aug 2015 v3.0 / Aug 2022 v4.0)
plus the treated-scaling limits and dose curves reverse-engineered from
Genesys Membrane Master 3VC (see claude/Genesys_scaling_model.md, 21 Nov 2026).

Limits
  - "lsi_max"        : CaCO3 LSI the product holds          (%MAX = (LSI+3)/(lsi_max+3))
  - other "limits"   : multiple of saturation the product holds (%MAX = index / limit)
Dose
  - Dose is sized as the antiscalant concentration needed IN THE CONCENTRATE;
    feed dose = concentrate requirement / CF.
  - "scale_basis": "LSI"  -> C_conc = poly(LSI_conc)              (LF, RC)
                   "SiO2" -> C_conc = a * SiO2_index_conc + b      (SI)
  - "strength_factor" multiplies both the scale and iron curves (RC = 2.80 x LF).
"""
from typing import Dict, Any, List

# LF scale-control curve, C_conc (mg/L) vs concentrate LSI (fit +-0.1 mg/L, LSI 0.25-2.6)
_LF_SCALE_POLY = (7.462, 0.714, 0.096, 0.237)          # c0 + c1*L + c2*L^2 + c3*L^3
# Iron-control curve, C_conc (mg/L) = k * (untreated concentrate Fe index) ^ n
_IRON_K, _IRON_N = 0.635, 1.22

ANTISCALANTS: Dict[str, Dict[str, Any]] = {
    "Genesys LF": {
        "manufacturer": "Genesys International Ltd (UK)",
        "description": "Broad spectrum antiscalant and antifoulant (concentrated phosphonate). "
                       "Sequesters Fe, Mn, Al; general purpose RO/NF.",
        "chemistry": "Neutralised phosphonic acid",
        "best_for": "Fouling waters (Fe / Mn / Al present), general purpose duty",
        "selection_role": "fouling",
        "datasheet": {
            "typical_dose_mg_l": [2.0, 4.0],
            "seawater_iron_dose_mg_l": [0.5, 1.0],
            "nsf_max_potable_dose_mg_l": 5.0,
            "effective_lsi": 2.6,
            "appearance": "Straw coloured liquid",
            "ph_as_supplied": [9.8, 10.2],
            "specific_gravity": [1.34, 1.37],
            "freezing_point_c": "< -15",
            "packaging": "25 kg kegs, 250 kg drums, 1,300 kg IBCs",
            "shelf_life_years": 2,
            "approvals": ["NSF listed", "UKDWI (drinking water)"],
            "inhibits": ["CaCO3", "CaSO4", "Ca3(PO4)2", "BaSO4", "SrSO4", "SiO2", "Fe", "Mn"],
            "notes": "Replaces acid addition. Dose continuously upstream of cartridge filters.",
        },
        "density_kg_l": 1.32,          # Membrane Master kg -> litre conversion
        "limits": {"lsi_max": 2.6, "CaSO4": 2.5, "BaSO4": 50.0, "SrSO4": 10.0, "CaF2": 120.0,
                   "Fe": 15.0, "SiO2": 1.58, "Al": 1.54, "Mn": 15.0, "Ca3(PO4)2": 1.0},
        "scale_basis": "LSI",
        "strength_factor": 1.0,
    },
    "Genesys RC": {
        "manufacturer": "Genesys International Ltd (UK)",
        "description": "Antiscalant/antifoulant for recycle and small RO/NF systems "
                       "(< 100 m3/day feed). Allows higher recovery.",
        "chemistry": "Blend of neutralised carboxylic and phosphonic acids",
        "best_for": "Normal waters where recovery is pushed high; concentrate recycle; small systems",
        "selection_role": "high_recovery",
        "datasheet": {
            "typical_dose_mg_l": [7.0, 15.0],
            "nsf_max_potable_dose_mg_l": None,
            "max_feed_flow_m3_day": 100.0,
            "appearance": "Pale liquid",
            "ph_as_supplied": [10.7, 11.3],
            "specific_gravity": [1.08, 1.12],
            "freezing_point_c": "< 0",
            "packaging": "25 kg kegs, 200 kg drums",
            "shelf_life_years": 2,
            "approvals": [],
            "inhibits": ["CaCO3", "CaSO4", "BaSO4", "SrSO4", "Ca3(PO4)2", "Mg(OH)2", "Fe", "Mn"],
            "notes": "Replaces acid addition. Simple test method.",
        },
        "density_kg_l": 1.10,
        "limits": {"lsi_max": 2.6, "CaSO4": 2.5, "BaSO4": 50.0, "SrSO4": 10.0, "CaF2": 120.0,
                   "Fe": 15.0, "SiO2": 1.58, "Al": 1.54, "Mn": 15.0, "Ca3(PO4)2": 1.0},
        "scale_basis": "LSI",
        "strength_factor": 2.80,       # RC dose = LF dose x 2.80 (8 Genesys runs, 2.78-2.81)
    },
    "Genesys SI": {
        "manufacturer": "Genesys International Ltd (UK)",
        "description": "Silica antiscalant/antifoulant for high-silica feed waters; also "
                       "inhibits CaCO3, CaSO4, BaSO4, SrSO4.",
        "chemistry": "Blend of neutralised carboxylic and phosphonic acids",
        "best_for": "High silica feed (silica is the limiting scalant at the design recovery)",
        "selection_role": "silica",
        "datasheet": {
            "typical_dose_mg_l": [2.0, 5.0],
            "nsf_max_potable_dose_mg_l": 5.0,
            "appearance": "Pale amber liquid",
            "ph_as_supplied": [9.8, 10.2],
            "specific_gravity": [1.13, 1.17],
            "freezing_point_c": "< -4",
            "packaging": "25 kg kegs, 240 kg drums, 1,200 kg IBCs",
            "shelf_life_years": 2,
            "approvals": ["NSF listed", "UKDWI (drinking water)"],
            "inhibits": ["CaCO3", "CaSO4", "BaSO4", "SrSO4", "Ca3(PO4)2", "SiO2", "Fe", "Mn"],
            "notes": "Replaces acid addition. Allows high recovery on silica-limited waters.",
        },
        "density_kg_l": 1.22,
        "limits": {"lsi_max": 2.6, "CaSO4": 2.5, "BaSO4": 50.0, "SrSO4": 10.0, "CaF2": 120.0,
                   "Fe": 15.0, "SiO2": 2.17, "Al": 1.54, "Mn": 15.0, "Ca3(PO4)2": 1.0},
        "scale_basis": "SiO2",
        "si_dose_line": (26.1, -19.4),   # C_conc = 26.1 * SiO2 index - 19.4 (6 runs, exact)
        "strength_factor": 1.0,
    },
}

# Untreated (no antiscalant) limits: saturation for every species, LSI 0 for CaCO3
UNTREATED_LIMITS = {"lsi_max": 0.0, "CaSO4": 1.0, "BaSO4": 1.0, "SrSO4": 1.0, "CaF2": 1.0,
                    "Fe": 1.0, "SiO2": 1.0, "Al": 1.0, "Mn": 1.0, "Ca3(PO4)2": 1.0}

_ALIASES = {"lf": "Genesys LF", "genesys lf": "Genesys LF", "genesys_lf": "Genesys LF",
            "rc": "Genesys RC", "genesys rc": "Genesys RC", "genesys_rc": "Genesys RC",
            "si": "Genesys SI", "genesys si": "Genesys SI", "genesys_si": "Genesys SI"}


def normalize_product(name) -> str:
    """'LF', 'genesys_lf', 'Genesys LF' -> 'Genesys LF'; 'auto' -> 'auto'; unknown/None -> None."""
    if not name:
        return None
    s = str(name).strip()
    if s.lower() in ("auto", "automatic", "recommend"):
        return "auto"
    if s in ANTISCALANTS:
        return s
    return _ALIASES.get(s.lower())


def get_antiscalant(name) -> Dict[str, Any]:
    key = normalize_product(name)
    return ANTISCALANTS.get(key) if key and key != "auto" else None


def list_antiscalants() -> List[Dict[str, Any]]:
    out = []
    for k, v in ANTISCALANTS.items():
        out.append({
            "id": k, "name": k, "manufacturer": v["manufacturer"],
            "description": v["description"], "best_for": v["best_for"],
            "selection_role": v["selection_role"], "chemistry": v["chemistry"],
            "datasheet": v["datasheet"], "limits": v["limits"],
            "density_kg_l": v["density_kg_l"],
        })
    return out


def scale_dose_conc(product: str, lsi_conc: float, sio2_index_conc: float) -> float:
    """Scale-control antiscalant needed in the concentrate, mg/L."""
    p = ANTISCALANTS[product]
    if p["scale_basis"] == "SiO2":
        a, b = p["si_dose_line"]
        return max(0.0, a * sio2_index_conc + b)
    return _lf_scale(lsi_conc) * p["strength_factor"]


def _lf_scale(lsi: float) -> float:
    L = max(0.0, min(lsi, 3.0))            # curve fitted for LSI 0.25-2.6
    c0, c1, c2, c3 = _LF_SCALE_POLY
    return c0 + c1 * L + c2 * L * L + c3 * L ** 3


def iron_dose_conc(product: str, fe_index_untreated_conc: float) -> float:
    """Iron-control antiscalant needed in the concentrate, mg/L."""
    if fe_index_untreated_conc <= 0:
        return 0.0
    p = ANTISCALANTS[product]
    factor = p["strength_factor"] if p["scale_basis"] == "LSI" else 1.0
    return _IRON_K * fe_index_untreated_conc ** _IRON_N * factor
