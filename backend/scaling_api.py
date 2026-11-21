"""
PACE Scaling / Antiscalant API (added 21 Nov 2026 - sent by msk on 21-11-2026)
================================================================================
  GET  /api/antiscalants             product database (Genesys LF / RC / SI)
  POST /api/antiscalant-analysis     Genesys-calibrated scaling, pH adjustment, antiscalant
                                     % of max, dose, recommendation and max recovery
  calculate_scaling_with_ph(...)     replacement body for POST /api/calculate-scaling
                                     (PHREEQC SI) - now applies the pH adjustment and concentrate speciation

Mount in server.py & server_impl.py:
    from scaling_api import router as scaling_router
    app.include_router(scaling_router)
"""
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from antiscalant_database import list_antiscalants
from scaling_engine import analyse, adjust_ph, ions_from_feed

router = APIRouter()

# Keys the UI may use for the dosing / adjusted pH (all accepted)
_TARGET_PH_KEYS = ("target_ph", "feed_ph", "adjusted_ph", "feed_ph_adjusted", "ph_adjusted",
                   "dosing_target_ph", "feed_target_ph", "ro_feed_ph")
_CHEM_KEYS = ("chemical", "acid_type", "dosing_chemical", "acid", "ph_chemical", "dosing_chem")
_REC_KEYS = ("recovery_pct", "target_recovery_pct", "recovery")


def _pick(d: Dict[str, Any], keys, default=None):
    for k in keys:
        v = d.get(k)
        if v not in (None, ""):
            return v
    return default


