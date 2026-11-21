"""
PACE Scaling & Antiscalant Engine (Genesys Membrane Master calibrated)
======================================================================
Reproduces the Genesys Membrane Master 3VC scaling / fouling indices, % of maximum
(untreated and treated), acid dose and antiscalant dose, as reverse-engineered on
21 Nov 2026 from ~65 Genesys runs (see claude/Genesys_scaling_model.md).

Flow of one calculation
  raw water --(pH adjustment: HCl / H2SO4 / NaOH to the target pH)--> RO feed
  RO feed   --(x 0.98*CF, CO2 not concentrated)-------------------> concentrate
  indices at raw / feed / concentrate  ->  %MAX untreated and treated (per product)
  antiscalant dose (concentrate requirement / CF)  ->  product recommendation

pH adjustment changes HCO3 (acid: HCO3 -> CO2), the counter-ion (Cl or SO4) and the
feed pH, and through them the concentrate pH, LSI, Fe, Al and SiO2 limits. Sulphate
and fluoride scales are pH-independent (as in Genesys) - with H2SO4 they rise slightly.
"""
import math
from typing import Dict, Any, Optional, List

from antiscalant_database import (ANTISCALANTS, UNTREATED_LIMITS, normalize_product,
                                  scale_dose_conc, iron_dose_conc)

MW = {"Ca": 40.08, "Mg": 24.305, "Na": 22.99, "K": 39.10, "Ba": 137.33, "Sr": 87.62,
      "NH4": 18.04, "Fe": 55.845, "Mn": 54.94, "Al": 26.98,
      "Cl": 35.45, "SO4": 96.06, "F": 19.00, "HCO3": 61.02, "CO3": 60.01, "NO3": 62.00,
      "PO4": 94.97, "SiO2": 60.08, "B": 10.81, "CO2": 44.01}
Z = {"Ca": 2, "Mg": 2, "Na": 1, "K": 1, "Ba": 2, "Sr": 2, "NH4": 1,
     "Cl": 1, "SO4": 2, "F": 1, "HCO3": 1, "CO3": 2, "NO3": 1, "PO4": 3}

# Feed-water keys used by the PACE UI -> engine ion keys
FEED_KEYS = {"calcium": "Ca", "magnesium": "Mg", "sodium": "Na", "potassium": "K",
             "barium": "Ba", "strontium": "Sr", "ammonium": "NH4", "iron": "Fe",
             "manganese": "Mn", "aluminium": "Al", "chloride": "Cl", "sulfate": "SO4",
             "fluoride": "F", "bicarbonate": "HCO3", "carbonate": "CO3", "nitrate": "NO3",
             "phosphate": "PO4", "silica": "SiO2", "boron": "B"}

SCALANTS = ["CaCO3", "CaSO4", "BaSO4", "SrSO4", "CaF2", "Ca3(PO4)2"]
FOULANTS = ["Fe", "SiO2", "Al", "Mn"]
SPECIES = SCALANTS + FOULANTS

EQ_WT = {"HCl": 36.46, "H2SO4": 49.04, "NaOH": 40.00}            # mg active per meq
STRENGTH = {"HCl": 0.35, "H2SO4": 0.95, "NaOH": 0.48}            # commercial strength
DENSITY = {"HCl": 1.18, "H2SO4": 1.84, "NaOH": 1.51}             # kg/L commercial


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def ions_from_feed(feed: Dict[str, Any]) -> Dict[str, float]:
    """PACE feed_water dict (calcium, magnesium, ...) -> engine ion dict (Ca, Mg, ...)."""
    out = {}
    for fk, ek in FEED_KEYS.items():
        v = feed.get(fk, feed.get(ek, 0.0))
        try:
            out[ek] = max(0.0, float(v or 0.0))
        except (TypeError, ValueError):
            out[ek] = 0.0
    return out


def _m(ions, k):
    """mol/L."""
    return ions.get(k, 0.0) / MW[k] / 1000.0


