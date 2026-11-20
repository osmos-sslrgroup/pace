"""
PACE Feed Water Conditioning / pH Adjustment Module
====================================================
Chemical dosing (HCl, H2SO4, NaOH) and CO2 degassing (decarbonator) for:
  - pre-treatment  (RO feed:  acid dosing, then decarbonator)
  - interstage     (2-pass RO: decarbonator and/or caustic before pass 2)
  - post-treatment (product:  decarbonator, then caustic / acid trim)

Rewritten 20 Nov 2026:
  * dose from the carbonate balance on TOTAL inorganic carbon (HCO3 + CO2)
  * acid converts HCO3 -> CO2, caustic converts CO2 -> HCO3
  * CO2 is always tracked (calculated from HCO3 and pH when not supplied), so the
    degasser actually removes CO2 and the pH after degassing is recalculated
  * correct order: acid -> degasser ; degasser -> caustic
  * chemical names and numbers from the UI are normalised; every zero dose comes
    with a note explaining why
"""
import math

PK1 = 6.35          # carbonic acid pK1 at 25 C
EQ_WT = {"HCl": 36.46, "H2SO4": 49.04, "NaOH": 40.00}   # mg active chemical per meq
MW_HCO3 = 61.0168
MW_CO2 = 44.01

_CHEM_ALIASES = {
    "HCl": ("hcl", "hydrochloric", "hydrochloric acid", "muriatic"),
    "H2SO4": ("h2so4", "sulfuric", "sulphuric", "sulfuric acid", "sulphuric acid"),
    "NaOH": ("naoh", "caustic", "caustic soda", "sodium hydroxide"),
}
_ACIDS = ("HCl", "H2SO4")


def normalize_chemical(name):
    """Map UI labels ('Hydrochloric Acid', 'HCL 33%', 'Caustic soda') to HCl / H2SO4 / NaOH."""
    if not name:
        return None
    s = str(name).strip().lower()
    for key, aliases in _CHEM_ALIASES.items():
        if s == key.lower() or any(s.startswith(a) for a in aliases):
            return key
    return None


def _num(value, default=None):
    """Float from a number or numeric string; default when empty or invalid."""
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _cfg_get(cfg, key, default=None):
    """Read a key from a dict or a Pydantic-style object."""
    if cfg is None:
        return default
    if isinstance(cfg, dict):
        return cfg.get(key, default)
    return getattr(cfg, key, default)


def co2_from_ph(hco3_mg_l, ph):
    """Free CO2 (mg/L) in equilibrium with HCO3 at a given pH."""
    if hco3_mg_l <= 0 or ph is None:
        return 0.0
    return hco3_mg_l / MW_HCO3 * math.pow(10.0, PK1 - ph) * MW_CO2


def ph_from_carbonate(hco3_mg_l, co2_mg_l, cap=8.3):
    """pH = pK1 + log10(HCO3/CO2); None if either is zero. Capped at 8.3 (CO3 ignored)."""
    if hco3_mg_l <= 0 or co2_mg_l <= 0:
        return None
    ph = PK1 + math.log10((hco3_mg_l / MW_HCO3) / (co2_mg_l / MW_CO2))
    return min(ph, cap)


def _dose_meq(hco3_mmol, co2_mmol, current_ph, target_ph, chemical):
    """meq/L of chemical to move from current_ph to target_ph at constant C_T."""
    c_t = hco3_mmol + co2_mmol
    hco3_target = c_t / (1.0 + math.pow(10.0, PK1 - target_ph))
    if chemical in _ACIDS:
        free_h = (math.pow(10.0, -target_ph) - math.pow(10.0, -current_ph)) * 1000.0
        return max(0.0, hco3_mmol - hco3_target) + max(0.0, free_h)
    free_oh = (math.pow(10.0, target_ph - 14.0) - math.pow(10.0, current_ph - 14.0)) * 1000.0
    return max(0.0, hco3_target - hco3_mmol) + max(0.0, free_oh)


