"""
Multi-Technology System Engine
Orchestrates UF, RO, and NF calculations based on the selected technology train.
"""

import math
from typing import Dict, Any, List
from uf_engine import UFEngine
from calc_engine import ROEngine
from membrane_database import MembraneDatabase


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
        return -A_dav * z * z * (sqrt_I / (1.0 + sqrt_I) - 0.3 * I)

    def gamma(z):
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
        self.uf_engine = UFEngine()
        self.ro_engine = ROEngine()
        
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
        - elements_per_vessel: int
        """
        train = input_data.get("technology_train", "RO")
        feed = input_data["feed_water"]
        target_flow = input_data["target_flow_m3h"]
        
        result = {
            "technology_train": train,
            "feed_water_used": feed,
            "uf_results": None,
            "ro_results": None
        }
        
        # 1. UF Simulation
        if "UF" in train:
            # The system feed flow enters the UF.
            # UF engine expects gross_feed_flow_m3h (intake limited).
            uf_res = self.uf_engine.simulate_uf(
                gross_feed_flow_m3h=target_flow,
                temp_c=feed.get("temperature", 25.0),
                module_name=input_data.get("uf_module", "PERMA-UF-i0875s40"),
                feed_turbidity=feed.get("turbidity", 20.0),
                feed_tss=feed.get("tss", 30.0),
                feed_tds=feed.get("tds", sum([v for k,v in feed.items() if isinstance(v, (int, float)) and k not in ["temperature", "ph", "turbidity", "tss", "tds"]])),
                feed_ph=feed.get("ph", 7.3)
            )
            result["uf_results"] = uf_res
            
            # The feed to the RO/NF system is the UF product
            ro_feed_flow = uf_res["overview"]["net_product_m3h"]
        else:
            # No UF, RO feed is direct from system feed flow
            ro_feed_flow = target_flow
            
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
            
            # Determine starting pressure based on TDS (rough estimate for converging solver)
            est_osmotic_bar = (sum(ions.values()) / 1000.0) * 0.7 # rough rule of thumb
            
            # Solve for feed pressure to achieve the target recovery
            target_recovery = input_data.get("target_recovery_pct", 75.0) / 100.0
            
            low_p = max(1.0, est_osmotic_bar - 5.0)
            high_p = max(120.0, est_osmotic_bar + 60.0)
            tol = 0.005 # 0.5% tolerance on recovery
            
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
                    elements_per_vessel=input_data.get("elements_per_vessel", 6)
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
                n_elements = n_vessels * input_data.get("elements_per_vessel", 6)
                
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
                
                total_opex_pa = energy_cost_pa + total_mem_repl_pa + uf_chem_cost_pa
                
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
        result["elements_per_vessel"] = input_data.get("elements_per_vessel", 6)
        result["target_recovery_pct"] = input_data.get("target_recovery_pct", 75.0)
        result["target_flow_m3h"] = input_data.get("target_flow_m3h", 50.0)
            
        return result

    def calculate_system_with_recycle(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Wrapper around calculate_system() that implements concentrate recycle.
        Iteratively blends a fraction of the last-stage concentrate back into
        the fresh feed until steady state is reached.

        Additional input_data keys:
          - recycle_ratio: float 0.0–1.0 (fraction of concentrate recycled)
        """
        recycle_ratio = input_data.get("recycle_ratio", 0.0)

        # If recycle is 0 or negligible, just call the normal path
        if recycle_ratio <= 0.001:
            return self.calculate_system(input_data)

        # 1. Run baseline (0% recycle) calculation to return at the top-level
        baseline_input = dict(input_data)
        baseline_input.pop("recycle_enabled", None)
        baseline_input.pop("recycle_ratio", None)
        final_result = self.calculate_system(baseline_input)

        feed = input_data["feed_water"]
        fresh_flow = input_data["target_flow_m3h"]

        # Build fresh-feed ion dict (same extraction as calculate_system)
        ion_keys = [
            ("calcium", "Ca"), ("magnesium", "Mg"), ("sodium", "Na"),
            ("potassium", "K"), ("chloride", "Cl"), ("sulfate", "SO4"),
            ("bicarbonate", "HCO3"), ("barium", "Ba"), ("strontium", "Sr"),
            ("fluoride", "F"), ("silica", "SiO2"), ("boron", "B"),
            ("nitrate", "NO3"), ("phosphate", "PO4"), ("ammonium", "NH4"),
            ("aluminium", "Al"), ("iron", "Fe"), ("manganese", "Mn")
        ]
        fresh_ions = {}
        for feed_key, engine_key in ion_keys:
            fresh_ions[engine_key] = feed.get(feed_key, 0)

        # Iteration state
        max_iter = 15
        tolerance = 0.002  # 0.2 % relative change in permeate flow
        q_r_prev = 0.0
        c_r_prev = {k: v for k, v in fresh_ions.items()}  # placeholder
        q_p_prev = None

        converged = False
        result = None
        iterations_used = 0

        for iteration in range(max_iter):
            iterations_used = iteration + 1

            # 1. Blend feed
            q_blend = fresh_flow + q_r_prev
            c_blend = {}
            for ion in fresh_ions:
                c_blend[ion] = (fresh_ions[ion] * fresh_flow + c_r_prev.get(ion, 0) * q_r_prev) / q_blend

            # 2. Build a modified input_data with blended feed
            blended_feed = dict(feed)
            for feed_key, engine_key in ion_keys:
                blended_feed[feed_key] = c_blend[engine_key]
            blended_feed["tds"] = sum(c_blend.values())

            modified_input = dict(input_data)
            modified_input["feed_water"] = blended_feed
            modified_input["target_flow_m3h"] = q_blend
            # Remove recycle keys so nested call doesn't recurse
            modified_input.pop("recycle_enabled", None)
            modified_input.pop("recycle_ratio", None)

            # 3. Call the EXISTING engine (completely unchanged)
            result = self.calculate_system(modified_input)

            # 4. Extract concentrate info from RO results
            ro_res = result.get("ro_results")
            if not ro_res:
                break

            summary = ro_res["summary"]
            q_p = summary.get("perm_flow", 0)
            q_c = summary.get("conc_flow", 0)

            # Get concentrate ions from the last element of the RO system
            elements_data = ro_res.get("elements", [])
            if elements_data:
                last_elem = elements_data[-1]
                c_c = last_elem.get("rej_ions", c_r_prev)
            else:
                c_c = c_r_prev

            # 5. Update recycle stream
            q_r_new = recycle_ratio * q_c
            c_r_new = {k: v for k, v in c_c.items()}

            # 6. Check convergence
            if q_p_prev is not None and q_p_prev > 0:
                delta = abs(q_p - q_p_prev) / q_p_prev
                if delta < tolerance:
                    converged = True
                    q_r_prev = q_r_new
                    c_r_prev = c_r_new
                    break

            # 7. Store for next iteration
            q_r_prev = q_r_new
            c_r_prev = c_r_new
            q_p_prev = q_p

        # 8. Add recycle metrics
        fresh_flow = input_data["target_flow_m3h"]

        # 8. Augment the baseline final_result with recycle metadata
        if result:
            q_p_final = 0
            feed_pressure_final = 0.0
            perm_tds_final = 0.0
            if result.get("ro_results"):
                ro_sum = result["ro_results"]["summary"]
                q_p_final = ro_sum.get("perm_flow", 0)
                feed_pressure_final = ro_sum.get("feed_pressure_bar", 0.0)
                perm_tds_final = ro_sum.get("perm_tds", 0.0)

            effective_recovery = q_p_final / fresh_flow if fresh_flow > 0 else 0

            result["recycle"] = {
                "enabled": True,
                "recycle_ratio": recycle_ratio,
                "recycle_flow_m3h": round(q_r_prev, 4),
                "blended_feed_flow_m3h": round(fresh_flow + q_r_prev, 4),
                "blended_feed_tds_mg_l": round(result["feed_water_used"].get("tds", 0.0), 1),
                "blended_feed_ions": c_blend,   # converged blended ions for physics engine
                "fresh_feed_flow_m3h": fresh_flow,
                "iterations_to_converge": iterations_used,
                "converged": converged,
                "effective_system_recovery": round(effective_recovery, 4),
                "effective_system_recovery_pct": round(effective_recovery * 100, 2),
                "feed_pressure_bar": round(feed_pressure_final, 2),
                "permeate_tds_mg_l": round(perm_tds_final, 1)
            }

            if not converged:
                result["recycle"]["warning"] = "Recycle loop did not converge within {} iterations".format(max_iter)

            return result

        return final_result

    def simulate_two_pass_system(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Orchestrates 2-Pass RO with interstage conditioning and recycle"""
        import sys
        import os
        sys.path.append(os.path.dirname(__file__))
        from conditioning import apply_conditioning
        
        pass1_cfg = input_data.get("pass1", {})
        pass2_cfg = input_data.get("pass2", {})
        cond_cfg = input_data.get("conditioning", {})
        rec_cfg = input_data.get("recycle", {})
        feed = input_data["feed_water"]
        fresh_flow = input_data["target_flow_m3h"]
        
        ion_keys = [
            ("calcium", "Ca"), ("magnesium", "Mg"), ("sodium", "Na"),
            ("potassium", "K"), ("chloride", "Cl"), ("sulfate", "SO4"),
            ("bicarbonate", "HCO3"), ("barium", "Ba"), ("strontium", "Sr"),
            ("fluoride", "F"), ("silica", "SiO2"), ("boron", "B"),
            ("nitrate", "NO3"), ("phosphate", "PO4"), ("ammonium", "NH4"),
            ("aluminium", "Al"), ("iron", "Fe"), ("manganese", "Mn")
        ]
        fresh_ions = {ek: feed.get(fk, 0.0) for fk, ek in ion_keys}
        
        # Helper to convert Pydantic to dict if needed
        def to_dict(obj):
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
            
        max_iter = 15
        tolerance = 0.002
        q_r_prev = 0.0
        c_r_prev = {k: 0.0 for k in fresh_ions}
        q_p2_prev = None
        
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
                    elements_per_vessel=pass1_cfg.get("elements_per_vessel", 6)
                )
                rec = p1_res["summary"]["total_recovery"]
                if abs(rec - p1_target_rec) < 0.005: break
                if rec < p1_target_rec: p1_low = mid_p
                else: p1_high = mid_p
                
            p1_perm_flow = p1_res["summary"]["perm_flow"]
            p1_perm_ions = p1_res["summary"]["perm_ions"]
            
            p2_feed_ions, cond_dose, cond_ph = apply_conditioning(p1_perm_ions, cond_cfg)
            
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
            min_vessels_total = max(1, int(min_elements / p2_elems_per_vessel) + 1)
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
                    beta_cap=1.20
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
            
            if q_p2_prev is not None and q_p2_prev > 0:
                delta = abs(p2_perm_flow - q_p2_prev) / q_p2_prev
                if delta < tolerance:
                    converged = True
                    q_r_prev = q_r_new
                    c_r_prev = c_r_new
                    final_p1_res = p1_res
                    final_p2_res = p2_res
                    break
                    
            q_r_prev = q_r_new
            c_r_prev = c_r_new
            q_p2_prev = p2_perm_flow
            final_p1_res = p1_res
            final_p2_res = p2_res
            
        eco_params = to_dict(input_data.get("economic_params", {}))
        economics = None
        if eco_params and final_p1_res and final_p2_res:
            economics = self._calculate_two_pass_economics(eco_params, pass1_cfg, pass2_cfg, final_p1_res, final_p2_res, cond_dose, p1_perm_flow)

        return {
            "technology_train": input_data.get("technology_train", "2P-RO"),
            "feed_water_used": input_data["feed_water"],
            "pass1_results": final_p1_res,
            "pass2_results": final_p2_res,
            "ro_membrane": pass1_cfg.get("ro_membrane", "BW30-400"),
            "pass2_membrane": pass2_cfg.get("ro_membrane", "BW30-400"),
            "uf_module": input_data.get("uf_module", "PERMA-UF-i0875s40"),
            "stages_count": pass1_cfg.get("stages", 2),
            "vessels_per_stage": pass1_cfg.get("vessels_per_stage", [4, 2]),
            "elements_per_vessel": pass1_cfg.get("elements_per_vessel", 6),
            "target_recovery_pct": input_data.get("target_recovery_pct", 75.0),
            "target_flow_m3h": input_data.get("target_flow_m3h", 50.0),
            "conditioning": {
                "enabled": cond_cfg.get("enabled", False),
                "target_ph": cond_cfg.get("target_ph"),
                "chemical": cond_cfg.get("chemical"),
                "dose_mg_l": round(cond_dose, 2)
            },
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

    def _calculate_two_pass_economics(self, eco_params, pass1_cfg, pass2_cfg, p1_res, p2_res, cond_dose, p1_perm_flow):
        mem1_price = 26880.0
        mem2_price = 26880.0
        
        n_vessels1 = sum(pass1_cfg.get("vessels_per_stage", [4,2]))
        n_elems1 = n_vessels1 * pass1_cfg.get("elements_per_vessel", 6)
        n_vessels2 = sum(pass2_cfg.get("vessels_per_stage", [2]))
        n_elems2 = n_vessels2 * pass2_cfg.get("elements_per_vessel", 6)
        
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
        
        chem_kg_pa = (cond_dose / 1000.0) * p1_perm_flow * hours_pa
        chem_cost_pa = chem_kg_pa * 20.0
        
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