def ionic_strength(ions: Dict[str, float]) -> float:
    """1/2 sum c z^2 (Genesys counts HCO3 as mg/50, i.e. as CaCO3)."""
    s = 0.0
    for k, z in Z.items():
        c = ions.get(k, 0.0)
        if c <= 0:
            continue
        mol = c / 50.0 / 1000.0 if k == "HCO3" else c / MW[k] / 1000.0
        s += mol * z * z
    return 0.5 * s


def tds(ions: Dict[str, float]) -> float:
    return sum(v for k, v in ions.items() if k != "CO2")


def _x(I):
    s = math.sqrt(max(I, 0.0))
    return s / (1.0 + s)


def pk1_cond(temp_c: float) -> float:
    """Conditional carbonic acid pK1' used by Genesys for the acid dose."""
    return 6.32 - 0.0019 * (temp_c - 20.0)


# ---------------------------------------------------------------------------
# pH adjustment (acid / caustic) of the raw water
# ---------------------------------------------------------------------------
def adjust_ph(ions: Dict[str, float], raw_ph: float, target_ph: Optional[float],
              chemical: Optional[str], temp_c: float) -> Dict[str, Any]:
    """
    Move the raw water to target_ph at constant carbonate (CO3 as entered).
    Returns {ions, ph, co2_mg_l, dose_mg_l (100 %), dose_commercial_mg_l, chemical, notes}.
    """
    ions = dict(ions)
    notes = []
    pk1 = pk1_cond(temp_c)
    hco3 = ions.get("HCO3", 0.0) / MW["HCO3"]               # mmol/L
    co2 = hco3 * 10 ** (pk1 - raw_ph)                        # mmol/L in equilibrium
    out = {"ph": raw_ph, "dose_mg_l": 0.0, "dose_commercial_mg_l": 0.0, "chemical": None,
           "meq_l": 0.0}

    chem = None
    if chemical:
        c = str(chemical).strip().lower()
        chem = "HCl" if c.startswith(("hcl", "hydrochloric", "35% hcl", "33% hcl")) or "hcl" in c else \
               "H2SO4" if ("h2so4" in c or "sulph" in c or "sulfur" in c) else \
               "NaOH" if ("naoh" in c or "caustic" in c or "hydroxide" in c) else None
    if target_ph is None or abs(target_ph - raw_ph) < 0.005:
        out.update(ions=ions, co2_mg_l=co2 * MW["CO2"], notes=notes)
        return out

    if chem is None:
        chem = "HCl" if target_ph < raw_ph else "NaOH"
        notes.append(f"No dosing chemical given - {chem} assumed for pH {raw_ph:.2f} -> {target_ph:.2f}")
    if chem in ("HCl", "H2SO4") and target_ph > raw_ph:
        notes.append(f"{chem} cannot raise pH; feed pH kept at raw pH {raw_ph:.2f}")
        out.update(ions=ions, co2_mg_l=co2 * MW["CO2"], notes=notes)
        return out
    if chem == "NaOH" and target_ph < raw_ph:
        notes.append(f"NaOH cannot lower pH; feed pH kept at raw pH {raw_ph:.2f}")
        out.update(ions=ions, co2_mg_l=co2 * MW["CO2"], notes=notes)
        return out

    ct = hco3 + co2
    hco3_new = ct / (1.0 + 10 ** (pk1 - target_ph))
    meq = abs(hco3 - hco3_new)
    if chem in ("HCl", "H2SO4"):
        meq += max(0.0, (10 ** -target_ph - 10 ** -raw_ph) * 1000.0)
    else:
        meq += max(0.0, (10 ** (target_ph - 14) - 10 ** (raw_ph - 14)) * 1000.0)
    ions["HCO3"] = hco3_new * MW["HCO3"]
    dose = meq * EQ_WT[chem]
    if chem == "HCl":
        ions["Cl"] = ions.get("Cl", 0.0) + meq * MW["Cl"]
    elif chem == "H2SO4":
        ions["SO4"] = ions.get("SO4", 0.0) + meq * MW["SO4"] / 2.0
    else:
        ions["Na"] = ions.get("Na", 0.0) + meq * MW["Na"]
    out.update(ions=ions, ph=target_ph, co2_mg_l=(ct - hco3_new) * MW["CO2"],
               dose_mg_l=round(dose, 3), dose_commercial_mg_l=round(dose / STRENGTH[chem], 2),
               chemical=chem, meq_l=round(meq, 4), notes=notes)
    return out


