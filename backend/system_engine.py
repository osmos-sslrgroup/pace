"""
Multi-Technology System Engine
Orchestrates UF, RO, and NF calculations based on the selected technology train.

23 Nov 2026 - FEED PRE-TREATMENT FIX
  * The RO Design "Feed Pre-treatment pH Adjustment" reached the engine as a flat
    `conditioning` block with no dosing location, so it was applied to the PRODUCT
    (post-treatment) and the RO feed pH never changed (HCl on permeate pH 5.4 -> 0 dose).
  * _location() now reads every location field / flag the UI may send
    (location, dosing_location, dosing_point, position, point, stage, apply_at, ...;
    apply_to_feed, feed_pretreatment, pre_treatment, ...) and matches free text
    ("Feed Pre-treatment", "feed_pretreatment", "RO feed", "Product", "Pass 2 feed").
  * A flat block WITHOUT a location now follows the chemical: acid (HCl / H2SO4) ->
    RO feed (pre-treatment); NaOH -> product (single pass) or interstage (2-pass).
  * feed_water.target_ph + feed_water.chemical are used as feed pre-treatment when no
    other pre-treatment block is sent.
  * result["feed_water_used"] stays the RAW feed (the treated pH is in
    result["ro_feed_ph"] / result["feed_conditioning"]["ph_out"]).
"""

import math
import re
from typing import Dict, Any, List
from uf_engine import UFEngine
from calc_engine import ROEngine, normalize_elements_per_vessel
from membrane_database import MembraneDatabase

# Feed-water key  ->  engine ion key (single list used by every solver in this module)
ION_KEYS = [
    ("calcium", "Ca"), ("magnesium", "Mg"), ("sodium", "Na"),
    ("potassium", "K"), ("chloride", "Cl"), ("sulfate", "SO4"),
    ("bicarbonate", "HCO3"), ("barium", "Ba"), ("strontium", "Sr"),
    ("fluoride", "F"), ("silica", "SiO2"), ("boron", "B"),
    ("nitrate", "NO3"), ("phosphate", "PO4"), ("ammonium", "NH4"),
    ("aluminium", "Al"), ("iron", "Fe"), ("manganese", "Mn")
]


def _total_elements(vessels_per_stage, epv, stages=None) -> int:
    """Total elements for a vessel array; epv may be an int or a per-stage list."""
    vps = vessels_per_stage if isinstance(vessels_per_stage, list) else [vessels_per_stage]
    n = stages or len(vps)
    epv_l = normalize_elements_per_vessel(epv, n)
    return sum((vps[i] if i < len(vps) else 1) * epv_l[i] for i in range(n))


def _epv_out(epv, stages):
    """For results: a plain int when every stage is the same (old format), else the per-stage list."""
    epv_l = normalize_elements_per_vessel(epv, stages)
    return epv_l[0] if len(set(epv_l)) == 1 else epv_l


def _tds(ions: Dict[str, float]) -> float:
    """TDS on the Toray DS2 basis: all ions + SiO2 + B; dissolved CO2 excluded."""
    return sum(v for k, v in ions.items() if k != "CO2" and isinstance(v, (int, float)))


def _cfg_dict(obj) -> Dict[str, Any]:
    """Dict from a dict, a Pydantic model or None."""
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    return {}


# ---------------------------------------------------------------------------
# Dosing-point (location) detection - FIX 23 Nov 2026
# ---------------------------------------------------------------------------
_PRE_LOC = ("pre", "feed", "pre-treatment", "pretreatment", "pre_treatment", "ro_feed", "before ro")
_POST_LOC = ("post", "permeate", "product", "post-treatment", "posttreatment", "post_treatment", "after ro")
_INTER_LOC = ("interstage", "inter-stage", "inter_stage", "between passes", "pass2_feed", "pass 2 feed")

# Keys that may carry the dosing point as text
_LOCATION_KEYS = ("location", "dosing_location", "dosing_point", "position", "point", "stage",
                  "apply_at", "applied_at", "dose_at", "treatment", "treatment_location",
                  "dosing_stage", "injection_point", "where")
# Boolean flags that select a dosing point
_PRE_FLAGS = ("apply_to_feed", "apply_to_ro_feed", "feed_pretreatment", "feed_pre_treatment",
              "pre_treatment", "pretreatment", "is_feed", "on_feed")
_POST_FLAGS = ("apply_to_permeate", "apply_to_product", "post_treatment", "posttreatment", "is_product")
_INTER_FLAGS = ("apply_to_interstage", "interstage_dosing")

_ACID_CHEMS = ("HCl", "H2SO4")


def _truthy(v) -> bool:
    """True for True / 1 / 'true' / 'yes' / 'on' (not for dicts or other objects)."""
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v == 1
    if isinstance(v, str):
        return v.strip().lower() in ("true", "yes", "on", "1", "y")
    return False


def _loc_from_text(text) -> str:
    """'pre' / 'post' / 'interstage' / '' from a free-text location ('Feed Pre-treatment', 'RO feed', ...)."""
    s = re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip()
    if not s:
        return ""
    if s in _INTER_LOC or any(w in s for w in ("inter", "pass 2", "pass2", "between pass", "2nd pass", "second pass")):
        return "interstage"
    if s in _POST_LOC or any(w in s for w in ("post", "permeate", "product", "after ro", "treated water")):
        return "post"
    if s in _PRE_LOC or any(w in s for w in ("pre", "feed", "raw", "before ro", "inlet")):
        return "pre"
    return ""


def _location(cfg: Dict[str, Any]) -> str:
    """'pre' / 'post' / 'interstage' / '' from any location field or flag of a config block."""
    if not isinstance(cfg, dict):
        return ""
    if any(_truthy(cfg.get(k)) for k in _PRE_FLAGS):
        return "pre"
    if any(_truthy(cfg.get(k)) for k in _POST_FLAGS):
        return "post"
    if any(_truthy(cfg.get(k)) for k in _INTER_FLAGS):
        return "interstage"
    for k in _LOCATION_KEYS:
        v = cfg.get(k)
        if isinstance(v, str) and v.strip():
            loc = _loc_from_text(v)
            if loc:
                return loc
    return ""


def _resolve_conditioning(input_data: Dict[str, Any], two_pass: bool = False) -> Dict[str, Any]:
    """
    Read every chemical-dosing and degasser setting the UI can send and sort them into
    dosing points:  pre (RO feed), interstage (2-pass only), post (product).

    Accepted shapes (any mix, in this priority):
      conditioning.feed_conditioning / pre_conditioning / pre      -> pre
      conditioning.permeate_conditioning / post_conditioning / post-> post
      conditioning.interstage_conditioning / interstage            -> interstage
      (the same keys at the top level of the request are accepted too)
      conditioning = {enabled, chemical, target_ph, <location field or flag>}
          flat block. Without a location (FIX 23 Nov 2026) it follows the chemical:
          acid (HCl / H2SO4) -> pre (RO feed); NaOH -> post (single pass) /
          interstage (2-pass); degassing only -> post / interstage as before.
      feed_water.target_ph + feed_water.chemical                    -> pre (if no pre block)
      degasser / feed_degasser            -> pre    (unless it carries a location)
      permeate_degasser / post_degasser   -> post
      interstage_degasser                 -> interstage
    """
    from conditioning import normalize_chemical
    cond = _cfg_dict(input_data.get("conditioning"))
    out = {"pre": {}, "post": {}, "interstage": {},
           "pre_degasser": {}, "post_degasser": {}, "interstage_degasser": {}, "notes": []}

    def first(*objs):
        for o in objs:
            d = _cfg_dict(o)
            if d:
                return d
        return {}

    out["pre"] = first(cond.get("feed_conditioning"), cond.get("pre_conditioning"), cond.get("pre"),
                       cond.get("pretreatment_conditioning"),
                       input_data.get("feed_conditioning"), input_data.get("pre_conditioning"))
    out["post"] = first(cond.get("permeate_conditioning"), cond.get("post_conditioning"), cond.get("post"),
                        input_data.get("permeate_conditioning"), input_data.get("post_conditioning"))
    out["interstage"] = first(cond.get("interstage_conditioning"), cond.get("interstage"),
                              input_data.get("interstage_conditioning"))
    if not two_pass and out["interstage"] and not out["post"]:
        out["post"] = out["interstage"]          # single pass has no interstage point
        out["interstage"] = {}

    # Flat conditioning block
    if any(k in cond for k in ("enabled", "chemical", "target_ph", "co2_degassing")):
        loc = _location(cond)
        note = None
        if not loc:
            chem = normalize_chemical(cond.get("chemical"))
            if chem in _ACID_CHEMS:
                loc = "pre"
                note = (f"Dosing location not sent with the conditioning block — {chem} applied to the "
                        f"RO feed (pre-treatment).")
            else:
                loc = "interstage" if two_pass else "post"
                note = (f"Dosing location not sent with the conditioning block — {chem or 'dosing'} applied as "
                        f"{'interstage (before pass 2)' if two_pass else 'post-treatment (product)'}.")
        if loc == "interstage" and not two_pass:
            loc = "post"
        if not out[loc]:
            out[loc] = cond
            if note and cond.get("enabled"):
                out["notes"].append(note)          # only when the fallback location is really used
        elif _truthy(cond.get("co2_degassing")) and not out[f"{loc}_degasser"]:
            # the slot already has an explicit block - keep the degassing tick of the flat block
            out[f"{loc}_degasser"] = {"enabled": True}

    # Feed-water level pH adjustment (Feed Data / Scaling keys) -> RO feed
    if not out["pre"]:
        fw = input_data.get("feed_water") or {}
        if isinstance(fw, dict):
            tph = fw.get("target_ph", fw.get("feed_target_ph"))
            chem = fw.get("chemical") or fw.get("dosing_chemical")
            if tph not in (None, "") and chem:
                out["pre"] = {"enabled": True, "chemical": chem, "target_ph": tph}

    # Degassers
    for key, default_loc in (("degasser", "pre"), ("feed_degasser", "pre"), ("pre_degasser", "pre"),
                             ("permeate_degasser", "post"), ("post_degasser", "post"),
                             ("product_degasser", "post"), ("interstage_degasser", "interstage")):
        for src in (input_data.get(key), cond.get(key)):
            d = _cfg_dict(src)
            if d:
                loc = _location(d) or default_loc
                if loc == "interstage" and not two_pass:
                    loc = "post"
                if not out[f"{loc}_degasser"]:
                    out[f"{loc}_degasser"] = d
    return out