def compute_chemical_dose(ions, target_ph, chemical):
    """
    Chemical dose (mg/L active chemical) to move a water from its pH (ions["pH"]) to
    target_ph. Kept for backward compatibility; see condition_water() for the full step.
    """
    chem = normalize_chemical(chemical)
    target_ph = _num(target_ph)
    current_ph = _num(ions.get("pH", ions.get("ph")), 7.0)
    if chem is None or target_ph is None or abs(current_ph - target_ph) < 0.05:
        return 0.0
    if (chem in _ACIDS and target_ph >= current_ph) or (chem == "NaOH" and target_ph <= current_ph):
        return 0.0
    hco3 = ions.get("HCO3", ions.get("bicarbonate", 0.0))
    co2 = ions.get("CO2")
    co2 = co2 if co2 else co2_from_ph(hco3, current_ph)
    d = _dose_meq(hco3 / MW_HCO3, co2 / MW_CO2, current_ph, target_ph, chem)
    return round(d * EQ_WT[chem], 2)


def _degas(state, degasser_cfg, notes, label):
    """Strip CO2 in a decarbonator; recalculate pH from the carbonate balance."""
    eff = _num(_cfg_get(degasser_cfg, "efficiency"), 0.95)
    eff = eff / 100.0 if eff > 1.0 else eff            # accept 90 or 0.90
    residual = _num(_cfg_get(degasser_cfg, "residual_co2_mg_l"), 3.0)
    co2_in = state["co2"]
    state["degas_co2_in"] = co2_in
    state["degas_ph_in"] = state["ph"]
    if co2_in <= residual:
        notes.append(f"{label} degasser: CO2 {co2_in:.1f} mg/L already at/below residual "
                     f"{residual:.1f} mg/L — nothing removed")
        return
    state["co2"] = max(residual, co2_in * (1.0 - eff))
    new_ph = ph_from_carbonate(state["ions"].get("HCO3", 0.0), state["co2"])
    if new_ph is not None:
        state["ph"] = new_ph
    state["co2_removed"] += co2_in - state["co2"]
    state["degas_co2_out"] = state["co2"]
    state["degas_ph_out"] = state["ph"]


def _dose(state, chem, target_ph, notes, label):
    """Dose acid or caustic to target_ph; update HCO3/CO2 and the counter-ion."""
    cur = state["ph"]
    if abs(cur - target_ph) < 0.05:
        notes.append(f"{label} dosing: water already at pH {cur:.2f} — no {chem} needed")
        return 0.0
    if chem in _ACIDS and target_ph > cur:
        notes.append(f"{label} dosing: {chem} cannot raise pH from {cur:.2f} to {target_ph:.2f} "
                     f"— choose NaOH or a lower target pH")
        return 0.0
    if chem == "NaOH" and target_ph < cur:
        notes.append(f"{label} dosing: NaOH cannot lower pH from {cur:.2f} to {target_ph:.2f} "
                     f"— choose HCl/H2SO4 or a higher target pH")
        return 0.0
    ions = state["ions"]
    hco3_mmol = ions.get("HCO3", 0.0) / MW_HCO3
    co2_mmol = state["co2"] / MW_CO2
    d_meq = _dose_meq(hco3_mmol, co2_mmol, cur, target_ph, chem)
    sign = -1.0 if chem in _ACIDS else 1.0
    carb = min(d_meq, hco3_mmol) if chem in _ACIDS else min(d_meq, co2_mmol)
    ions["HCO3"] = max(0.0, (hco3_mmol + sign * carb) * MW_HCO3)
    state["co2"] = max(0.0, (co2_mmol - sign * carb) * MW_CO2)
    dose = d_meq * EQ_WT[chem]
    if chem == "NaOH":
        ions["Na"] = ions.get("Na", 0.0) + dose * (22.99 / 40.00)
    elif chem == "H2SO4":
        ions["SO4"] = ions.get("SO4", 0.0) + dose * (96.06 / 98.08)
    else:
        ions["Cl"] = ions.get("Cl", 0.0) + dose * (35.45 / 36.46)
    state["ph"] = target_ph
    return round(dose, 2)