# ---------------------------------------------------------------------------
# Indices of one water
# ---------------------------------------------------------------------------
def indices(ions: Dict[str, float], ph: float, temp_c: float, I: float) -> Dict[str, float]:
    """Genesys scaling / fouling indices of one water (index = 1.0 at saturation, LSI for CaCO3)."""
    T = temp_c
    sx, x = math.sqrt(max(I, 0)), _x(I)
    res = {}

    # CaCO3 - Langelier (Genesys form, no TDS term)
    ca, alk = ions.get("Ca", 0.0), ions.get("HCO3", 0.0) * 0.8202 + ions.get("CO3", 0.0) * 1.6667
    if ca > 0 and alk > 0:
        pHs = 12.4704 - 0.0216 * T - math.log10(ca * 2.497) - math.log10(alk)
        res["CaCO3"] = ph - pHs
    else:
        res["CaCO3"] = -3.0

    so4 = _m(ions, "SO4")
    # CaSO4 (conditional Ksp, Genesys temperature step at 20 C)
    ksp = 10 ** (-3.403 + 0.809 * x + 0.831 * I)
    m_t = 1.0 - 0.022 * (T - 20.0) if T <= 20.0 else 1.135
    res["CaSO4"] = _m(ions, "Ca") * so4 / ksp * m_t
    res["BaSO4"] = _m(ions, "Ba") * so4 / 10 ** (-10.029 + 4.345 * x - 0.365 * I)
    res["SrSO4"] = _m(ions, "Sr") * so4 / 10 ** (-6.870 + 5.514 * x - 0.751 * I)
    res["CaF2"] = _m(ions, "Ca") * _m(ions, "F") ** 2 / 4.0e-11

    # Ca3(PO4)2 - not calibrated against Genesys (all runs had PO4 = 0)
    po4 = _m(ions, "PO4")
    if po4 > 0 and ca > 0:
        # PO4^3- fraction from pK3 12.35 / pK2 7.20; Ksp(Ca3(PO4)2) ~ 2.0e-29 (molar, approx.)
        h = 10 ** -ph
        frac = 1.0 / (1 + h / 10 ** -12.35 + h * h / (10 ** -12.35 * 10 ** -7.20))
        res["Ca3(PO4)2"] = (_m(ions, "Ca") ** 3 * (po4 * frac) ** 2) / 2.0e-29
    else:
        res["Ca3(PO4)2"] = 0.0

    # Fe, Mn - pH-dependent allowable, Genesys T multiplier clamped 15-40 C
    tc = min(max(T, 15.0), 40.0)
    m_fe = 1.0 + 0.0276 * (tc - 20.0)
    fe_lim = 10 ** (0.360 - 0.1744 * ph)
    res["Fe"] = ions.get("Fe", 0.0) / fe_lim * m_fe
    res["Mn"] = ions.get("Mn", 0.0) / fe_lim * m_fe        # not calibrated: Fe rule applied

    # SiO2 / Al - amorphous silica solubility with ionisation and T correction
    S = 111.3 * (1.0 + 10 ** (ph - 8.68)) * (1.0 + 0.01735 * (T - 20.0))
    res["SiO2"] = ions.get("SiO2", 0.0) / S
    res["Al"] = ions.get("Al", 0.0) / (S / 100.0)
    res["_sio2_solubility_mg_l"] = S
    return res


def pct_max(idx: Dict[str, float], limits: Dict[str, float]) -> Dict[str, float]:
    """% of maximum allowed for each species against a limit set."""
    out = {}
    for sp in SPECIES:
        v = idx.get(sp, 0.0)
        if sp == "CaCO3":
            out[sp] = max(0.0, (v + 3.0) / (limits["lsi_max"] + 3.0) * 100.0)
        else:
            out[sp] = max(0.0, v / limits.get(sp, 1.0) * 100.0)
    return out