def _conditioning_info(step: Dict[str, Any], dosing_cfg: Dict[str, Any], ph_in: float, co2_in: float) -> Dict[str, Any]:
    """Report block for one dosing point (kept compatible with the old keys)."""
    return {
        "enabled": bool(dosing_cfg.get("enabled", False)),
        "chemical": step["chemical"] or dosing_cfg.get("chemical"),
        "dose_mg_l": step["dose_mg_l"],
        "target_ph": step["ph"],                 # pH actually reached (old key name)
        "requested_target_ph": dosing_cfg.get("target_ph"),
        "ph_in": round(ph_in, 3),
        "ph_out": step["ph"],
        "co2_in_mg_l": round(co2_in, 3),
        "co2_out_mg_l": step["co2_mg_l"],
        "co2_removed_mg_l": step["co2_removed_mg_l"],
        "degasser_applied": step["degasser_applied"],
        "degasser_co2_in_mg_l": step.get("degasser_co2_in_mg_l"),
        "degasser_co2_out_mg_l": step.get("degasser_co2_out_mg_l"),
        "degasser_ph_in": step.get("degasser_ph_in"),
        "degasser_ph_out": step.get("degasser_ph_out"),
        "notes": step["notes"],
    }


def _compute_nf_concentrate_scaling(conc_ions: Dict[str, float], feed_ph: float, temp_c: float) -> Dict[str, Any]:
    """
    Compute Saturation Indices for NF concentrate scalants using Davies ionic-strength
    correction for activity coefficients (spec Section 4.6).

    Scalants evaluated:
      - CaSO4 (Gypsum)   Ksp = 4.93e-5 mol²/L²
      - BaSO4 (Barite)   Ksp = 1.08e-10
      - SrSO4 (Celestite) Ksp = 3.44e-7
      - CaF2  (Fluorite) Ksp = 3.45e-11 mol³/L³
      - SiO2  (Amorphous) expressed as saturation %
      - CaCO3 (Calcite)   expressed as LSI
    """
    # Molecular weights
    _mw = {
        "Ca": 40.078, "Mg": 24.305, "Na": 22.990, "K": 39.098,
        "Ba": 137.327, "Sr": 87.62, "Cl": 35.45, "SO4": 96.06,
        "HCO3": 61.017, "NO3": 62.00, "F": 18.998, "PO4": 94.97,
        "NH4": 18.04, "Fe": 55.845, "Mn": 54.938
    }
    _charges = {
        "Ca": 2, "Mg": 2, "Na": 1, "K": 1, "Ba": 2, "Sr": 2,
        "Cl": 1, "SO4": 2, "HCO3": 1, "NO3": 1, "F": 1, "PO4": 3,
        "NH4": 1, "Fe": 2, "Mn": 2
    }

    # Ionic strength (mol/L) from concentrate ions
    I = 0.5 * sum(
        (conc_ions.get(ion, 0) / _mw[ion] / 1000.0) * z * z
        for ion, z in _charges.items() if ion in _mw
    )

    # Davies equation: logγ = −A·z² × (√I/(1+√I) − 0.3I)  [A ≈ 0.509 at 25°C]
    A_dav = 0.509
    sqrt_I = math.sqrt(max(I, 1e-12))

    def log_gamma(z):
        """Calculate log10 activity coefficient for ion charge z using the Davies equation."""
        return -A_dav * z * z * (sqrt_I / (1.0 + sqrt_I) - 0.3 * I)

    def gamma(z):
        """Calculate activity coefficient gamma for ion charge z."""
        return 10.0 ** log_gamma(z)

    def mol(ion):
        """Concentration of ion in concentrate as mol/L."""
        return max(0.0, conc_ions.get(ion, 0)) / _mw.get(ion, 50) / 1000.0

    results = {}

    # 1. CaSO4 (Gypsum) — SI = log10([Ca²⁺]γ²[SO4²⁻]γ² / Ksp)
    Ksp_gyp = 4.93e-5
    ip_gyp = mol("Ca") * mol("SO4") * gamma(2) ** 2
    si_gyp = math.log10(ip_gyp / Ksp_gyp) if ip_gyp > 0 else -99.0
    results["CaSO4_gypsum"] = {
        "SI": round(si_gyp, 3),
        "risk": "HIGH" if si_gyp > 0 else ("MODERATE" if si_gyp > -0.5 else "LOW"),
        "antiscalant_required": si_gyp > 0
    }

    # 2. BaSO4 (Barite) — Ksp = 1.08e-10
    Ksp_bar = 1.08e-10
    ip_bar = mol("Ba") * mol("SO4") * gamma(2) ** 2
    si_bar = math.log10(ip_bar / Ksp_bar) if ip_bar > 0 else -99.0
    results["BaSO4_barite"] = {
        "SI": round(si_bar, 3),
        "risk": "HIGH" if si_bar > 0 else ("MODERATE" if si_bar > -0.5 else "LOW"),
        "antiscalant_required": si_bar > 0
    }

    # 3. SrSO4 (Celestite) — Ksp = 3.44e-7
    Ksp_cel = 3.44e-7
    ip_cel = mol("Sr") * mol("SO4") * gamma(2) ** 2
    si_cel = math.log10(ip_cel / Ksp_cel) if ip_cel > 0 else -99.0
    results["SrSO4_celestite"] = {
        "SI": round(si_cel, 3),
        "risk": "HIGH" if si_cel > 0 else ("MODERATE" if si_cel > -0.5 else "LOW"),
        "antiscalant_required": si_cel > 0
    }

    # 4. CaF2 (Fluorite) — Ksp = 3.45e-11 mol³/L³
    Ksp_flu = 3.45e-11
    ip_flu = mol("Ca") * (mol("F") ** 2) * gamma(2) * (gamma(1) ** 2)
    si_flu = math.log10(ip_flu / Ksp_flu) if ip_flu > 0 else -99.0
    results["CaF2_fluorite"] = {
        "SI": round(si_flu, 3),
        "risk": "HIGH" if si_flu > 0 else ("MODERATE" if si_flu > -0.5 else "LOW"),
        "antiscalant_required": si_flu > 0
    }

    # 5. SiO2 amorphous — saturation % (spec: warn > 80%)
    sio2_c = max(0.0, conc_ions.get("SiO2", 0))
    # Solubility of amorphous SiO2 ≈ 100 mg/L at 25°C, slight positive T dependence
    sio2_sol = 100.0 + max(0.0, temp_c - 25.0) * 0.5
    sio2_sat_pct = (sio2_c / sio2_sol * 100.0) if sio2_sol > 0 else 0.0
    results["SiO2"] = {
        "sat_pct": round(sio2_sat_pct, 1),
        "conc_mg_l": round(sio2_c, 2),
        "solubility_mg_l": round(sio2_sol, 1),
        "risk": "HIGH" if sio2_sat_pct > 80 else ("MODERATE" if sio2_sat_pct > 60 else "LOW"),
        "antiscalant_required": sio2_sat_pct > 80
    }

    # 6. CaCO3 (Calcite) — Langelier SI at concentrate (simplified)
    # pHs = pK2 - pKsp + p[Ca²⁺] + p[HCO3⁻] - logγ(2) - logγ(1)
    # At 25°C: pK2 = 10.33, pKsp(Calcite) = 8.48
    ca_mol_c = mol("Ca")
    hco3_mol_c = mol("HCO3")
    if ca_mol_c > 0 and hco3_mol_c > 0:
        pHs = (10.33 - 8.48
               - math.log10(ca_mol_c)
               - math.log10(hco3_mol_c)
               - log_gamma(2) - log_gamma(1))
        lsi_conc = feed_ph - pHs  # use feed pH as surrogate (conservative)
    else:
        lsi_conc = -99.0
    results["CaCO3_calcite"] = {
        "LSI": round(lsi_conc, 3),
        "risk": "HIGH" if lsi_conc > 0 else ("MODERATE" if lsi_conc > -0.5 else "LOW"),
        "antiscalant_required": lsi_conc > 0
    }

    return results