def condition_water(ions, ph, dosing_cfg=None, degasser_cfg=None, co2_mg_l=None, label="Feed"):
    """
    One conditioning step (dosing point) on a water.

    ions       : ion dict, mg/L (a "CO2" key is used if present, never added)
    ph         : pH of the water before this step
    dosing_cfg : {"enabled", "chemical", "target_ph"}  (dict or object)
    degasser_cfg: {"enabled", "efficiency", "residual_co2_mg_l"}, or a dosing_cfg
                 carrying "co2_degassing": True (legacy flag)
    co2_mg_l   : free CO2 of the water if known (else from HCO3 and pH)

    Order: acid -> degasser ; degasser -> caustic  (degasser alone: just degasser)

    Returns dict: ions (pH key removed), ph, co2_mg_l, dose_mg_l, chemical,
                  co2_removed_mg_l, dosing_applied, degasser_applied, notes
    """
    ph = _num(ph, 7.0)
    work = {k: v for k, v in ions.items() if k not in ("pH", "ph")}
    had_co2_key = "CO2" in work
    if co2_mg_l is None:
        co2_mg_l = work.get("CO2") if work.get("CO2") else co2_from_ph(work.get("HCO3", 0.0), ph)
    state = {"ions": work, "ph": ph, "co2": float(co2_mg_l or 0.0), "co2_removed": 0.0}
    notes = []

    dose_on = bool(_cfg_get(dosing_cfg, "enabled", False))
    degas_on = bool(_cfg_get(degasser_cfg, "enabled", False)) or bool(_cfg_get(dosing_cfg, "co2_degassing", False))
    chem_raw = _cfg_get(dosing_cfg, "chemical")
    chem = normalize_chemical(chem_raw)
    target_ph = _num(_cfg_get(dosing_cfg, "target_ph"))

    if dose_on and chem is None:
        notes.append(f"{label} dosing enabled but chemical '{chem_raw}' not recognised "
                     f"(use HCl, H2SO4 or NaOH) — no dose applied")
        dose_on = False
    if dose_on and target_ph is None:
        notes.append(f"{label} dosing enabled but no valid target pH given — no dose applied")
        dose_on = False

    dose = 0.0
    if dose_on and degas_on and chem == "NaOH":
        _degas(state, degasser_cfg, notes, label)
        dose = _dose(state, chem, target_ph, notes, label)
    else:
        if dose_on:
            dose = _dose(state, chem, target_ph, notes, label)
        if degas_on:
            _degas(state, degasser_cfg, notes, label)

    if had_co2_key:
        work["CO2"] = state["co2"]
    return {
        "ions": work,
        "ph": round(state["ph"], 3),
        "co2_mg_l": round(state["co2"], 3),
        "dose_mg_l": dose,
        "chemical": chem if dose_on else None,
        "co2_removed_mg_l": round(state["co2_removed"], 3),
        "dosing_applied": dose > 0,
        "degasser_applied": state["co2_removed"] > 0,
        # degasser inlet / outlet (acid is dosed before it, caustic after it)
        "degasser_co2_in_mg_l": round(state.get("degas_co2_in", 0.0), 3) if degas_on else None,
        "degasser_co2_out_mg_l": round(state.get("degas_co2_out", state.get("degas_co2_in", 0.0)), 3) if degas_on else None,
        "degasser_ph_in": round(state.get("degas_ph_in", ph), 3) if degas_on else None,
        "degasser_ph_out": round(state.get("degas_ph_out", state.get("degas_ph_in", ph)), 3) if degas_on else None,
        "notes": notes,
    }


def apply_conditioning(p1_permeate_ions, cond_cfg, degasser_cfg=None):
    """
    Backward-compatible wrapper: returns (ions_with_pH, dose_mg_l, ph_after).
    The input pH is read from ions["pH"].
    """
    ph_in = _num(p1_permeate_ions.get("pH", p1_permeate_ions.get("ph")), 7.0)
    out = condition_water(p1_permeate_ions, ph_in, cond_cfg, degasser_cfg, label="Conditioning")
    ions = dict(out["ions"])
    ions["pH"] = out["ph"]
    return ions, out["dose_mg_l"], out["ph"]