def _status(p):
    return "OK" if p < 90.0 else ("CAUTION" if p <= 100.0 else "EXCEEDED")


# ---------------------------------------------------------------------------
# One design point
# ---------------------------------------------------------------------------
def analyse(feed: Dict[str, Any], recovery_pct: float, temp_c: float = None, raw_ph: float = None,
            target_ph: float = None, chemical: str = None, antiscalant: str = "auto",
            product_flow_m3h: float = None, feed_flow_m3h: float = None,
            sweep: bool = True) -> Dict[str, Any]:
    """
    Full Genesys-style scaling analysis at one recovery.

    feed            PACE feed_water dict (calcium, ..., temperature, ph)
    recovery_pct    RO recovery, %
    target_ph       RO feed pH after dosing (None = no pH adjustment)
    chemical        'HCl' / 'H2SO4' / 'NaOH' (UI labels accepted)
    antiscalant     'auto' | 'Genesys LF' | 'Genesys RC' | 'Genesys SI' | 'none'
    product_flow_m3h / feed_flow_m3h   for kg/day figures (either one)
    """
    T = float(temp_c if temp_c is not None else feed.get("temperature", 25.0) or 25.0)
    ph_raw = float(raw_ph if raw_ph is not None else feed.get("ph", feed.get("pH", 7.0)) or 7.0)
    r = max(0.0, min(float(recovery_pct), 99.0)) / 100.0
    CF = 1.0 / (1.0 - r)
    f = 0.98 * CF

    raw = ions_from_feed(feed)
    adj = adjust_ph(raw, ph_raw, target_ph, chemical, T)
    feed_ions, ph_f = adj["ions"], adj["ph"]

    I_raw, I_f = ionic_strength(raw), ionic_strength(feed_ions)
    I_c = I_f * CF
    conc = {k: v * f for k, v in feed_ions.items()}
    ph_c = ph_f + math.log10(f) - 0.55 * (math.sqrt(I_c) - math.sqrt(I_f))

    idx = {"raw": indices(raw, ph_raw, T, I_raw),
           "feed": indices(feed_ions, ph_f, T, I_f),
           "concentrate": indices(conc, ph_c, T, I_c)}

    untreated = {s: pct_max(idx[s], UNTREATED_LIMITS) for s in idx}
    treated = {}
    for name, p in ANTISCALANTS.items():
        treated[name] = {"feed": pct_max(idx["feed"], p["limits"]),
                         "concentrate": pct_max(idx["concentrate"], p["limits"])}

    # flows for kg/day
    if feed_flow_m3h is None and product_flow_m3h is not None:
        feed_flow_m3h = product_flow_m3h / r if r > 0 else product_flow_m3h
    q_feed_d = (feed_flow_m3h or 0.0) * 24.0

    # doses for every product
    ci = idx["concentrate"]
    doses = {}
    for name, p in ANTISCALANTS.items():
        sc = scale_dose_conc(name, ci["CaCO3"], ci["SiO2"])
        fe = iron_dose_conc(name, ci["Fe"])
        feed_sc, feed_fe = sc / CF, fe / CF
        total = feed_sc + feed_fe
        kg_d = total * q_feed_d / 1000.0
        doses[name] = {
            "scale_dose_mg_l": round(feed_sc, 2), "iron_dose_mg_l": round(feed_fe, 2),
            "total_feed_dose_mg_l": round(total, 2),
            "concentrate_level_mg_l": round(total * CF, 2),
            "kg_per_day": round(kg_d, 3), "litre_per_day": round(kg_d / p["density_kg_l"], 3),
            "max_treated_pct": round(max(treated[name]["concentrate"].values()), 1),
            "limiting_species": max(treated[name]["concentrate"], key=treated[name]["concentrate"].get),
        }
        ds = p["datasheet"]
        nsf = ds.get("nsf_max_potable_dose_mg_l")
        lo, hi = ds["typical_dose_mg_l"]
        msgs = []
        if total > hi:
            msgs.append(f"Dose {total:.2f} mg/L above datasheet typical range {lo}-{hi} mg/L")
        if nsf and total > nsf:
            msgs.append(f"Above NSF potable-water limit {nsf} mg/L")
        if name == "Genesys RC" and feed_flow_m3h and feed_flow_m3h * 24 > ds.get("max_feed_flow_m3_day", 1e9):
            msgs.append("Datasheet: RC intended for systems < 100 m3/day feed")
        doses[name]["notes"] = msgs

    recommendation = recommend(untreated["concentrate"], treated, r * 100.0, feed_ions)
    selected = normalize_product(antiscalant)
    if selected in (None,) and str(antiscalant).lower() in ("none", "no", "untreated", "off"):
        selected = "none"
    if selected == "auto" or selected is None:
        selected = recommendation["product"]

    sel_block = None
    if selected in ANTISCALANTS:
        tconc = treated[selected]["concentrate"]
        sel_block = {
            "product": selected,
            "treated_pct": {"feed": _round(treated[selected]["feed"]), "concentrate": _round(tconc)},
            "status": {k: _status(v) for k, v in tconc.items()},
            "all_within_limits": all(v <= 100.0 for v in tconc.values()),
            "dose": doses[selected],
        }

    acid_block = None
    if adj["chemical"]:
        chem = adj["chemical"]
        kg_d = adj["dose_mg_l"] * q_feed_d / 1000.0
        acid_block = {"chemical": chem, "strength_pct": STRENGTH[chem] * 100,
                      "dose_100pct_mg_l": round(adj["dose_mg_l"], 2),
                      "dose_commercial_mg_l": adj["dose_commercial_mg_l"],
                      "kg_per_day_commercial": round(kg_d / STRENGTH[chem], 3),
                      "litre_per_day_commercial": round(kg_d / STRENGTH[chem] / DENSITY[chem], 3),
                      "meq_l": adj["meq_l"]}

    result = {
        "engine": "PACE scaling engine (Genesys Membrane Master calibrated, 21 Nov 2026)",
        "inputs": {"recovery_pct": round(r * 100, 2), "cf": round(CF, 3), "temperature_c": T,
                   "raw_ph": ph_raw, "target_ph": target_ph, "chemical": adj["chemical"],
                   "antiscalant_requested": antiscalant},
        "water": {
            "raw": {"ph": round(ph_raw, 2), "tds": round(tds(raw), 1), "ionic_strength": round(I_raw, 4)},
            "feed": {"ph": round(ph_f, 2), "tds": round(tds(feed_ions), 1), "ionic_strength": round(I_f, 4),
                     "co2_mg_l": round(adj["co2_mg_l"], 2), "ions": _round(feed_ions, 2)},
            "concentrate": {"ph": round(ph_c, 2), "tds": round(tds(conc), 1), "ionic_strength": round(I_c, 4),
                            "ions": _round(conc, 2)},
        },
        "ph_adjustment": acid_block,
        "indices": {s: _round({k: v for k, v in idx[s].items() if not k.startswith("_")}, 3) for s in idx},
        "sio2_solubility_mg_l": {s: round(idx[s]["_sio2_solubility_mg_l"], 1) for s in idx},
        "untreated_pct": {s: _round(untreated[s]) for s in untreated},
        "treated_pct": {k: {s: _round(v[s]) for s in v} for k, v in treated.items()},
        "doses": doses,
        "recommendation": recommendation,
        "selected": sel_block,
        "notes": adj["notes"] + _notes(feed_ions),
    }
    if sweep:
        result["max_recovery"] = max_recovery(feed, T, ph_raw, target_ph, chemical)
    return result