class SystemEngine:
    def __init__(self):
        """Initialize SystemEngine with UF and RO calculation engines."""
        self.uf_engine = UFEngine()
        self.ro_engine = ROEngine()

    # ------------------------------------------------------------------
    # Shared helpers (used by calculate_system and the recycle solver)
    # ------------------------------------------------------------------
    def _run_uf(self, feed: Dict[str, Any], input_data: Dict[str, Any], gross_flow: float) -> Dict[str, Any]:
        """Run the UF engine on a given gross (fresh) feed flow."""
        return self.uf_engine.simulate_uf(
            gross_feed_flow_m3h=gross_flow,
            temp_c=feed.get("temperature", 25.0),
            module_name=input_data.get("uf_module", "PERMA-UF-i0875s40"),
            feed_turbidity=feed.get("turbidity", 20.0),
            feed_tss=feed.get("tss", 30.0),
            feed_tds=feed.get("tds", sum([v for k, v in feed.items() if isinstance(v, (int, float)) and k not in ["temperature", "ph", "turbidity", "tss", "tds"]])),
            feed_ph=feed.get("ph", 7.3)
        )

    @staticmethod
    def _condition_feed(ions: Dict[str, float], feed: Dict[str, Any], input_data: Dict[str, Any],
                        two_pass: bool = False):
        """
        Pre-treatment: acid/caustic dosing then decarbonator on the RO feed, ONCE.
        Returns (conditioned_ions, info_dict_or_None, feed_ph_after).
        info["co2_out_mg_l"] is the free CO2 of the treated feed (used for permeate pH).
        """
        from conditioning import condition_water, co2_from_ph, _num
        cfg = _resolve_conditioning(input_data, two_pass=two_pass)
        pre, degas = cfg["pre"], cfg["pre_degasser"]
        feed_ph = _num(feed.get("ph", feed.get("pH")), 7.0)
        co2_in = feed.get("co2") or feed.get("carbon_dioxide") or co2_from_ph(ions.get("HCO3", 0.0), feed_ph)
        if not (pre.get("enabled") or degas.get("enabled") or pre.get("co2_degassing")):
            return dict(ions), None, feed_ph
        step = condition_water(ions, feed_ph, pre, degas, co2_mg_l=co2_in, label="Pre-treatment")
        info = _conditioning_info(step, pre, feed_ph, co2_in)
        info["notes"] = [n for n in cfg["notes"] if "RO feed" in n] + info["notes"]
        info["location"] = "pre"
        return step["ions"], info, step["ph"]

    @staticmethod
    def _carbonate_ph(hco3_mg_l: float, co2_mg_l: float, fallback: float):
        from conditioning import ph_from_carbonate
        ph = ph_from_carbonate(hco3_mg_l, co2_mg_l)
        return round(ph, 2) if ph is not None else fallback

    def calculate_system(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point for system calculation.
        input_data must contain:
        - technology_train: e.g., "UF+RO", "RO", "UF+NF"
        - feed_water: dict of ions, temp, ph, tds
        - target_flow_m3h: float
        - target_recovery_pct: float
        - ro_membrane: str (model name)
        - uf_module: str (model name)
        - stages: int
        - vessels_per_stage: List[int]
        - elements_per_vessel: int, or one value per stage e.g. [6, 3]
        """
        train = input_data.get("technology_train", "RO")
        # FIX: work on a copy — the dosed pH used to be written back into the caller's
        # feed, so any repeat call (membrane recommender, ageing, re-calculate) saw the
        # feed already at the target pH and dosed nothing.
        feed = dict(input_data["feed_water"])
        target_flow = input_data["target_flow_m3h"]

        result = {
            "technology_train": train,
            # FIX 23 Nov 2026: the RAW feed (the local `feed` gets the treated pH below)
            "feed_water_used": dict(input_data["feed_water"]),
            "uf_results": None,
            "ro_results": None
        }

        # 1. UF Simulation
        if "UF" in train:
            # The system feed flow enters the UF.
            # UF engine expects gross_feed_flow_m3h (intake limited).
            # RECYCLE FIX: the recycle solver sizes the UF once on the FRESH feed and
            # passes the result in, so the recycle never goes through the UF.
            uf_res = input_data.get("_uf_results_override") or self._run_uf(feed, input_data, target_flow)
            result["uf_results"] = uf_res

            # The feed to the RO/NF system is the UF product
            ro_feed_flow = uf_res["overview"]["net_product_m3h"]
        else:
            # No UF, RO feed is direct from system feed flow
            ro_feed_flow = target_flow

        # RECYCLE FIX: recycle solver sets the RO pass feed (fresh + recycle) directly
        if input_data.get("_ro_feed_flow_override") is not None:
            ro_feed_flow = float(input_data["_ro_feed_flow_override"])

        # Standalone UF train (CHANGE 9)
        if train == "UF":
            eco_params = input_data.get("economic_params") or {}
            avail = eco_params.get("plant_availability", 0.90)
            hours_pa = avail * 8760.0
            uf_summary = uf_res.get("overview", {})
            q_net = uf_summary.get("net_product_m3h", target_flow)
            q_annual = q_net * hours_pa

            uf_modules = uf_summary.get("total_modules", uf_res.get("sizing", {}).get("total_modules", 1))
            uf_module_name = input_data.get("uf_module", "PERMA-UF-i0875s40")
            uf_mod = MembraneDatabase.get_uf_module(uf_module_name)
            uf_unit_cost = eco_params.get("uf_module_cost") or eco_params.get("uf_module_cost_inr") or uf_mod.get("unit_cost_inr", 100000.0)
            uf_capex_mem = uf_modules * uf_unit_cost
            uf_equip_sub = uf_capex_mem * 2.0
            ic_factor = eco_params.get("ic_factor") if eco_params.get("ic_factor") is not None else eco_params.get("installation_factor", 0.15)
            cont_factor = eco_params.get("contingency_factor", 0.10)
            uf_capex_total = uf_equip_sub * (1.0 + ic_factor) * (1.0 + cont_factor)

            feed_kw = uf_mod.get("feed_pump_kw_per_module", 0.75)
            bw_kw = uf_mod.get("backwash_pump_kw_per_module", 1.10)
            uf_kw = (feed_kw + bw_kw) * uf_modules
            tariff = eco_params.get("electricity_tariff", 7.50)
            uf_energy_pa = uf_kw * hours_pa * tariff
            uf_life = eco_params.get("uf_membrane_lifetime", 7.0)
            uf_repl_pa = uf_capex_mem / max(1.0, uf_life)
            uf_chem_pa = 7.0e-3 * q_annual * 30.0
            uf_opex_total = uf_energy_pa + uf_repl_pa + uf_chem_pa

            discount_rate = eco_params.get("discount_rate", 0.10)
            project_life = eco_params.get("project_life", 20.0)
            if project_life <= 0:
                crf = 0.0
            elif discount_rate > 0:
                denom = ((1.0 + discount_rate) ** project_life) - 1.0
                crf = (discount_rate * ((1.0 + discount_rate) ** project_life)) / denom if denom > 0 else (1.0 / project_life)
            else:
                crf = 1.0 / project_life
            annualised_capex = uf_capex_total * crf
            cost_per_kl = (annualised_capex + uf_opex_total) / max(1.0, q_annual)

            result["economics"] = {
                "capex": {"total_capex_inr": round(uf_capex_total, 2), "uf_membranes_inr": round(uf_capex_mem, 2)},
                "opex": {"total_opex_pa_inr": round(uf_opex_total, 2), "energy_cost_pa_inr": round(uf_energy_pa, 2), "uf_mem_repl_pa_inr": round(uf_repl_pa, 2)},
                "metrics": {"cost_per_kl_inr": round(cost_per_kl, 2), "annual_production_kl": round(q_annual, 0)}
            }
            result["uf_module"] = input_data.get("uf_module", "PERMA-UF-i0875s40")
            result["target_flow_m3h"] = target_flow
            return result

        # 2. RO/NF Simulation
        if "RO" in train or "NF" in train:
            # Extract ions from feed
            ions = {
                "Ca": feed.get("calcium", 0),
                "Mg": feed.get("magnesium", 0),
                "Na": feed.get("sodium", 0),
                "K": feed.get("potassium", 0),
                "Cl": feed.get("chloride", 0),
                "SO4": feed.get("sulfate", 0),
                "HCO3": feed.get("bicarbonate", 0),
                "Ba": feed.get("barium", 0),
                "Sr": feed.get("strontium", 0),
                "F": feed.get("fluoride", 0),
                "SiO2": feed.get("silica", 0),
                "B": feed.get("boron", 0),
                "NO3": feed.get("nitrate", 0),
                "PO4": feed.get("phosphate", 0),
                "NH4": feed.get("ammonium", 0),
                "Al": feed.get("aluminium", 0),
                "Fe": feed.get("iron", 0),
                "Mn": feed.get("manganese", 0)
            }

            # Feed conditioning and degasser before RO bisection (CHANGE 3 & 4)
            # RECYCLE FIX: skipped when the recycle solver has already conditioned the
            # fresh feed (otherwise the recycled concentrate is acid-dosed again).
            from conditioning import co2_from_ph, condition_water, _num
            ro_feed_co2 = None
            if not input_data.get("_feed_preconditioned", False):
                ions, feed_cond_info, cond_feed_ph = self._condition_feed(ions, feed, input_data)
                if feed_cond_info:
                    feed["ph"] = cond_feed_ph
                    result["feed_conditioning"] = feed_cond_info
                    ro_feed_co2 = feed_cond_info["co2_out_mg_l"]
            else:
                ro_feed_co2 = input_data.get("_feed_co2_mg_l")
                if input_data.get("_feed_conditioning_info"):
                    result["feed_conditioning"] = input_data["_feed_conditioning_info"]  # for OPEX
            ro_feed_ph = _num(feed.get("ph"), 7.0)
            if ro_feed_co2 is None:
                ro_feed_co2 = co2_from_ph(ions.get("HCO3", 0.0), ro_feed_ph)
            # Treated RO feed (after pre-treatment) — used by the physics / ageing engine
            result["ro_feed_ions"] = dict(ions)
            result["ro_feed_ph"] = round(ro_feed_ph, 3)
            result["ro_feed_co2_mg_l"] = round(ro_feed_co2, 3)

            # Genesys-calibrated scaling / antiscalant analysis on the RO feed after
            # pre-treatment dosing (added 21 Nov 2026 - scaling_engine.py)
            try:
                from scaling_engine import analyse as _scaling_analyse
                _sfeed = dict(ions)
                _sfeed["temperature"] = feed.get("temperature", 25.0)
                _sfeed["ph"] = feed.get("ph", 7.0)
                result["scaling_analysis"] = _scaling_analyse(
                    _sfeed, input_data.get("target_recovery_pct", 75.0),
                    antiscalant=input_data.get("antiscalant_product") or "auto",
                    feed_flow_m3h=input_data.get("_antiscalant_flow_m3h", ro_feed_flow), sweep=True)
            except Exception as _e:
                result["scaling_analysis"] = {"error": str(_e)}

            # Determine starting pressure based on TDS (rough estimate for converging solver)
            est_osmotic_bar = (sum(ions.values()) / 1000.0) * 0.7 # rough rule of thumb

            # Solve for feed pressure to achieve the target recovery
            target_recovery = input_data.get("target_recovery_pct", 75.0) / 100.0

            low_p = max(1.0, est_osmotic_bar - 5.0)
            high_p = max(120.0, est_osmotic_bar + 60.0)
            tol = input_data.get("_recovery_tol", 0.005) # 0.5% tolerance on recovery (recycle solver: 0.05%)

            ro_res = None
            for _ in range(25):
                mid_p = (low_p + high_p) / 2.0
                ro_res = self.ro_engine.simulate_system(
                    feed_flow_m3h=ro_feed_flow,
                    feed_pressure_bar=mid_p,
                    feed_ions=ions,
                    temp_c=feed.get("temperature", 25.0),
                    membrane_model=input_data.get("ro_membrane", "BW30-400"),
                    stages=input_data.get("stages", 2),
                    vessels_per_stage=input_data.get("vessels_per_stage", [4, 2]),
                    elements_per_vessel=input_data.get("elements_per_vessel", 6),
                    permeate_pressure_bar=input_data.get("permeate_pressure_bar", input_data.get("permeate_backpressure", 0.0)),
                    enable_booster=input_data.get("enable_booster", False),
                    interboost_dp_bar=input_data.get("interboost_dp_bar", None)
                )
                rec = ro_res["summary"]["total_recovery"]
                if abs(rec - target_recovery) < tol:
                    break
                if rec < target_recovery:
                    low_p = mid_p
                else:
                    high_p = mid_p

            result["ro_results"] = ro_res

            # ----------------------------------------------------------------
            # CARBONATE TRACKING through the RO (FIX 20 Nov 2026)
            # Free CO2 passes the membrane (~0 % rejection), so permeate and
            # concentrate carry the RO-feed CO2; their pH follows from HCO3/CO2.
            # (Toray Nadhi check: permeate pH 4.47 vs DS2 4.49; conc 6.67 vs 6.60)
            # ----------------------------------------------------------------
            s_ro = ro_res["summary"]
            raw_perm_ions = {k: v for k, v in s_ro.get("perm_ions", {}).items() if k != "CO2"}
            conc_ions_ro = s_ro.get("conc_ions", {})
            s_ro["feed_ph"] = round(ro_feed_ph, 2)
            s_ro["feed_co2_mg_l"] = round(ro_feed_co2, 3)
            s_ro["perm_co2_mg_l"] = round(ro_feed_co2, 3)
            if s_ro.get("perm_ph") is None:
                s_ro["perm_ph"] = self._carbonate_ph(raw_perm_ions.get("HCO3", 0.0), ro_feed_co2,
                                                     round(max(4.5, ro_feed_ph - 1.5), 2))
            if s_ro.get("conc_ph") is None:
                s_ro["conc_ph"] = self._carbonate_ph(conc_ions_ro.get("HCO3", 0.0), ro_feed_co2, ro_feed_ph)
            s_ro["ro_perm_ph"] = s_ro["perm_ph"]          # RO permeate before post-treatment

            # Post-treatment: decarbonator then caustic / acid trim on the product
            cfg_all = _resolve_conditioning(input_data)
            post_cfg, post_degas = cfg_all["post"], cfg_all["post_degasser"]
            if post_cfg.get("enabled") or post_degas.get("enabled") or post_cfg.get("co2_degassing"):
                ph_in = s_ro["perm_ph"]
                step = condition_water(raw_perm_ions, ph_in, post_cfg, post_degas,
                                       co2_mg_l=ro_feed_co2, label="Post-treatment")
                s_ro["conditioned_perm_ions"] = step["ions"]
                s_ro["product_ions"] = step["ions"]
                s_ro["product_tds"] = _tds(step["ions"])
                s_ro["product_ph"] = step["ph"]
                s_ro["product_co2_mg_l"] = step["co2_mg_l"]
                s_ro["perm_ph"] = step["ph"]              # old behaviour: perm_ph = final pH
                info = _conditioning_info(step, post_cfg, ph_in, ro_feed_co2)
                info["location"] = "post"
                if not input_data.get("_feed_preconditioned"):
                    info["notes"] = [n for n in cfg_all["notes"] if "post-treatment" in n] + info["notes"]
                result["permeate_conditioning"] = info
            else:
                s_ro["product_ions"] = raw_perm_ions
                s_ro["product_tds"] = _tds(raw_perm_ions)
                s_ro["product_ph"] = s_ro["perm_ph"]
                s_ro["product_co2_mg_l"] = round(ro_feed_co2, 3)

            # ----------------------------------------------------------------
            # NF-SPECIFIC ANALYSIS (feed quality, concentrate scaling, hard stop)
            # Runs only when the technology train includes an NF membrane.
            # ----------------------------------------------------------------
            if "NF" in train and ro_res:
                nf_feed_checks = []
                nf_warnings    = []

                # --- Feed quality pre-checks (spec Section 4.1 / Table 6) ---
                feed_tds  = feed.get("tds", sum(ions.values()))
                turbidity = feed.get("turbidity", 0.0) or 0.0
                sdi       = feed.get("sdi", 0.0) or 0.0
                toc       = feed.get("toc", 0.0) or 0.0
                cl2       = feed.get("cl2", 0.0) or 0.0
                iron_feed = feed.get("iron", 0.0) or 0.0
                mn_feed   = feed.get("manganese", 0.0) or 0.0
                feed_ph   = feed.get("ph", 7.0) or 7.0

                def _fq(code, sev, msg, val=None, lim=None):
                    """Record a feed water quality limit check result."""
                    entry = {"type": code, "severity": sev, "message": msg}
                    if val is not None: entry["value"] = round(val, 3)
                    if lim is not None: entry["limit"] = lim
                    nf_feed_checks.append(entry)

                if feed_tds > 8000:
                    _fq("NF-W-FQ-TDS", "CRITICAL",
                        f"Feed TDS {feed_tds:.0f} mg/L exceeds 8,000 limit — consider BWRO instead",
                        feed_tds, 8000)
                elif feed_tds > 5000:
                    _fq("NF-W-FQ-TDS", "WARNING",
                        f"Feed TDS {feed_tds:.0f} mg/L in caution range (5,000–8,000 mg/L)",
                        feed_tds, 5000)

                if sdi > 5:
                    _fq("NF-W-FQ-SDI", "CRITICAL",
                        f"SDI15 {sdi:.1f} > 5 — NF membrane protection insufficient; pretreatment required",
                        sdi, 5)
                elif sdi > 3:
                    _fq("NF-W-FQ-SDI", "WARNING",
                        f"SDI15 {sdi:.1f} > 3 — add multimedia filtration (MMF)",
                        sdi, 3)

                if iron_feed > 0.3:
                    _fq("NF-W-FQ-FE", "CRITICAL",
                        f"Fe(total) {iron_feed:.2f} mg/L > 0.3 — NF TFC membrane sensitive to iron fouling",
                        iron_feed, 0.3)
                elif iron_feed > 0.05:
                    _fq("NF-W-FQ-FE", "WARNING",
                        f"Fe(total) {iron_feed:.2f} mg/L > 0.05 — iron removal filter recommended",
                        iron_feed, 0.05)

                if mn_feed > 0.1:
                    _fq("NF-W-FQ-MN", "WARNING",
                        f"Mn {mn_feed:.2f} mg/L > 0.1 — greensand or KMnO4 treatment required",
                        mn_feed, 0.1)
                elif mn_feed > 0.05:
                    _fq("NF-W-FQ-MN", "WARNING",
                        f"Mn {mn_feed:.2f} mg/L > 0.05 — greensand filter recommended",
                        mn_feed, 0.05)

                if cl2 > 0.1:
                    _fq("NF-W-FQ-CL2", "CRITICAL",
                        f"Free Cl₂ {cl2:.2f} ppm > 0.1 — NF polyamide TFC membrane will oxidize",
                        cl2, 0.1)
                elif cl2 > 0.05:
                    _fq("NF-W-FQ-CL2", "WARNING",
                        f"Free Cl₂ {cl2:.2f} ppm in caution range — add SMBS dechlorination",
                        cl2, 0.05)

                if toc > 10:
                    _fq("NF-W-FQ-TOC", "CRITICAL",
                        f"TOC {toc:.1f} mg/L > 10 — high NOM fouling risk; NF not recommended",
                        toc, 10)
                elif toc > 3:
                    _fq("NF-W-FQ-TOC", "WARNING",
                        f"TOC {toc:.1f} mg/L > 3 — NOM fouling risk; add coagulation/PAC adsorption",
                        toc, 3)

                if turbidity > 1:
                    _fq("NF-W-FQ-TURB", "WARNING",
                        f"Turbidity {turbidity:.1f} NTU > 1 — add multimedia filtration",
                        turbidity, 1)

                if feed_ph < 4:
                    _fq("NF-W-FQ-PH", "CRITICAL",
                        f"Feed pH {feed_ph:.1f} < 4 — outside NF membrane continuous operation range",
                        feed_ph, 4)
                elif feed_ph < 6:
                    _fq("NF-W-FQ-PH", "WARNING",
                        f"Feed pH {feed_ph:.1f} in caution range — pH adjustment recommended",
                        feed_ph, 6)
                elif feed_ph > 9:
                    _fq("NF-W-FQ-PH", "WARNING",
                        f"Feed pH {feed_ph:.1f} > 9 — pH adjustment may be needed",
                        feed_ph, 9)

                # --- Pretreatment recommendations (spec Table 10 / Section 5.2) ---
                pretreatment = ["5 µm Cartridge Filter (always required before NF HP pump)"]
                if turbidity > 5 or sdi > 5:
                    pretreatment.append("Multimedia Filter (MMF) — remove particulates")
                if iron_feed > 0.05:
                    pretreatment.append("Iron Removal Filter (greensand/oxidation)")
                if mn_feed > 0.05:
                    pretreatment.append("Greensand / KMnO₄ filter for Mn removal")
                if cl2 > 0.05:
                    pretreatment.append("SMBS Dechlorination + PAC dosing")
                if toc > 3:
                    pretreatment.append("Coagulation–Flocculation or PAC Adsorption (NOM)")
                if feed_ph < 6 or feed_ph > 9:
                    pretreatment.append("pH Correction (acid / caustic dosing upstream)")

                # --- Concentrate scaling indices (spec Section 4.6 / Table 9) ---
                conc_ions_nf = ro_res["summary"].get("conc_ions", {})
                nf_scaling   = _compute_nf_concentrate_scaling(conc_ions_nf, feed_ph, feed.get("temperature", 25.0))

                # Antiscalant flag: any scalant with SI > 0 or SiO2 > 80%
                antiscalant_required = any(
                    v.get("antiscalant_required") for v in nf_scaling.values()
                )
                if antiscalant_required:
                    if "Antiscalant dosing (NF-specific formulation)" not in pretreatment:
                        pretreatment.append("Antiscalant dosing (NF-specific formulation) — at least one scalant SI > 0")

                # --- Hard stop: P_feed > 41 bar (NF-W-HYD-10) ---
                p_feed_nf = ro_res["summary"].get("feed_pressure_bar", 0.0)
                if p_feed_nf > 41.0:
                    nf_warnings.append({
                        "type": "NF-W-HYD-10",
                        "severity": "CRITICAL",
                        "message": (
                            f"P_feed {p_feed_nf:.1f} bar exceeds 41 bar maximum for NF 8\" elements — "
                            "STOP: reduce recovery, switch to BWRO, or add stages"
                        )
                    })

                ro_res["nf_analysis"] = {
                    "feed_quality_checks": nf_feed_checks,
                    "pretreatment_recommendations": pretreatment,
                    "concentrate_scaling": nf_scaling,
                    "antiscalant_required": antiscalant_required,
                    "nf_warnings": nf_warnings
                }
                result["ro_results"] = ro_res

            # --- Economic Calculation ---
            eco_params = input_data.get("economic_params")
            if eco_params and ro_res:
                summary = ro_res["summary"]
                mem_type = input_data.get("ro_membrane", "BW30-400")
                membrane = MembraneDatabase.get_ro_membrane(mem_type)

                # Always determine membrane price from the membrane type to avoid
                # stale cached values from the frontend's eco-mem-cost input
                if mem_type and "nf" in mem_type.lower():
                    elem_price = 19200.0
                elif membrane and membrane.get("type", "").upper() == "SWRO":
                    elem_price = 30240.0
                elif membrane and membrane.get("nominal_rejection", membrane.get("rejection_pct", 0)) >= 0.995:
                    elem_price = 30240.0
                else:
                    elem_price = 26880.0


                vessels_per_stage = input_data.get("vessels_per_stage", [4, 2])
                n_vessels = sum(vessels_per_stage)
                n_elements = _total_elements(vessels_per_stage, input_data.get("elements_per_vessel", 6),
                                             input_data.get("stages", len(vessels_per_stage)))

                c_membranes = n_elements * elem_price
                c_vessels = n_vessels * eco_params.get("vessel_cost", 48000.0)

                hp_kw = summary.get("hp_pump_power_kw", 0.0)
                bp_kw = summary.get("booster_pump_power_kw", 0.0)

                pump_cost_kw = eco_params.get("pump_cost_kw", 96000.0)
                c_hp_pump = hp_kw * pump_cost_kw
                c_bp_pump = bp_kw * pump_cost_kw

                # --- UF CAPEX/OPEX (added when UF train selected) ---
                c_uf_modules = 0.0
                c_uf_pumps = 0.0
                uf_energy_cost_pa = 0.0
                uf_mem_repl_pa = 0.0
                uf_chem_cost_pa = 0.0
                uf_capex_breakdown = {}

                uf_res = result.get("uf_results")
                if uf_res:
                    uf_mod_name = input_data.get("uf_module", "PERMA-UF-i0875s40")
                    uf_mod = MembraneDatabase.get_uf_module(uf_mod_name)
                    n_uf_modules = uf_res["overview"]["total_modules"]

                    # CAPEX: UF modules + UF pumps
                    # Use user-specified cost if provided, else fall back to database default
                    uf_unit_cost = eco_params.get("uf_module_cost", uf_mod.get("unit_cost_inr", 120000.0))
                    c_uf_modules = n_uf_modules * uf_unit_cost

                    uf_feed_kw = uf_mod.get("feed_pump_kw_per_module", 0.75) * n_uf_modules
                    uf_bw_kw   = uf_mod.get("backwash_pump_kw_per_module", 1.10) * n_uf_modules
                    c_uf_pumps = (uf_feed_kw + uf_bw_kw) * pump_cost_kw

                    # OPEX: UF energy (feed + BW pumps), CEB chemicals, UF membrane replacement
                    avail_uf = eco_params.get("plant_availability", 0.90)
                    hours_pa_uf = avail_uf * 8760.0
                    tariff = eco_params.get("electricity_tariff", 7.50)
                    uf_energy_cost_pa = (uf_feed_kw + uf_bw_kw) * hours_pa_uf * tariff

                    # CEB chemicals: ~7 g per m³ of net UF permeate (citric acid + NaOCl blended)
                    # Industry practice: dilute CEB ~2x per week, ~200 mg/L NaOCl + 2000 mg/L citric acid
                    # Effective dose blended across production volume ≈ 0.007 kg/m³ net permeate
                    net_uf_flow_m3h = uf_res["overview"]["net_product_m3h"]
                    ceb_kg_pa = 0.007 * net_uf_flow_m3h * hours_pa_uf   # 7 g/m³ net permeate
                    uf_chem_cost_pa = ceb_kg_pa * 30.0                   # ₹30/kg average CEB chemical cost

                    # UF module replacement: ~7 year life
                    uf_mem_life = eco_params.get("uf_membrane_lifetime", 7.0)
                    uf_mem_repl_pa = c_uf_modules / uf_mem_life if uf_mem_life > 0 else 0.0

                    uf_capex_breakdown = {
                        "uf_modules_inr": round(c_uf_modules, 2),
                        "uf_pumps_inr": round(c_uf_pumps, 2),
                        "uf_modules_count": n_uf_modules,
                    }

                c_equip_sub = c_membranes + c_vessels + c_hp_pump + c_bp_pump + c_uf_modules + c_uf_pumps

                ic_factor = eco_params.get("ic_factor", 0.15)
                c_ic = c_equip_sub * ic_factor

                contingency_factor = eco_params.get("contingency_factor", 0.10)
                c_contingency = (c_equip_sub + c_ic) * contingency_factor

                total_capex = c_equip_sub + c_ic + c_contingency

                # OPEX
                avail = eco_params.get("plant_availability", 0.90)
                hours_pa = avail * 8760.0

                total_kw = summary.get("total_power_kw", 0.0)
                tariff = eco_params.get("electricity_tariff", 7.50)
                energy_cost_pa = total_kw * hours_pa * tariff + uf_energy_cost_pa

                mem_life = eco_params.get("membrane_lifetime", 5.0)
                ro_mem_repl_pa = c_membranes / mem_life if mem_life > 0 else 0
                # uf_mem_repl_pa already computed above (0.0 when no UF)
                total_mem_repl_pa = ro_mem_repl_pa + uf_mem_repl_pa

                # Antiscalant chemical OPEX (CHANGE 8; Genesys products 21 Nov 2026)
                as_type = input_data.get("antiscalant_type", "Phosphonate")
                as_dose = input_data.get("antiscalant_dose_mg_l", 3.0)
                _sel = (result.get("scaling_analysis") or {}).get("selected") or {}
                _prod = str(input_data.get("antiscalant_product") or "manual").lower()
                if _sel and (_prod != "manual" or as_dose is None):
                    as_dose = _sel["dose"]["total_feed_dose_mg_l"]
                    as_type = _sel["product"]
                as_dose = as_dose or 0.0
                as_costs = {"Phosphonate": 250.0, "Polycarboxylate": 320.0, "Dendrimer": 450.0}
                as_cost_kg = eco_params.get("antiscalant_cost_per_kg") or as_costs.get(as_type, 280.0)
                antiscalant_cost_pa = 0.0
                if input_data.get("antiscalant_dosed", True):
                    # RECYCLE FIX: antiscalant is dosed into the fresh RO feed, not the recycle
                    as_flow = input_data.get("_antiscalant_flow_m3h", ro_feed_flow)
                    antiscalant_cost_pa = (as_flow * hours_pa * (as_dose / 1000.0)) * as_cost_kg

                # FIX 20 Nov 2026: pH-dosing chemicals were never costed for single-pass RO
                chem_price = eco_params.get("chemical_cost_per_kg", 20.0)   # INR/kg, 100 % basis
                fc = result.get("feed_conditioning") or {}
                pc = result.get("permeate_conditioning") or {}
                as_flow_chem = input_data.get("_antiscalant_flow_m3h", ro_feed_flow)
                chem_kg_pa = (fc.get("dose_mg_l", 0.0) * as_flow_chem
                              + pc.get("dose_mg_l", 0.0) * summary.get("perm_flow", 0.0)) / 1000.0 * hours_pa
                ph_chem_cost_pa = chem_kg_pa * chem_price

                total_opex_pa = energy_cost_pa + total_mem_repl_pa + uf_chem_cost_pa + antiscalant_cost_pa + ph_chem_cost_pa

                # Cost per KL
                discount_rate = eco_params.get("discount_rate", 0.10)
                project_life = eco_params.get("project_life", 20.0)
                crf = 0.0
                if discount_rate > 0 and project_life > 0:
                    crf = (discount_rate * ((1 + discount_rate) ** project_life)) / (((1 + discount_rate) ** project_life) - 1)

                annualised_capex = total_capex * crf
                total_annual_cost = annualised_capex + total_opex_pa

                q_perm = summary.get("perm_flow", 0.0)
                q_annual = q_perm * hours_pa

                cost_per_kl = total_annual_cost / q_annual if q_annual > 0 else 0.0

                result["economics"] = {
                    "unit_membrane_cost_inr": elem_price,
                    "capex": {
                        "membranes_inr": round(c_membranes, 2),
                        "vessels_inr": round(c_vessels, 2),
                        "hp_pump_inr": round(c_hp_pump, 2),
                        "booster_pump_inr": round(c_bp_pump, 2),
                        **uf_capex_breakdown,
                        "equip_subtotal_inr": round(c_equip_sub, 2),
                        "ic_inr": round(c_ic, 2),
                        "contingency_inr": round(c_contingency, 2),
                        "total_capex_inr": round(total_capex, 2)
                    },
                    "opex": {
                        "annual_hours": round(hours_pa, 0),
                        "energy_cost_pa_inr": round(energy_cost_pa, 2),
                        "ro_mem_repl_pa_inr": round(ro_mem_repl_pa, 2),
                        "uf_mem_repl_pa_inr": round(uf_mem_repl_pa, 2),
                        "membrane_repl_pa_inr": round(total_mem_repl_pa, 2),  # kept for backward compat
                        "uf_ceb_chemicals_pa_inr": round(uf_chem_cost_pa, 2),
                        "antiscalant_cost_pa_inr": round(antiscalant_cost_pa, 2),
                        "antiscalant_product": as_type,
                        "antiscalant_dose_mg_l": round(as_dose, 2),
                        "chemical_cost_pa_inr": round(ph_chem_cost_pa, 2),
                        "total_opex_pa_inr": round(total_opex_pa, 2)
                    },
                    "metrics": {
                        "crf": round(crf, 4),
                        "annualised_capex_inr": round(annualised_capex, 2),
                        "total_annual_cost_inr": round(total_annual_cost, 2),
                        "annual_production_kl": round(q_annual, 0),
                        "cost_per_kl_inr": round(cost_per_kl, 2)
                    }
                }

        result["ro_membrane"] = input_data.get("ro_membrane", "BW30-400")
        result["uf_module"] = input_data.get("uf_module", "PERMA-UF-i0875s40")
        result["stages_count"] = input_data.get("stages", 2)
        result["vessels_per_stage"] = input_data.get("vessels_per_stage", [4, 2])
        result["elements_per_vessel"] = _epv_out(input_data.get("elements_per_vessel", 6),
                                                 input_data.get("stages", 2))
        result["target_recovery_pct"] = input_data.get("target_recovery_pct", 75.0)
        result["target_flow_m3h"] = input_data.get("target_flow_m3h", 50.0)

        return result

    def calculate_system_with_recycle(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Concentrate recycle on the Toray DS2 / WAVE basis (rewritten 20 Nov 2026).

        Inputs (in addition to the calculate_system keys):
          target_flow_m3h      FRESH (raw) feed to the system, m3/h
          target_recovery_pct  SYSTEM recovery = product / fresh RO feed, %  (held fixed)
          recycle_flow_m3h     recycle flow, m3/h (Toray input; takes priority), or
          recycle_ratio        fraction of the TOTAL concentrate returned to the HP-pump
                               suction, 0 to < 0.95

        Method (same order as Toray DS2):
          1. Pretreat the FRESH feed only: UF sized on the fresh flow (once), then pH
             conditioning / degasser (once)                -> treated feed  F, Ct
          2. Flow balance:  Qp = Rsys*F,  Qd = F - Qp,  Qpass = F + Qr,
             Rpass = Qp / Qpass                            (pass recovery is a RESULT)
          3. Concentrate from the OVERALL salt balance (recycle does not enter it):
                 Cc = (F*Ct - Qp*Cp) / Qd
          4. Blend:  Cb = (F*Ct + Qr*Cc) / Qpass
          5. Solve the RO pass at Qpass, Rpass, Cb -> new Cp. Repeat 3-5 until Cp, Qp
             and Cc settle (only Cp is unknown, so this closes in 2-4 passes).
          6. Check the salt balance  F*Ct = Qp*Cp + Qd*Cc  and report a Toray-style
             stream table.
        """
        rec_flow_in = input_data.get("recycle_flow_m3h")
        rec_flow_in = float(rec_flow_in) if rec_flow_in not in (None, "") else 0.0
        recycle_ratio = float(input_data.get("recycle_ratio", 0.0) or 0.0)

        # No recycle -> normal path
        if rec_flow_in <= 1e-6 and recycle_ratio <= 0.001:
            return self.calculate_system(input_data)

        train = input_data.get("technology_train", "RO")
        if not ("RO" in train or "NF" in train):
            return self.calculate_system(input_data)

        feed = dict(input_data["feed_water"])          # never mutate the caller's feed
        fresh_flow = float(input_data["target_flow_m3h"])
        r_sys = float(input_data.get("target_recovery_pct", 75.0)) / 100.0
        warnings: List[Dict[str, Any]] = []

        # ---- Step 1: pretreatment of the FRESH feed (once) -----------------------
        uf_res = None
        if "UF" in train:
            uf_res = self._run_uf(feed, input_data, fresh_flow)
            F = float(uf_res["overview"]["net_product_m3h"])   # fresh RO feed
        else:
            F = fresh_flow

        raw_ions = {ek: float(feed.get(fk, 0.0) or 0.0) for fk, ek in ION_KEYS}
        treated, cond_info, treated_ph = self._condition_feed(raw_ions, feed, input_data)
        treated = {k: float(treated.get(k, 0.0) or 0.0) for k in raw_ions}
        from conditioning import co2_from_ph
        # Free CO2 of the treated feed; the recycle carries about the same CO2
        # (CO2 passes the membrane), so the blend CO2 is taken equal to it.
        treated_co2 = cond_info["co2_out_mg_l"] if cond_info else co2_from_ph(treated.get("HCO3", 0.0), treated_ph)

        # ---- Step 2: flow balance -------------------------------------------------
        qp_target = r_sys * F
        qd_target = F - qp_target
        if qd_target <= 0:
            raise ValueError("System recovery must be below 100 % when recycle is used.")

        if rec_flow_in > 1e-6:
            Qr = rec_flow_in
            recycle_basis = "flow"
            recycle_ratio = Qr / (Qr + qd_target)            # report as fraction of total conc
        else:
            if recycle_ratio >= 0.95:
                raise ValueError("recycle_ratio must be < 0.95 (fraction of total concentrate).")
            Qr = recycle_ratio * qd_target / (1.0 - recycle_ratio)
            recycle_basis = "fraction of total concentrate"

        Qpass = F + Qr
        r_pass = qp_target / Qpass

        # ---- Steps 3-5: iterate on permeate quality only -----------------------
        cp = {k: 0.0 for k in treated}        # first guess: perfect rejection
        qp = qp_target
        max_iter = 20
        tol = 1e-4                            # 0.01 % on Qp and on concentrate TDS
        converged = False
        result = None
        iterations_used = 0
        blended_feed = None
        c_blend = dict(treated)
        c_conc = dict(treated)

        for it in range(1, max_iter + 1):
            iterations_used = it
            qd = F - qp

            # Step 3: concentrate from the overall balance
            c_conc = {k: max(0.0, (F * treated[k] - qp * cp.get(k, 0.0)) / qd) for k in treated}
            # Step 4: blend of treated fresh feed + recycle
            c_blend = {k: (F * treated[k] + Qr * c_conc[k]) / Qpass for k in treated}

            blended_feed = dict(feed)
            for fk, ek in ION_KEYS:
                blended_feed[fk] = c_blend[ek]
            blended_feed["tds"] = _tds(c_blend)
            # Blend pH from blend HCO3 and CO2 (Toray Nadhi: treated 6.00 -> blend 6.16)
            blend_ph = self._carbonate_ph(c_blend.get("HCO3", 0.0), treated_co2, treated_ph)
            blended_feed["ph"] = blend_ph

            # Step 5: solve the pass at Qpass / Rpass (no UF rerun, no re-dosing)
            run = dict(input_data)
            for key in ("recycle_enabled", "recycle_ratio", "recycle_flow_m3h"):
                run.pop(key, None)
            run.update({
                "feed_water": blended_feed,
                "target_flow_m3h": fresh_flow,
                "target_recovery_pct": r_pass * 100.0,
                "_ro_feed_flow_override": Qpass,
                "_uf_results_override": uf_res,
                "_feed_preconditioned": True,
                "_feed_co2_mg_l": treated_co2,
                "_feed_conditioning_info": cond_info,
                "_recovery_tol": 0.0005,
                "_antiscalant_flow_m3h": F,
            })
            result = self.calculate_system(run)
            ro_res = result.get("ro_results")
            if not ro_res:
                warnings.append({"type": "Recycle solver: RO pass returned no result"})
                break

            s = ro_res["summary"]
            qp_new = float(s.get("perm_flow", 0.0))
            cp_new = {k: float(s.get("perm_ions", {}).get(k, 0.0)) for k in treated}
            qd_new = F - qp_new
            if qd_new <= 0:
                warnings.append({"type": "Recycle solver: permeate exceeds fresh feed"})
                break
            c_conc_new = {k: max(0.0, (F * treated[k] - qp_new * cp_new[k]) / qd_new) for k in treated}

            d_qp = abs(qp_new - qp) / max(qp, 1e-9)
            d_cc = abs(_tds(c_conc_new) - _tds(c_conc)) / max(_tds(c_conc), 1e-9)
            cp, qp = cp_new, qp_new
            if d_qp < tol and d_cc < tol:
                converged = True
                c_conc = c_conc_new
                break

        if result is None or not result.get("ro_results"):
            # Fall back to a plain run so the caller still gets a result
            fallback = self.calculate_system(input_data)
            fallback["recycle"] = {"enabled": True, "converged": False, "warnings": warnings}
            return fallback

        # ---- Step 6: balance check and reporting ---------------------------------
        ro_res = result["ro_results"]
        s = ro_res["summary"]
        qp = float(s["perm_flow"])
        qd = F - qp
        q_conc_total = float(s.get("conc_flow", Qr + qd))
        conc_engine = {k: float(s.get("conc_ions", {}).get(k, 0.0)) for k in treated}
        perm_ions = {k: float(s.get("perm_ions", {}).get(k, 0.0)) for k in treated}

        salt_in = F * _tds(treated)
        salt_out = qp * _tds(perm_ions) + qd * _tds(conc_engine)
        balance_err_pct = (salt_out - salt_in) / salt_in * 100.0 if salt_in > 0 else 0.0
        if abs(balance_err_pct) > 0.5:
            warnings.append({"type": "Recycle mass balance error > 0.5 %",
                             "value": round(balance_err_pct, 2), "limit": 0.5})
        if not converged:
            warnings.append({"type": f"Recycle loop did not converge in {max_iter} iterations"})
        if abs(q_conc_total - (Qr + qd)) > 0.01 * max(q_conc_total, 1e-9):
            warnings.append({"type": "Recycle flow split mismatch",
                             "value": round(q_conc_total, 3), "limit": round(Qr + qd, 3)})

        system_recovery = qp / F if F > 0 else 0.0
        pass_recovery = qp / Qpass if Qpass > 0 else 0.0
        p_feed = float(s.get("feed_pressure_bar", 0.0))
        p_conc = float(s.get("conc_pressure_bar", 0.0))

        # Pass-level summary keeps the engine's own numbers; add system-level ones
        s["pass_recovery"] = pass_recovery
        s["system_recovery"] = system_recovery
        s["fresh_feed_flow"] = F
        s["recycle_flow"] = Qr
        s["drain_flow"] = qd
        s["treated_feed_tds"] = _tds(treated)
        s["blend_feed_tds"] = _tds(c_blend)

        streams = [{"no": 1, "name": "Raw feed", "flow_m3h": fresh_flow,
                    "tds_mg_l": _tds(raw_ions), "pressure_bar": 0.0, "ph": feed.get("ph", 7.0)}]
        if uf_res:
            streams.append({"no": 2, "name": "UF product (fresh RO feed)", "flow_m3h": F,
                            "tds_mg_l": _tds(raw_ions), "pressure_bar": 0.0, "ph": feed.get("ph", 7.0)})
        streams += [
            {"no": 3, "name": "Treated feed", "flow_m3h": F, "tds_mg_l": _tds(treated),
             "pressure_bar": 0.0, "ph": treated_ph},
            {"no": 4, "name": "Feed to pass (treated feed + recycle)", "flow_m3h": Qpass,
             "tds_mg_l": _tds(c_blend), "pressure_bar": p_feed, "ph": blended_feed.get("ph", treated_ph)},
            {"no": 5, "name": "Total concentrate", "flow_m3h": Qr + qd,
             "tds_mg_l": _tds(conc_engine), "pressure_bar": p_conc, "ph": s.get("conc_ph")},
            {"no": 6, "name": "Recycle", "flow_m3h": Qr,
             "tds_mg_l": _tds(conc_engine), "pressure_bar": p_conc, "ph": s.get("conc_ph")},
            {"no": 7, "name": "Concentrate to drain", "flow_m3h": qd,
             "tds_mg_l": _tds(conc_engine), "pressure_bar": p_conc, "ph": s.get("conc_ph")},
            {"no": 8, "name": "Product", "flow_m3h": qp,
             "tds_mg_l": _tds(s.get("product_ions") or perm_ions),
             "pressure_bar": float(s.get("permeate_pressure_bar", 0.0)), "ph": s.get("product_ph")},
        ]
        for st in streams:
            st["flow_m3h"] = round(st["flow_m3h"], 3)
            st["tds_mg_l"] = round(st["tds_mg_l"], 2)
            st["pressure_bar"] = round(st["pressure_bar"], 2)

        result["feed_water_used"] = input_data["feed_water"]      # fresh feed, not the blend
        result["blended_feed_water"] = blended_feed
        result["target_flow_m3h"] = fresh_flow
        result["target_recovery_pct"] = r_sys * 100.0
        if cond_info:
            result["feed_conditioning"] = cond_info
        result["treated_feed_ph"] = round(treated_ph, 3)

        result["recycle"] = {
            "enabled": True,
            "basis": recycle_basis,
            "recycle_ratio": round(recycle_ratio, 4),           # fraction of total concentrate
            "recycle_flow_m3h": round(Qr, 4),
            "recycle_pct_of_fresh_feed": round(Qr / F * 100.0, 2) if F > 0 else 0.0,
            "fresh_feed_flow_m3h": fresh_flow,
            "fresh_ro_feed_flow_m3h": round(F, 4),
            "blended_feed_flow_m3h": round(Qpass, 4),
            "blended_feed_tds_mg_l": round(_tds(c_blend), 1),
            "blended_feed_ions": c_blend,                        # converged blend for physics engine
            "treated_feed_ions": treated,
            "treated_feed_tds_mg_l": round(_tds(treated), 1),
            "concentrate_ions": conc_engine,
            "concentrate_tds_mg_l": round(_tds(conc_engine), 1),
            "total_concentrate_flow_m3h": round(Qr + qd, 4),
            "drain_flow_m3h": round(qd, 4),
            "pass_recovery_pct": round(pass_recovery * 100.0, 2),
            "effective_system_recovery": round(system_recovery, 4),
            "effective_system_recovery_pct": round(system_recovery * 100.0, 2),
            "feed_pressure_bar": round(p_feed, 2),
            "permeate_tds_mg_l": round(_tds(perm_ions), 2),
            "mass_balance_error_pct": round(balance_err_pct, 3),
            "iterations_to_converge": iterations_used,
            "converged": converged,
            "streams": streams,
            "warnings": warnings,
        }
        if not converged:
            result["recycle"]["warning"] = "Recycle loop did not converge within {} iterations".format(max_iter)
        return result

    def simulate_two_pass_system(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Orchestrates 2-Pass RO with interstage conditioning and recycle"""
        import sys
        import os
        sys.path.append(os.path.dirname(__file__))
        from conditioning import condition_water, co2_from_ph, _num

        pass1_cfg = input_data.get("pass1", {})
        pass2_cfg = input_data.get("pass2", {})
        cond_cfg = input_data.get("conditioning", {})
        rec_cfg = input_data.get("recycle", {})
        feed = dict(input_data["feed_water"])          # FIX: never mutate the caller's feed
        fresh_flow = input_data["target_flow_m3h"]
        # FIX 20 Nov 2026: pre-treatment, interstage and post-treatment dosing points
        # and their degassers are all read here (pre/post were ignored in 2P-RO before)
        cond_points = _resolve_conditioning(input_data, two_pass=True)

        ion_keys = [
            ("calcium", "Ca"), ("magnesium", "Mg"), ("sodium", "Na"),
            ("potassium", "K"), ("chloride", "Cl"), ("sulfate", "SO4"),
            ("bicarbonate", "HCO3"), ("barium", "Ba"), ("strontium", "Sr"),
            ("fluoride", "F"), ("silica", "SiO2"), ("boron", "B"),
            ("nitrate", "NO3"), ("phosphate", "PO4"), ("ammonium", "NH4"),
            ("aluminium", "Al"), ("iron", "Fe"), ("manganese", "Mn")
        ]
        fresh_ions = {ek: feed.get(fk, 0.0) for fk, ek in ion_keys}

        # Pre-treatment (acid + decarbonator) on the FRESH feed, once
        pre_info = None
        fresh_ions, pre_info, feed_ph_treated = self._condition_feed(fresh_ions, feed, input_data, two_pass=True)
        fresh_ions = {ek: fresh_ions.get(ek, 0.0) for _, ek in ion_keys}
        feed_co2 = pre_info["co2_out_mg_l"] if pre_info else co2_from_ph(fresh_ions.get("HCO3", 0.0), feed_ph_treated)
        inter_info = None

        # Helper to convert Pydantic to dict if needed
        def to_dict(obj):
            """Convert Pydantic model or mapping to standard Python dict."""
            if hasattr(obj, "dict"): return obj.dict()
            return obj if isinstance(obj, dict) else {}

        pass1_cfg = to_dict(pass1_cfg)
        pass2_cfg = to_dict(pass2_cfg)
        cond_cfg = to_dict(cond_cfg)
        rec_cfg = to_dict(rec_cfg)

        recycle_enabled = rec_cfg.get("enabled", False)
        if isinstance(rec_cfg, dict):
            recycle_ratio = rec_cfg.get("recycle_ratio", 0.0) if recycle_enabled else 0.0
        else:
            recycle_ratio = getattr(rec_cfg, "recycle_ratio", 0.0) if recycle_enabled else 0.0

        max_iter = 40          # FIX: was 15 — salt in the loop settles slower than flow
        tolerance = 0.001
        q_r_prev = 0.0
        c_r_prev = {k: 0.0 for k in fresh_ions}
        q_p2_prev = None
        tds_r_prev = None      # FIX: convergence now also checks recycle TDS

        converged = False
        final_p1_res = None
        final_p2_res = None
        cond_dose = 0.0
        iterations_used = 0

        for iteration in range(max_iter):
            iterations_used += 1

            q_blend = fresh_flow + q_r_prev
            c_blend = {}
            for k in fresh_ions:
                c_blend[k] = (fresh_ions[k]*fresh_flow + c_r_prev.get(k,0)*q_r_prev) / q_blend if q_blend > 0 else 0

            p1_est_osmotic = (sum(c_blend.values()) / 1000.0) * 0.7
            p1_low = max(1.0, p1_est_osmotic - 5.0)
            p1_high = max(120.0, p1_est_osmotic + 60.0)
            p1_target_rec = pass1_cfg.get("target_recovery_pct", 75.0) / 100.0

            p1_res = None
            for _ in range(25):
                mid_p = (p1_low + p1_high) / 2.0
                p1_res = self.ro_engine.simulate_system(
                    feed_flow_m3h=q_blend,
                    feed_pressure_bar=mid_p,
                    feed_ions=c_blend,
                    temp_c=feed.get("temperature", 25.0),
                    membrane_model=pass1_cfg.get("membrane", "BW30-400"),
                    stages=pass1_cfg.get("stages", 2),
                    vessels_per_stage=pass1_cfg.get("vessels_per_stage", [4,2]),
                    elements_per_vessel=pass1_cfg.get("elements_per_vessel", 6),
                    permeate_pressure_bar=input_data.get("permeate_pressure_bar", input_data.get("permeate_backpressure", 0.0)),
                    enable_booster=input_data.get("enable_booster", False),
                    interboost_dp_bar=input_data.get("interboost_dp_bar", None)
                )
                rec = p1_res["summary"]["total_recovery"]
                if abs(rec - p1_target_rec) < 0.005: break
                if rec < p1_target_rec: p1_low = mid_p
                else: p1_high = mid_p

            p1_perm_flow = p1_res["summary"]["perm_flow"]
            p1_perm_ions = p1_res["summary"]["perm_ions"]

            # Pass-1 permeate pH from HCO3 and CO2 (CO2 passes the membrane)
            p1_perm_ions = {k: v for k, v in p1_perm_ions.items() if k not in ("CO2", "pH")}
            p1_perm_ph = p1_res["summary"].get("perm_ph")
            if p1_perm_ph is None:
                p1_perm_ph = self._carbonate_ph(p1_perm_ions.get("HCO3", 0.0), feed_co2,
                                                round(max(4.5, feed_ph_treated - 1.5), 2))
                p1_res["summary"]["perm_ph"] = p1_perm_ph
            p1_res["summary"]["perm_co2_mg_l"] = round(feed_co2, 3)
            p1_res["summary"]["feed_co2_mg_l"] = round(feed_co2, 3)
            p1_res["summary"]["feed_ph"] = round(feed_ph_treated, 2)
            if p1_res["summary"].get("conc_ph") is None:
                p1_res["summary"]["conc_ph"] = self._carbonate_ph(
                    p1_res["summary"].get("conc_ions", {}).get("HCO3", 0.0), feed_co2, feed_ph_treated)

            # Interstage: decarbonator and/or caustic before pass 2
            inter_cfg, inter_degas = cond_points["interstage"], cond_points["interstage_degasser"]
            step = condition_water(p1_perm_ions, p1_perm_ph, inter_cfg, inter_degas,
                                   co2_mg_l=feed_co2, label="Interstage")
            p2_feed_ions = step["ions"]
            cond_dose = step["dose_mg_l"]
            p2_feed_ph, p2_feed_co2 = step["ph"], step["co2_mg_l"]
            inter_info = _conditioning_info(step, inter_cfg, p1_perm_ph, feed_co2)

            p2_est_osmotic = (sum(p2_feed_ions.values()) / 1000.0) * 0.7
            p2_low = max(1.0, p2_est_osmotic - 2.0)
            p2_high = max(60.0, p2_est_osmotic + 40.0)
            p2_target_rec = pass2_cfg.get("target_recovery_pct", 85.0) / 100.0

            # Auto-size Pass 2 vessels
            # Pass 2 feed = Pass 1 permeate (p1_perm_flow m3/h)
            # Required permeate = p1_perm_flow * p2_target_rec
            # Each element area ~37 m2 (8040 element), design flux = 20 LMH
            # Permeate per element = 37 * 20 / 1000 = 0.74 m3/h
            # Min elements needed = required_perm / 0.74
            p2_mem_model = pass2_cfg.get("membrane", "BW30-400")
            p2_membrane = MembraneDatabase.get_ro_membrane(p2_mem_model)
            elem_area_m2 = p2_membrane.get("active_area_m2", 37.0) if p2_membrane else 37.0
            design_flux_lmh = 20.0
            perm_per_elem = (elem_area_m2 * design_flux_lmh) / 1000.0  # m3/h
            required_perm = p1_perm_flow * p2_target_rec
            min_elements = max(1, int(required_perm / perm_per_elem) + 1)
            p2_elems_per_vessel = pass2_cfg.get("elements_per_vessel", 6)
            p2_stages = pass2_cfg.get("stages", 1)
            # Compute min vessels needed (split across stages if multi-stage)
            _p2_epv = normalize_elements_per_vessel(p2_elems_per_vessel, p2_stages)
            min_vessels_total = max(1, int(min_elements / (sum(_p2_epv) / len(_p2_epv))) + 1)
            user_vessels = pass2_cfg.get("vessels_per_stage", [2])
            user_vessels_total = sum(user_vessels) if isinstance(user_vessels, list) else user_vessels
            if user_vessels_total < min_vessels_total:
                # Auto-scale vessels per stage proportionally
                scale = min_vessels_total / max(1, user_vessels_total)
                p2_vessels_per_stage = [max(1, round(v * scale)) for v in (user_vessels if isinstance(user_vessels, list) else [user_vessels])]
                print("[2P-RO] Auto-sized P2 vessels from %s -> %s (need %d for %.0f%% rec of %.1f m3/h)" % (
                    user_vessels, p2_vessels_per_stage, min_vessels_total, p2_target_rec*100, p1_perm_flow))
            else:
                p2_vessels_per_stage = user_vessels if isinstance(user_vessels, list) else [user_vessels]

            p2_res = None
            for _ in range(25):
                mid_p = (p2_low + p2_high) / 2.0
                p2_res = self.ro_engine.simulate_system(
                    feed_flow_m3h=p1_perm_flow,
                    feed_pressure_bar=mid_p,
                    feed_ions=p2_feed_ions,
                    temp_c=feed.get("temperature", 25.0),
                    membrane_model=pass2_cfg.get("membrane", "BW30-400"),
                    stages=p2_stages,
                    vessels_per_stage=p2_vessels_per_stage,
                    elements_per_vessel=p2_elems_per_vessel,
                    beta_cap=None,
                    permeate_pressure_bar=pass2_cfg.get("permeate_pressure_bar", input_data.get("permeate_pressure_bar", input_data.get("permeate_backpressure", 0.0))),
                    enable_booster=pass2_cfg.get("enable_booster", input_data.get("enable_booster", False)),
                    interboost_dp_bar=pass2_cfg.get("interboost_dp_bar", input_data.get("interboost_dp_bar", None))
                )
                rec = p2_res["summary"]["total_recovery"]
                if abs(rec - p2_target_rec) < 0.005: break
                if rec < p2_target_rec: p2_low = mid_p
                else: p2_high = mid_p

            p2_conc_flow = p2_res["summary"]["conc_flow"]
            p2_conc_ions = p2_res["summary"]["conc_ions"]
            p2_perm_flow = p2_res["summary"]["perm_flow"]

            q_r_new = recycle_ratio * p2_conc_flow
            c_r_new = p2_conc_ions.copy()

            tds_r_new = _tds(c_r_new)
            if q_p2_prev is not None and q_p2_prev > 0 and tds_r_prev:
                delta = abs(p2_perm_flow - q_p2_prev) / q_p2_prev
                delta_tds = abs(tds_r_new - tds_r_prev) / tds_r_prev
                if delta < tolerance and delta_tds < tolerance:
                    converged = True
                    q_r_prev = q_r_new
                    c_r_prev = c_r_new
                    final_p1_res = p1_res
                    final_p2_res = p2_res
                    break

            q_r_prev = q_r_new
            c_r_prev = c_r_new
            q_p2_prev = p2_perm_flow
            tds_r_prev = tds_r_new
            final_p1_res = p1_res
            final_p2_res = p2_res

        # Pass-2 permeate pH, then post-treatment on the final product
        post_info = None
        if final_p2_res:
            s2 = final_p2_res["summary"]
            p2_perm = {k: v for k, v in s2.get("perm_ions", {}).items() if k not in ("CO2", "pH")}
            if s2.get("perm_ph") is None:
                s2["perm_ph"] = self._carbonate_ph(p2_perm.get("HCO3", 0.0), p2_feed_co2,
                                                   round(max(4.5, p2_feed_ph - 1.0), 2))
            s2["perm_co2_mg_l"] = round(p2_feed_co2, 3)
            s2["ro_perm_ph"] = s2["perm_ph"]
            post_cfg, post_degas = cond_points["post"], cond_points["post_degasser"]
            if post_cfg.get("enabled") or post_degas.get("enabled") or post_cfg.get("co2_degassing"):
                ph_in = s2["perm_ph"]
                pstep = condition_water(p2_perm, ph_in, post_cfg, post_degas,
                                        co2_mg_l=p2_feed_co2, label="Post-treatment")
                s2["conditioned_perm_ions"] = pstep["ions"]
                s2["product_ions"], s2["product_tds"] = pstep["ions"], _tds(pstep["ions"])
                s2["product_ph"], s2["product_co2_mg_l"] = pstep["ph"], pstep["co2_mg_l"]
                s2["perm_ph"] = pstep["ph"]
                post_info = _conditioning_info(pstep, post_cfg, ph_in, p2_feed_co2)
            else:
                s2["product_ions"], s2["product_tds"] = p2_perm, _tds(p2_perm)
                s2["product_ph"], s2["product_co2_mg_l"] = s2["perm_ph"], round(p2_feed_co2, 3)

        eco_params = to_dict(input_data.get("economic_params", {}))
        economics = None
        if eco_params and final_p1_res and final_p2_res:
            # chemical kg/h of the pre- and post-treatment points, added to the interstage dose
            extra_chem_kg_h = ((pre_info or {}).get("dose_mg_l", 0.0) * fresh_flow
                               + (post_info or {}).get("dose_mg_l", 0.0) * final_p2_res["summary"]["perm_flow"]) / 1000.0
            economics = self._calculate_two_pass_economics(eco_params, pass1_cfg, pass2_cfg, final_p1_res, final_p2_res,
                                                           cond_dose, p1_perm_flow, extra_chem_kg_h=extra_chem_kg_h)

        return {
            "technology_train": input_data.get("technology_train", "2P-RO"),
            "feed_water_used": input_data["feed_water"],
            "pass1_results": final_p1_res,
            "pass2_results": final_p2_res,
            # FIX: configs use the key "membrane" (report always showed BW30-400)
            "ro_membrane": pass1_cfg.get("membrane", pass1_cfg.get("ro_membrane", "BW30-400")),
            "pass2_membrane": pass2_cfg.get("membrane", pass2_cfg.get("ro_membrane", "BW30-400")),
            "uf_module": input_data.get("uf_module", "PERMA-UF-i0875s40"),
            "stages_count": pass1_cfg.get("stages", 2),
            "vessels_per_stage": pass1_cfg.get("vessels_per_stage", [4, 2]),
            "elements_per_vessel": _epv_out(pass1_cfg.get("elements_per_vessel", 6), pass1_cfg.get("stages", 2)),
            "target_recovery_pct": input_data.get("target_recovery_pct", 75.0),
            "target_flow_m3h": input_data.get("target_flow_m3h", 50.0),
            "conditioning": {
                # interstage block (old keys kept for the UI)
                "enabled": bool((inter_info or {}).get("enabled", False)),
                "target_ph": (inter_info or {}).get("ph_out", cond_cfg.get("target_ph")),
                "chemical": (inter_info or {}).get("chemical", cond_cfg.get("chemical")),
                "dose_mg_l": round(cond_dose, 2),
                "interstage": inter_info,
                "notes": cond_points["notes"] + ((inter_info or {}).get("notes") or []),
            },
            "feed_conditioning": pre_info,
            "permeate_conditioning": post_info,
            # Treated pass-1 fresh feed (after pre-treatment) — used by the physics engine
            "ro_feed_ions": dict(fresh_ions),
            "ro_feed_ph": round(feed_ph_treated, 3),
            "ro_feed_co2_mg_l": round(feed_co2, 3),
            "recycle": {
                "enabled": recycle_enabled,
                "recycle_ratio": recycle_ratio,
                "recycle_flow_m3h": round(q_r_prev, 4),
                "converged": converged,
                "iterations": iterations_used,
                # Fields expected by the Concentrate Recycle UI card
                "fresh_feed_flow_m3h": fresh_flow,
                "blended_feed_flow_m3h": round(fresh_flow + q_r_prev, 4),
                "blended_feed_tds_mg_l": round(sum(c_blend.values()), 1),
                "blended_feed_ions": c_blend,   # converged blended ions for physics engine
                "effective_system_recovery": round(
                    (final_p2_res["summary"]["perm_flow"] / fresh_flow) if fresh_flow > 0 else 0, 4
                ),
                "effective_system_recovery_pct": round(
                    (final_p2_res["summary"]["perm_flow"] / fresh_flow * 100) if fresh_flow > 0 else 0, 2
                ),
                "feed_pressure_bar": round(
                    final_p1_res["summary"]["feed_pressure_bar"] if final_p1_res else 0.0, 2
                ),
                "permeate_tds_mg_l": round(
                    final_p2_res["summary"]["perm_tds"] if final_p2_res else 0.0, 1
                ),
                **({
                    "warning": "2P-RO recycle loop did not converge within {} iterations".format(max_iter)
                } if not converged else {})
            },
            "system_summary": {
                "fresh_feed_flow_m3h": fresh_flow,
                "final_permeate_flow_m3h": final_p2_res["summary"]["perm_flow"],
                "overall_recovery": final_p2_res["summary"]["perm_flow"] / fresh_flow if fresh_flow > 0 else 0,
                "overall_recovery_pct": (final_p2_res["summary"]["perm_flow"] / fresh_flow * 100) if fresh_flow > 0 else 0,
                "final_permeate_tds": final_p2_res["summary"]["perm_tds"],
                "total_power_kw": final_p1_res["summary"]["total_power_kw"] + final_p2_res["summary"]["total_power_kw"],
                "sec_kwh_m3": (final_p1_res["summary"]["total_power_kw"] + final_p2_res["summary"]["total_power_kw"]) / final_p2_res["summary"]["perm_flow"] if final_p2_res["summary"]["perm_flow"] > 0 else 0
            },
            "economics": economics
        }

    def _calculate_two_pass_economics(self, eco_params, pass1_cfg, pass2_cfg, p1_res, p2_res, cond_dose, p1_perm_flow,
                                     extra_chem_kg_h: float = 0.0):
        """Calculate combined capital and operating expenditures for two-pass RO system."""
        mem1_price = 26880.0
        mem2_price = 26880.0

        vps1 = pass1_cfg.get("vessels_per_stage", [4, 2])
        vps2 = pass2_cfg.get("vessels_per_stage", [2])
        n_vessels1, n_vessels2 = sum(vps1), sum(vps2)
        n_elems1 = _total_elements(vps1, pass1_cfg.get("elements_per_vessel", 6), pass1_cfg.get("stages", len(vps1)))
        n_elems2 = _total_elements(vps2, pass2_cfg.get("elements_per_vessel", 6), pass2_cfg.get("stages", len(vps2)))

        c_membranes = (n_elems1 * mem1_price) + (n_elems2 * mem2_price)
        c_vessels = (n_vessels1 + n_vessels2) * eco_params.get("vessel_cost", 48000.0)

        hp_kw = p1_res["summary"]["hp_pump_power_kw"] + p2_res["summary"]["hp_pump_power_kw"]
        bp_kw = p1_res["summary"]["booster_pump_power_kw"] + p2_res["summary"]["booster_pump_power_kw"]

        pump_cost_kw = eco_params.get("pump_cost_kw", 96000.0)
        c_hp_pump = hp_kw * pump_cost_kw
        c_bp_pump = bp_kw * pump_cost_kw

        c_equip_sub = c_membranes + c_vessels + c_hp_pump + c_bp_pump
        ic_factor = eco_params.get("ic_factor", 0.15)
        contingency_factor = eco_params.get("contingency_factor", 0.10)
        c_ic = c_equip_sub * ic_factor
        c_contingency = (c_equip_sub + c_ic) * contingency_factor
        total_capex = c_equip_sub + c_ic + c_contingency

        avail = eco_params.get("plant_availability", 0.90)
        hours_pa = avail * 8760.0
        tariff = eco_params.get("electricity_tariff", 7.50)
        energy_cost_pa = (hp_kw + bp_kw) * hours_pa * tariff
        mem_life = eco_params.get("membrane_lifetime", 5.0)
        mem_repl_pa = c_membranes / mem_life if mem_life > 0 else 0.0

        # interstage dose + pre/post-treatment doses (FIX: pre/post were not costed)
        chem_kg_pa = ((cond_dose / 1000.0) * p1_perm_flow + extra_chem_kg_h) * hours_pa
        chem_cost_pa = chem_kg_pa * eco_params.get("chemical_cost_per_kg", 20.0)

        total_opex_pa = energy_cost_pa + mem_repl_pa + chem_cost_pa

        discount = eco_params.get("discount_rate", 0.10)
        life = eco_params.get("project_life", 20.0)
        crf = (discount * ((1 + discount)**life)) / (((1 + discount)**life) - 1) if discount > 0 else 0
        annualised_capex = total_capex * crf
        total_annual = annualised_capex + total_opex_pa

        q_annual = p2_res["summary"]["perm_flow"] * hours_pa
        cost_per_kl = total_annual / q_annual if q_annual > 0 else 0

        return {
            "unit_membrane_cost_inr": mem1_price,
            "capex": {
                "membranes_inr": round(c_membranes, 2),
                "vessels_inr": round(c_vessels, 2),
                "hp_pump_inr": round(c_hp_pump, 2),
                "booster_pump_inr": round(c_bp_pump, 2),
                "equip_subtotal_inr": round(c_equip_sub, 2),
                "ic_inr": round(c_ic, 2),
                "contingency_inr": round(c_contingency, 2),
                "total_capex_inr": round(total_capex, 2)
            },
            "opex": {
                "annual_hours": round(hours_pa, 0),
                "energy_cost_pa_inr": round(energy_cost_pa, 2),
                "membrane_repl_pa_inr": round(mem_repl_pa, 2),
                "chemical_cost_pa_inr": round(chem_cost_pa, 2),
                "total_opex_pa_inr": round(total_opex_pa, 2)
            },
            "metrics": {
                "crf": round(crf, 4),
                "annualised_capex_inr": round(annualised_capex, 2),
                "annual_production_kl": round(q_annual, 2),
                "total_annual_cost_inr": round(total_annual, 2),
                "cost_per_kl_inr": round(cost_per_kl, 2)
            }
        }