def _num(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


class AntiscalantInput(BaseModel):
    model_config = {"extra": "allow"}
    feed_water: dict                          # same dict as /api/calculate-system
    recovery_pct: float = 75.0
    temperature: Optional[float] = None       # default feed_water["temperature"]
    raw_ph: Optional[float] = None            # default feed_water["ph"]
    target_ph: Optional[float] = None         # RO feed pH after dosing; None = no adjustment
    chemical: Optional[str] = None            # HCl / H2SO4 / NaOH (UI labels accepted)
    antiscalant: Optional[str] = "auto"       # auto | Genesys LF | Genesys RC | Genesys SI | none
    product_flow_m3h: Optional[float] = None
    feed_flow_m3h: Optional[float] = None
    sweep: bool = True                        # max-recovery search per product


@router.get("/api/antiscalants")
def get_antiscalants():
    """Antiscalant product database."""
    return {"antiscalants": list_antiscalants()}


@router.post("/api/antiscalant-analysis")
def antiscalant_analysis(data: AntiscalantInput):
    """Genesys-calibrated scaling analysis with pH adjustment and antiscalant selection."""
    try:
        extra = data.model_dump()
        target_ph = data.target_ph if data.target_ph is not None else _num(_pick(extra, _TARGET_PH_KEYS))
        chemical = data.chemical or _pick(extra, _CHEM_KEYS)
        return analyse(data.feed_water, data.recovery_pct, temp_c=data.temperature, raw_ph=data.raw_ph,
                       target_ph=target_ph, chemical=chemical, antiscalant=data.antiscalant or "auto",
                       product_flow_m3h=data.product_flow_m3h, feed_flow_m3h=data.feed_flow_m3h,
                       sweep=data.sweep)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# PHREEQC saturation indices WITH the pH adjustment and concentrate scaling
# ---------------------------------------------------------------------------
_PHREEQC_SI = {"gypsum_si": "Gypsum", "calcite_si": "Calcite", "aragonite_si": "Aragonite",
               "barite_si": "Barite", "lsi": "Calcite", "celestite_si": "Celestite",
               "fluorite_si": "Fluorite", "anhydrite_si": "Anhydrite", "silica_si": "SiO2(a)",
               "iron_si": "Fe(OH)3(a)", "aluminium_si": "Al(OH)3(a)", "manganese_si": "Pyrolusite",
               "calcium_phosphate_si": "Hydroxyapatite"}


def _phreeqc_si(pp, ions: Dict[str, float], ph: float, temp_c: float) -> Dict[str, float]:
    sol = pp.add_solution({
        'units': 'mg/L', 'temp': temp_c, 'pH': ph,
        'Ca': ions.get("Ca", 0), 'Mg': ions.get("Mg", 0), 'Na': ions.get("Na", 0), 'K': ions.get("K", 0),
        'N(-3)': f"{ions.get('NH4', 0)} as NH4", 'Cl': ions.get("Cl", 0),
        'S(6)': f"{ions.get('SO4', 0)} as SO4",
        'Alkalinity': f"{ions.get('HCO3', 0)} as HCO3",
        'N(5)': f"{ions.get('NO3', 0)} as NO3", 'Sr': ions.get("Sr", 0), 'F': ions.get("F", 0),
        'Si': f"{ions.get('SiO2', 0)} as SiO2", 'Ba': ions.get("Ba", 0), 'Al': ions.get("Al", 0),
        'Fe': ions.get("Fe", 0), 'Mn': ions.get("Mn", 0), 'P': f"{ions.get('PO4', 0)} as PO4",
        'B': ions.get("B", 0),
    })
    out = {k: sol.si(v) for k, v in _PHREEQC_SI.items()}
    sol.forget()
    return out


def calculate_scaling_with_ph(data, pp) -> Dict[str, Any]:
    """
    Body for POST /api/calculate-scaling.

    Harmonized 21 Nov 2026 (sent by msk on 21-11-2026):
      * Computes stoichiometric acid/alkali dosing (converts HCO3 -> CO2, adds counter-ions)
      * Evaluates PHREEQC saturation indices on treated feed and concentrated brine
      * Attaches Genesys-calibrated antiscalant limits, % of max saturation, and product selection
      * Returns top-level keys matching the evaluated stream (brine concentrate when recovery > 0)
    """
    d = data.model_dump() if hasattr(data, "model_dump") else dict(data)
    feed = {k: v for k, v in d.items()}
    temp = float(d.get("temperature", 25.0) or 25.0)
    raw_ph = float(d.get("raw_ph", d.get("ph", 7.0)) or 7.0)
    target_ph = _num(_pick(d, _TARGET_PH_KEYS))
    chemical = _pick(d, _CHEM_KEYS) or "H2SO4"
    recovery = _num(_pick(d, _REC_KEYS))
    if recovery is not None and recovery <= 1.0:
        recovery *= 100.0                      # accept 0.75 as 75%
    if recovery is None:
        recovery = 75.0
    antiscalant = _pick(d, ("antiscalant", "antiscalant_type", "antiscalant_product"), "auto")

    cf = 1.0 / (1.0 - recovery / 100.0) if recovery < 100 else 1.0
    if d.get("concentration_factor"):
        cf = float(d["concentration_factor"])

    raw_ions = ions_from_feed(feed)
    adj = adjust_ph(raw_ions, raw_ph, target_ph, chemical, temp)
    feed_ions, feed_ph = adj["ions"], adj["ph"]

    result = {}
    feed_si = _phreeqc_si(pp, feed_ions, feed_ph, temp) if pp is not None else {}
    raw_si = _phreeqc_si(pp, raw_ions, raw_ph, temp) if pp is not None else {}

    result["raw_si"] = raw_si
    result["feed_si"] = feed_si
    result["raw_ph"] = round(raw_ph, 2)
    result["feed_ph"] = round(feed_ph, 3)
    result["cf"] = round(cf, 2)

    dose_val = adj.get("dose_commercial_mg_l") or adj.get("dose_mg_l") or 0.0
    result["acid_dose_mg_l"] = round(dose_val, 2)
    result["acid_type"] = adj.get("chemical") or chemical or "H2SO4"
    result["stream_evaluated"] = "concentrate" if cf > 1.01 else "feed"

    result["ph_adjustment"] = {
        "chemical": adj["chemical"],
        "dose_100pct_mg_l": adj["dose_mg_l"],
        "dose_commercial_mg_l": adj["dose_commercial_mg_l"],
        "hco3_raw_mg_l": round(raw_ions.get("HCO3", 0), 2),
        "hco3_feed_mg_l": round(feed_ions.get("HCO3", 0), 2),
        "co2_feed_mg_l": round(adj["co2_mg_l"], 2),
        "notes": adj["notes"]
    }

    if recovery:
        g = analyse(feed, recovery, temp_c=temp, raw_ph=raw_ph, target_ph=target_ph,
                    chemical=chemical, antiscalant=antiscalant, sweep=False)
        conc = g["water"]["concentrate"]
        conc_si = _phreeqc_si(pp, conc["ions"], conc["ph"], temp) if pp is not None else {}
        result["concentrate_si"] = conc_si
        result["concentrate_ph"] = conc["ph"]
        result["genesys"] = g

        # When evaluating concentrate stream (CF > 1), set top-level SI keys to concentrate stream
        if cf > 1.01 and conc_si:
            result.update(conc_si)
        else:
            result.update(feed_si)
    else:
        result.update(feed_si)

    return result