SILICA_TRIGGER_PCT = 70.0      # LF-treated SiO2 % above which SI is suggested
HIGH_RECOVERY_PCT = 80.0       # recovery at/above which RC is suggested for normal water
FOULING_TRIGGER_PCT = 50.0     # LF-treated Fe / Al / Mn % above which LF is suggested
FOULING_FEED_MG_L = {"Fe": 0.3, "Mn": 0.05}   # feed levels that flag fouling (PACE pre-treatment flags)


def recommend(untreated_conc: Dict[str, float], treated: Dict[str, Any], recovery_pct: float,
              feed_ions: Dict[str, float] = None) -> Dict[str, Any]:
    """
    Product suggestion following the Permionics design practice (21 Nov 2026):
      high silica (silica limiting)         -> Genesys SI
      fouling parameters (Fe / Al / Mn)      -> Genesys LF
      normal water, pushing recovery         -> Genesys RC
      otherwise                              -> Genesys LF (general purpose)
    """
    lf = treated["Genesys LF"]["concentrate"]
    reasons = []
    lf_limiting = max(lf, key=lf.get)
    if lf["SiO2"] >= SILICA_TRIGGER_PCT or (lf_limiting in ("SiO2", "Al") and lf[lf_limiting] >= 50.0):
        reasons.append(f"High silica: SiO2 {lf['SiO2']:.0f} % of max with LF "
                       f"(SI holds 2.17x silica solubility vs 1.58x for LF/RC)")
        return {"product": "Genesys SI", "role": "silica", "reasons": reasons}
    feed_ions = feed_ions or {}
    foul = [f"{k} {lf[k]:.0f} % of max with LF" for k in ("Fe", "Al", "Mn") if lf.get(k, 0.0) >= FOULING_TRIGGER_PCT]
    foul += [f"feed {k} {feed_ions[k]:.2f} mg/L >= {lim} mg/L" for k, lim in FOULING_FEED_MG_L.items()
             if feed_ions.get(k, 0.0) >= lim]
    if foul:
        reasons.append("Fouling parameters present: " + "; ".join(foul))
        return {"product": "Genesys LF", "role": "fouling", "reasons": reasons}
    if recovery_pct >= HIGH_RECOVERY_PCT or lf["CaCO3"] >= 80.0:
        reasons.append(f"Normal water at high recovery ({recovery_pct:.1f} %, CaCO3 {lf['CaCO3']:.0f} % "
                       f"of max with LF) - RC for higher recovery")
        return {"product": "Genesys RC", "role": "high_recovery", "reasons": reasons}
    reasons.append("No dominant silica / fouling / high-recovery driver - LF general purpose")
    return {"product": "Genesys LF", "role": "general", "reasons": reasons}


def max_recovery(feed, temp_c, raw_ph, target_ph=None, chemical=None,
                 lo=40.0, hi=95.0, step=0.5) -> Dict[str, Any]:
    """Highest recovery with every species <= 100 % of max: untreated and with each product."""
    names = ["untreated"] + list(ANTISCALANTS)
    best = {n: None for n in names}
    limiting = {n: None for n in names}
    done = set()
    rec = lo
    while rec <= hi + 1e-9 and len(done) < len(names):
        a = analyse(feed, rec, temp_c, raw_ph, target_ph, chemical, antiscalant="none", sweep=False)
        sets = {"untreated": a["untreated_pct"]["concentrate"]}
        for n in ANTISCALANTS:
            sets[n] = a["treated_pct"][n]["concentrate"]
        for n, p in sets.items():
            if n in done:
                continue
            worst = max(p, key=p.get)
            if p[worst] <= 100.0:
                best[n] = round(rec, 1)
            else:
                limiting[n] = worst
                done.add(n)
        rec += step
    return {n: {"max_recovery_pct": best[n], "limited_by": limiting[n],
                "below_search_range": best[n] is None} for n in names}


def _round(d, n=1):
    return {k: round(v, n) for k, v in d.items()}


def _notes(ions):
    n = []
    if ions.get("PO4", 0) > 0:
        n.append("Ca3(PO4)2 index is an estimate (not calibrated against Genesys).")
    if ions.get("Mn", 0) > 0:
        n.append("Mn index uses the Fe solubility rule (not calibrated against Genesys).")
    return n
