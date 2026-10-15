"""
Physics-Based Membrane Aging Engine (DEPRECATED)
Element-wise Fouling, Scaling & Degradation Engine for PACE.

DEPRECATION NOTICE: As of the unified engine update, the /api/simulate-aging
endpoint now routes through PhysicsAgingEngine (physics_aging_engine.py) instead
of this module, ensuring both the Membrane Aging tab and the Year-wise Projection
tab produce identical results. This file is retained for reference but is no longer
called in production.

Computes time-dependent effective membrane parameters:
  - A_eff(s,e,t): water permeability (reduced by fouling + compaction + oxidation)
  - B_eff(s,e,t): salt permeability (increased by oxidative damage)
  - dh_eff(s,e,t): hydraulic diameter (narrowed by deposits)

Four degradation mechanisms:
  1. Fouling (cake, biofouling, NOM adsorption)
  2. Scaling (crystal growth from PHREEQC SI)
  3. Oxidative damage (Cl2 exposure)
  4. Physical compaction (pressure-driven densification)
"""

import math
import copy
from typing import Dict, List, Any, Optional, Tuple
from calc_engine import ROEngine
from membrane_database import MembraneDatabase

# ──────────────────────────────────────────────────────────────────────────────
# Appendix A: Mineral Crystal Growth Rate Parameters
# Γ_m values referenced to R_m = 1.26e11 m⁻¹ (HPA-RO-8040 at 25°C)
# ──────────────────────────────────────────────────────────────────────────────
MINERAL_PARAMS = {
    "Calcite":    {"n": 2, "gamma_m": 8.6e-7,  "k_g": 2.0e-8, "alpha_scale": 4.3e10, "M_w": 0.1001, "delta_si_antiscalant": 0.5, "cip_rev_frac": 0.90, "cip_irrev_frac": 0.10},
    "Aragonite":  {"n": 2, "gamma_m": 6.0e-7,  "k_g": 1.5e-8, "alpha_scale": 4.0e10, "M_w": 0.1001, "delta_si_antiscalant": 0.5, "cip_rev_frac": 0.90, "cip_irrev_frac": 0.10},
    "Gypsum":     {"n": 2, "gamma_m": 1.3e-7,  "k_g": 5.0e-9, "alpha_scale": 1.5e10, "M_w": 0.1722, "delta_si_antiscalant": 0.3, "cip_rev_frac": 0.90, "cip_irrev_frac": 0.10},
    "Anhydrite":  {"n": 2, "gamma_m": 0.8e-7,  "k_g": 3.0e-9, "alpha_scale": 2.0e10, "M_w": 0.1361, "delta_si_antiscalant": 0.3, "cip_rev_frac": 0.90, "cip_irrev_frac": 0.10},
    "Barite":     {"n": 2, "gamma_m": 0.7e-7,  "k_g": 5.0e-10,"alpha_scale": 6.0e10, "M_w": 0.2334, "delta_si_antiscalant": 0.2, "cip_rev_frac": 0.50, "cip_irrev_frac": 0.50},
    "Celestite":  {"n": 2, "gamma_m": 0.6e-7,  "k_g": 8.0e-10,"alpha_scale": 4.0e10, "M_w": 0.1836, "delta_si_antiscalant": 0.2, "cip_rev_frac": 0.50, "cip_irrev_frac": 0.50},
    "Fluorite":   {"n": 2, "gamma_m": 0.4e-7,  "k_g": 1.0e-9, "alpha_scale": 5.0e10, "M_w": 0.0781, "delta_si_antiscalant": 0.1, "cip_rev_frac": 0.90, "cip_irrev_frac": 0.10},
    "SiO2(a)":   {"n": 1, "gamma_m": 0.2e-7,  "k_g": 1.0e-9, "alpha_scale": 3.5e10, "M_w": 0.0601, "delta_si_antiscalant": 0.1, "cip_rev_frac": 0.40, "cip_irrev_frac": 0.60},
}

# Reference R_m for Γ_m scaling (HPA-RO-8040)
R_M_REFERENCE = 1.26e11  # m⁻¹

# ──────────────────────────────────────────────────────────────────────────────
# Appendix B: Default Model Calibration Constants
# ──────────────────────────────────────────────────────────────────────────────
DEFAULT_MODEL_PARAMS = {
    # Cake fouling
    "gamma_c": 2.5e-6,         # FRI per LMH per SDI per hour
    "k_rem": 5.0e-4,           # h⁻¹ (~4.3% of cake removed per day)
    "r_sp_cake": 1.0e12,       # m⁻² specific cake resistance

    # Biofouling
    "mu_bio_ref": 1.2e-3,      # h⁻¹ at TOC=2 mg/L, 25°C
    "k_shear": 4.0e-4,         # h⁻¹ at v_ref = 0.20 m/s
    "beta_bio": 0.012,         # /mg-L (FRI_bio,max = beta_bio * TOC)
    "k_mu_T": 0.05,            # °C⁻¹
    "TOC_ref": 2.0,            # mg/L
    "T_ref": 25.0,             # °C
    "v_ref": 0.20,             # m/s reference crossflow velocity

    # NOM adsorption
    "kappa_rev": 8.0e-8,       # FRI per LMH per mg/L per hour
    "kappa_irrev": 2.0e-9,     # FRI per mg/L per hour

    # Physical compaction
    "C_comp": 0.020,           # per decade of operating months (BWRO-LP)

    # Oxidative damage
    "k_ox_B": 1.5e-4,          # per ppm·h
    "k_ox_A": 5.0e-5,          # per ppm·h

    # CIP efficacy
    "eps_cake_0": 0.90,        # initial CIP efficacy for cake
    "eps_bio_0": 0.70,         # initial CIP efficacy for biofilm
    "eps_scale_0": 0.80,       # initial CIP efficacy for carbonate scale
    "k_eps_rev": 0.05,         # efficacy decay per CIP cycle (reversible)
    "k_eps_irrev": 0.15,       # efficacy decay per CIP cycle (irreversible)

    # FRI reversible/irreversible fractions
    "f_rev_cake": 0.85,
    "f_rev_bio": 0.70,
    "f_rev_scale_carbonate": 0.90,
    "f_rev_scale_hard": 0.50,   # barite, celestite
    "f_rev_scale_silica": 0.40,

    # Element position corrections
    "sdi_stage2_factor": 0.60,  # SDI reduction for Stage 2 element 1
    "intercept_slope": 0.15,    # f_intercept(e) = 1/(1 + 0.15*(e-1))

    # Channel blockage
    "max_theta": 0.40,         # max fractional channel blockage

    # CIP triggers
    "npf_trigger": 0.85,
    "dp_ratio_trigger": 1.15,
    "nsr_trigger": 0.90,
}

# Compaction coefficients by application
COMPACTION_COEFFICIENTS = {
    "BWRO-LP":  0.020,   # 10–20 bar
    "BWRO-MP":  0.030,   # 20–35 bar
    "HP-BWRO":  0.040,   # 35–55 bar
    "SWRO":     0.050,   # 55–80 bar
}


class AgingEngine:
    """Physics-based membrane aging engine for PACE."""

    def __init__(self):
        self.ro_engine = ROEngine()

    # ──────────────────────────────────────────────────────────────────────
    # 1. BASELINE PROFILE COMPUTATION
    # ──────────────────────────────────────────────────────────────────────

    def compute_baseline_profile(
        self,
        feed_ions: Dict[str, float],
        temp_c: float,
        ph: float,
        membrane_model: str,
        stages: int,
        vessels_per_stage: List[int],
        elements_per_vessel: int,
        target_recovery_pct: float,
        feed_flow_m3h: float
    ) -> Dict[str, Any]:
        """
        Run the clean-state baseline simulation (A₀, B₀, dh_clean) at the
        design recovery target. Extract element-wise local conditions.

        Returns dict with:
          - baseline_result: full ROEngine.simulate_system() output
          - feed_pressure_bar: converged feed pressure
          - local_conditions: dict keyed by (stage, elem) with CF, J, v, SDI_eff, f_cf
        """
        membrane = MembraneDatabase.get_ro_membrane(membrane_model)

        # Bisection solver for feed pressure (same as SystemEngine.calculate_system)
        est_osmotic = (sum(feed_ions.values()) / 1000.0) * 0.7
        low_p = max(1.0, est_osmotic - 5.0)
        high_p = max(120.0, est_osmotic + 60.0)
        target_recovery = target_recovery_pct / 100.0
        tol = 0.005

        ro_res = None
        converged_p = (low_p + high_p) / 2.0

        for _ in range(25):
            mid_p = (low_p + high_p) / 2.0
            ro_res = self.ro_engine.simulate_system(
                feed_flow_m3h=feed_flow_m3h,
                feed_pressure_bar=mid_p,
                feed_ions=feed_ions,
                temp_c=temp_c,
                membrane_model=membrane_model,
                stages=stages,
                vessels_per_stage=vessels_per_stage,
                elements_per_vessel=elements_per_vessel
            )
            rec = ro_res["summary"]["total_recovery"]
            if abs(rec - target_recovery) < tol:
                converged_p = mid_p
                break
            if rec < target_recovery:
                low_p = mid_p
            else:
                high_p = mid_p
            converged_p = mid_p

        return {
            "baseline_result": ro_res,
            "feed_pressure_bar": converged_p,
            "membrane": membrane,
        }

    def compute_local_conditions(
        self,
        baseline_result: Dict[str, Any],
        membrane: Dict[str, Any],
        feed_ions: Dict[str, float],
        feed_flow_m3h: float,
        stages: int,
        vessels_per_stage: List[int],
        elements_per_vessel: int,
        sdi_feed: float,
        model_params: Dict[str, float]
    ) -> Dict[Tuple[int, int], Dict[str, float]]:
        """
        Extract element-wise local conditions from baseline simulation:
        CF(s,e), J_local(s,e), v_local(s,e), SDI_eff(s,e), f_cf(s,e)
        """
        elements = baseline_result["elements"]
        local_conds = {}

        # Compute cumulative permeate for CF calculation
        v_ref = model_params.get("v_ref", DEFAULT_MODEL_PARAMS["v_ref"])
        intercept_slope = model_params.get("intercept_slope", DEFAULT_MODEL_PARAMS["intercept_slope"])
        sdi_s2_factor = model_params.get("sdi_stage2_factor", DEFAULT_MODEL_PARAMS["sdi_stage2_factor"])

        # Spacer geometry
        spacer_mil = membrane.get("feed_spacer_mil", 34)
        t_fs = spacer_mil * 2.54e-5  # m
        area_m2 = membrane.get("active_area_m2", 37.2)
        length_m = membrane.get("length_m", 1.016)
        w_total = area_m2 / (2.0 * length_m)
        epsilon = 0.90
        a_cross = w_total * t_fs * epsilon

        for elem_data in elements:
            s = elem_data["stage"]       # 1-indexed
            e = elem_data["position"]    # 1-indexed

            n_vessels_s = vessels_per_stage[s - 1] if s <= len(vessels_per_stage) else 1

            # Local flux (from baseline)
            j_local = elem_data["flux"]  # LMH

            # Local crossflow velocity
            avg_flow = (elem_data["feed_flow"] + elem_data["conc_flow"]) / 2.0
            avg_flow_m3s = avg_flow / 3600.0
            v_local = avg_flow_m3s / a_cross if a_cross > 0 else 0.1

            # Concentration factor — ratio of feed to remaining flow
            feed_flow_stage = elem_data["feed_flow"]  # per-vessel feed at this element
            # CF is estimated from mass balance: cumulative permeate removed
            # CF = feed_flow / conc_flow for this element position
            cf = elem_data["feed_flow"] / max(0.001, elem_data["conc_flow"])

            # Crossflow correction factor
            f_cf = math.sqrt(v_ref / max(0.01, v_local))

            # Effective SDI
            f_intercept = 1.0 / (1.0 + intercept_slope * (e - 1))
            if s == 1:
                sdi_eff = sdi_feed * math.sqrt(cf) * f_intercept
            else:
                # Stage 2+: SDI reduced by depth filtration in previous stages
                sdi_eff = sdi_feed * sdi_s2_factor * math.sqrt(cf) * f_intercept

            local_conds[(s, e)] = {
                "cf": cf,
                "j_local": j_local,
                "v_local": v_local,
                "f_cf": f_cf,
                "sdi_eff": sdi_eff,
                "f_intercept": f_intercept,
            }

        return local_conds

    # ──────────────────────────────────────────────────────────────────────
    # 2. PHREEQC SI MATRIX
    # ──────────────────────────────────────────────────────────────────────

    def compute_element_wise_si(
        self,
        feed_ions: Dict[str, float],
        local_conditions: Dict[Tuple[int, int], Dict[str, float]],
        temp_c: float,
        ph: float,
        antiscalant_dosed: bool = True
    ) -> Dict[Tuple[int, int], Dict[str, float]]:
        """
        Compute element-wise SI matrix using PHREEQC.
        For each element position, scale feed ions by CF and evaluate SI.
        Apply antiscalant ΔSI correction if dosed.
        """
        import phreeqpython
        pp = phreeqpython.PhreeqPython(database='phreeqc.dat')

        si_matrix = {}
        # Map from our ion keys to PHREEQC input format
        ion_map = {
            "Ca": "Ca", "Mg": "Mg", "Na": "Na", "K": "K",
            "Cl": "Cl", "Ba": "Ba", "Sr": "Sr", "F": "F",
        }

        for (s, e), conds in local_conditions.items():
            cf = conds["cf"]

            # pH correction: CO₂ passes through; alkalinity concentrates
            ph_local = ph + math.log10(max(1.0, cf))

            # Scale all ions by CF
            try:
                sol_input = {
                    'units': 'mg/L',
                    'temp': temp_c,
                    'pH': min(ph_local, 12.0),
                }
                for ion_key, phreeqc_key in ion_map.items():
                    conc = feed_ions.get(ion_key, 0) * cf
                    if conc > 0:
                        sol_input[phreeqc_key] = conc

                # Special format ions
                so4_conc = feed_ions.get("SO4", 0) * cf
                if so4_conc > 0:
                    sol_input["S(6)"] = f"{so4_conc} as SO4"

                hco3_conc = feed_ions.get("HCO3", 0) * cf
                if hco3_conc > 0:
                    sol_input["Alkalinity"] = f"{hco3_conc} as HCO3"

                sio2_conc = feed_ions.get("SiO2", 0) * cf
                if sio2_conc > 0:
                    sol_input["Si"] = f"{sio2_conc} as SiO2"

                sol = pp.add_solution(sol_input)

                # Get SI for each monitored mineral
                element_si = {}
                phreeqc_mineral_names = {
                    "Calcite": "Calcite",
                    "Aragonite": "Aragonite",
                    "Gypsum": "Gypsum",
                    "Anhydrite": "Anhydrite",
                    "Barite": "Barite",
                    "Celestite": "Celestite",
                    "Fluorite": "Fluorite",
                    "SiO2(a)": "SiO2(a)",
                }

                for mineral_key, phreeqc_name in phreeqc_mineral_names.items():
                    try:
                        si_val = sol.si(phreeqc_name)
                        # Apply antiscalant correction
                        if antiscalant_dosed and mineral_key in MINERAL_PARAMS:
                            si_val -= MINERAL_PARAMS[mineral_key]["delta_si_antiscalant"]
                        element_si[mineral_key] = si_val
                    except Exception:
                        element_si[mineral_key] = -999.0

                sol.forget()
                si_matrix[(s, e)] = element_si

            except Exception:
                # If PHREEQC fails for this element, use negative SI (no scaling)
                si_matrix[(s, e)] = {m: -999.0 for m in MINERAL_PARAMS.keys()}

        return si_matrix

    # ──────────────────────────────────────────────────────────────────────
    # 3. STATE VECTOR INITIALIZATION
    # ──────────────────────────────────────────────────────────────────────

    def _init_state_matrix(
        self,
        stages: int,
        elements_per_vessel: int,
        vessels_per_stage: List[int]
    ) -> Dict[Tuple[int, int], Dict[str, Any]]:
        """Initialize zero-state vector for every element position."""
        state = {}
        for s in range(1, stages + 1):
            for e in range(1, elements_per_vessel + 1):
                state[(s, e)] = {
                    "fri_cake": 0.0,
                    "fri_bio": 1e-6,   # tiny seed for logistic growth
                    "fri_nom_rev": 0.0,
                    "fri_nom_irrev": 0.0,
                    "fri_scale": {m: 0.0 for m in MINERAL_PARAMS.keys()},
                    "e_cl2": 0.0,      # cumulative chlorine exposure (ppm·h)
                    "t_total_h": 0.0,  # total operating hours
                    "t_net_h": 0.0,    # hours since last CIP
                    "n_cip": 0,        # CIP event count
                }
        return state

    # ──────────────────────────────────────────────────────────────────────
    # 4. FRI SUB-MODEL UPDATE FUNCTIONS
    # ──────────────────────────────────────────────────────────────────────

    def _update_fri_cake(
        self, state: Dict, conds: Dict, params: Dict, dt_h: float
    ) -> float:
        """
        Colloidal cake fouling (§4.1).
        dFRI_cake/dt = γ_c × SDI_eff × J_local × f_cf − k_rem × FRI_cake
        """
        gamma_c = params.get("gamma_c", DEFAULT_MODEL_PARAMS["gamma_c"])
        k_rem = params.get("k_rem", DEFAULT_MODEL_PARAMS["k_rem"])

        deposition = gamma_c * conds["sdi_eff"] * conds["j_local"] * conds["f_cf"]
        removal = k_rem * state["fri_cake"]

        # Forward Euler update (clamped to non-negative)
        new_fri = state["fri_cake"] + (deposition - removal) * dt_h
        return max(0.0, new_fri)

    def _update_fri_bio(
        self, state: Dict, conds: Dict, params: Dict,
        toc_feed: float, temp_c: float, dt_h: float
    ) -> float:
        """
        Logistic biofilm growth (§4.2).
        dFRI_bio/dt = μ_bio × FRI_bio × (1 − FRI_bio/FRI_bio,max) − k_shear × FRI_bio
        """
        mu_ref = params.get("mu_bio_ref", DEFAULT_MODEL_PARAMS["mu_bio_ref"])
        k_shear = params.get("k_shear", DEFAULT_MODEL_PARAMS["k_shear"])
        beta_bio = params.get("beta_bio", DEFAULT_MODEL_PARAMS["beta_bio"])
        k_mu_T = params.get("k_mu_T", DEFAULT_MODEL_PARAMS["k_mu_T"])
        toc_ref = params.get("TOC_ref", DEFAULT_MODEL_PARAMS["TOC_ref"])
        t_ref = params.get("T_ref", DEFAULT_MODEL_PARAMS["T_ref"])
        v_ref = params.get("v_ref", DEFAULT_MODEL_PARAMS["v_ref"])

        # Temperature and TOC dependence of growth rate
        mu_bio = mu_ref * math.sqrt(max(0.01, toc_feed) / toc_ref) * math.exp(k_mu_T * (temp_c - t_ref))

        # Crossflow-dependent shear (k_shear ∝ v²)
        v_local = conds["v_local"]
        k_shear_local = k_shear * (v_local / v_ref) ** 2 if v_ref > 0 else k_shear

        # Maximum biofilm FRI
        fri_bio_max = beta_bio * max(0.01, toc_feed)

        # Logistic growth with shear removal
        fri_bio = state["fri_bio"]
        growth = mu_bio * fri_bio * (1.0 - fri_bio / fri_bio_max) if fri_bio_max > 0 else 0.0
        removal = k_shear_local * fri_bio

        new_fri = fri_bio + (growth - removal) * dt_h
        return max(1e-6, min(new_fri, fri_bio_max))  # clamp to [seed, max]

    def _update_fri_nom(
        self, state: Dict, conds: Dict, params: Dict,
        toc_feed: float, dt_h: float
    ) -> Tuple[float, float]:
        """
        NOM adsorption (§4.3) — reversible + irreversible components.
        """
        kappa_rev = params.get("kappa_rev", DEFAULT_MODEL_PARAMS["kappa_rev"])
        kappa_irrev = params.get("kappa_irrev", DEFAULT_MODEL_PARAMS["kappa_irrev"])

        # Reversible: accumulates with inter-CIP operating time
        new_rev = state["fri_nom_rev"] + kappa_rev * toc_feed * conds["j_local"] * dt_h

        # Irreversible: accumulates with total operating time (monotonic)
        new_irrev = state["fri_nom_irrev"] + kappa_irrev * toc_feed * dt_h

        return max(0.0, new_rev), max(0.0, new_irrev)

    def _update_fri_scale(
        self, state: Dict, si_values: Dict[str, float],
        membrane: Dict, params: Dict, dt_h: float
    ) -> Dict[str, float]:
        """
        Crystal growth scaling (§5).
        FRI_scale,m += Γ_m × (Ω_m − 1)^n_m × Δt
        where Ω_m = 10^SI_m
        """
        # Compute R_m for this membrane to scale Γ_m
        A0 = membrane.get("permeability_A", 3.213)  # LMH/bar
        mu_ref = 8.9e-4  # Pa·s at 25°C
        R_m = 3.6e8 / (A0 * mu_ref)

        new_scale = {}
        for mineral, mp in MINERAL_PARAMS.items():
            si = si_values.get(mineral, -999.0)
            current = state["fri_scale"].get(mineral, 0.0)

            if si > 0:  # Only precipitate if SI > 0 (supersaturated)
                omega = 10.0 ** si
                n = mp["n"]

                # Scale Γ_m by membrane R_m ratio
                gamma_m_scaled = mp["gamma_m"] * R_M_REFERENCE / R_m

                delta_fri = gamma_m_scaled * ((omega - 1.0) ** n) * dt_h
                new_scale[mineral] = current + delta_fri
            else:
                new_scale[mineral] = current  # no growth below saturation

        return new_scale

    def _compute_compaction_factor(self, t_total_h: float, params: Dict) -> float:
        """
        Physical compaction (§6.2).
        A_comp(t) = 1 − C_comp × log₁₀(t_months + 1)
        """
        C_comp = params.get("C_comp", DEFAULT_MODEL_PARAMS["C_comp"])
        t_months = t_total_h / 720.0
        factor = 1.0 - C_comp * math.log10(t_months + 1.0)
        return max(0.5, factor)  # physical lower bound

    def _compute_oxidation_factors(self, e_cl2: float, params: Dict) -> Tuple[float, float]:
        """
        Oxidative damage (§6.1).
        A_ox = exp(−k_ox,A × E_Cl2)
        B_ox = exp(+k_ox,B × E_Cl2)
        """
        k_ox_A = params.get("k_ox_A", DEFAULT_MODEL_PARAMS["k_ox_A"])
        k_ox_B = params.get("k_ox_B", DEFAULT_MODEL_PARAMS["k_ox_B"])

        a_ox = math.exp(-k_ox_A * e_cl2)
        b_ox = math.exp(k_ox_B * e_cl2)

        return a_ox, b_ox

    # ──────────────────────────────────────────────────────────────────────
    # 5. TIME-STEP UPDATE
    # ──────────────────────────────────────────────────────────────────────

    def update_element_state(
        self,
        state_matrix: Dict[Tuple[int, int], Dict],
        local_conditions: Dict[Tuple[int, int], Dict],
        si_matrix: Dict[Tuple[int, int], Dict[str, float]],
        membrane: Dict[str, Any],
        feed_history: Dict[str, float],
        model_params: Dict[str, float],
        dt_h: float = 720.0
    ) -> Dict[Tuple[int, int], Dict]:
        """
        Advance all element states by one time step (§10.3, Steps A–D).
        dt_h: time step in hours (default 720 = 1 month)
        """
        toc_feed = feed_history.get("toc_mg_l", 2.0)
        temp_c = feed_history.get("temperature_c", 25.0)
        cl2_conc = feed_history.get("cl2_residual_mg_l", 0.0)

        for (s, e), state in state_matrix.items():
            conds = local_conditions.get((s, e))
            si_vals = si_matrix.get((s, e), {})

            if conds is None:
                continue

            # Step A: Update fouling FRI components
            state["fri_cake"] = self._update_fri_cake(state, conds, model_params, dt_h)
            state["fri_bio"] = self._update_fri_bio(state, conds, model_params, toc_feed, temp_c, dt_h)
            nom_rev, nom_irrev = self._update_fri_nom(state, conds, model_params, toc_feed, dt_h)
            state["fri_nom_rev"] = nom_rev
            state["fri_nom_irrev"] = nom_irrev

            # Step B: Update scaling FRI
            state["fri_scale"] = self._update_fri_scale(state, si_vals, membrane, model_params, dt_h)

            # Step C: Update chemical degradation
            state["e_cl2"] += cl2_conc * dt_h
            state["t_total_h"] += dt_h
            state["t_net_h"] += dt_h

        return state_matrix

    # ──────────────────────────────────────────────────────────────────────
    # 6. COMPUTE EFFECTIVE PARAMETERS
    # ──────────────────────────────────────────────────────────────────────

    def compute_effective_params(
        self,
        state_matrix: Dict[Tuple[int, int], Dict],
        membrane: Dict[str, Any],
        model_params: Dict[str, float]
    ) -> Dict[Tuple[int, int], Dict[str, float]]:
        """
        Compute A_eff, B_eff, dh_eff for every element from current state (§7, Step D).
        """
        A0 = membrane.get("permeability_A", 3.213)
        B0 = membrane.get("permeability_B", 3.72e-8)
        spacer_mil = membrane.get("feed_spacer_mil", 34)
        t_fs = spacer_mil * 2.54e-5  # spacer thickness in meters
        dh_clean = 2.0 * t_fs

        max_theta = model_params.get("max_theta", DEFAULT_MODEL_PARAMS["max_theta"])
        r_sp_cake = model_params.get("r_sp_cake", DEFAULT_MODEL_PARAMS["r_sp_cake"])

        mu_ref = 8.9e-4
        R_m = 3.6e8 / (A0 * mu_ref)

        eff_params = {}

        for (s, e), state in state_matrix.items():
            # Total FRI
            fri_scale_total = sum(state["fri_scale"].values())
            fri_total = (state["fri_cake"] + state["fri_bio"] +
                         state["fri_nom_rev"] + state["fri_nom_irrev"] +
                         fri_scale_total)

            # Compaction and oxidation factors
            comp_factor = self._compute_compaction_factor(state["t_total_h"], model_params)
            a_ox, b_ox = self._compute_oxidation_factors(state["e_cl2"], model_params)

            # Effective A (§7.2)
            a_eff = A0 * comp_factor * a_ox / (1.0 + fri_total)

            # Effective B (§7.3)
            b_eff = B0 * b_ox

            # Effective dh (§3.4)
            # δ_foul = (FRI_cake + FRI_bio) × R_m / r_sp_cake
            delta_foul = (state["fri_cake"] + state["fri_bio"]) * R_m / r_sp_cake
            theta = 2.0 * delta_foul / t_fs if t_fs > 0 else 0.0
            theta = min(theta, max_theta)
            dh_eff = dh_clean * (1.0 - theta)

            eff_params[(s, e)] = {
                "A_eff": a_eff,
                "B_eff": b_eff,
                "dh_eff": dh_eff,
                "fri_total": fri_total,
                "fri_cake": state["fri_cake"],
                "fri_bio": state["fri_bio"],
                "fri_nom_rev": state["fri_nom_rev"],
                "fri_nom_irrev": state["fri_nom_irrev"],
                "fri_scale_total": fri_scale_total,
                "fri_scale_detail": dict(state["fri_scale"]),
                "comp_factor": comp_factor,
                "a_ox_factor": a_ox,
                "b_ox_factor": b_ox,
                "theta": theta,
            }

        return eff_params

    # ──────────────────────────────────────────────────────────────────────
    # 7. CIP APPLICATION
    # ──────────────────────────────────────────────────────────────────────

    def apply_cip(
        self,
        state_matrix: Dict[Tuple[int, int], Dict],
        model_params: Dict[str, float]
    ) -> Dict[Tuple[int, int], Dict]:
        """
        Apply CIP state update (§9.3) with per-component efficacy and decay.
        """
        eps_cake_0 = model_params.get("eps_cake_0", DEFAULT_MODEL_PARAMS["eps_cake_0"])
        eps_bio_0 = model_params.get("eps_bio_0", DEFAULT_MODEL_PARAMS["eps_bio_0"])
        eps_scale_0 = model_params.get("eps_scale_0", DEFAULT_MODEL_PARAMS["eps_scale_0"])
        k_eps_rev = model_params.get("k_eps_rev", DEFAULT_MODEL_PARAMS["k_eps_rev"])
        k_eps_irrev = model_params.get("k_eps_irrev", DEFAULT_MODEL_PARAMS["k_eps_irrev"])

        for (s, e), state in state_matrix.items():
            n_cip = state["n_cip"]

            # Efficacy decays with number of CIP cycles (§9.2)
            eps_cake = eps_cake_0 * math.exp(-k_eps_rev * n_cip)
            eps_bio = eps_bio_0 * math.exp(-k_eps_rev * n_cip)

            # Post-CIP state update (§9.3)
            state["fri_cake"] *= (1.0 - eps_cake)
            state["fri_bio"] *= (1.0 - eps_bio)
            state["fri_nom_rev"] = 0.0  # fully removable by high-pH CIP

            # Scale: per-mineral CIP efficacy
            for mineral, mp in MINERAL_PARAMS.items():
                if mineral in state["fri_scale"]:
                    # Hard scales (barite, celestite, silica) have lower removal
                    if mineral in ("Barite", "Celestite"):
                        eps_scale_m = 0.50 * math.exp(-k_eps_irrev * n_cip)
                    elif mineral == "SiO2(a)":
                        eps_scale_m = 0.40 * math.exp(-k_eps_irrev * n_cip)
                    else:
                        eps_scale_m = eps_scale_0 * math.exp(-k_eps_rev * n_cip)
                    state["fri_scale"][mineral] *= (1.0 - eps_scale_m)

            # Reset inter-CIP timer, increment CIP count
            state["t_net_h"] = 0.0
            state["n_cip"] += 1

        return state_matrix

    # ──────────────────────────────────────────────────────────────────────
    # 8. SIMULATE AGED SYSTEM (re-run solver with aged parameters)
    # ──────────────────────────────────────────────────────────────────────

    def simulate_aged_system(
        self,
        feed_ions: Dict[str, float],
        temp_c: float,
        membrane_model: str,
        stages: int,
        vessels_per_stage: List[int],
        elements_per_vessel: int,
        target_recovery_pct: float,
        feed_flow_m3h: float,
        eff_params: Dict[Tuple[int, int], Dict[str, float]],
        simulation_mode: str = "constant_recovery",
        design_pressure: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Re-run the PACE element-wise simulation with aged A_eff, B_eff, dh_eff.

        For constant_recovery mode: bisect for the feed pressure that achieves
        the target recovery with the degraded membrane parameters.
        """
        membrane = MembraneDatabase.get_ro_membrane(membrane_model)

        # Build aged parameter matrix for the engine
        aged_params = {}
        for (s, e), ep in eff_params.items():
            aged_params[(s, e)] = {
                "A": ep["A_eff"],
                "B": ep["B_eff"],
                "dh": ep["dh_eff"],
            }

        est_osmotic = (sum(feed_ions.values()) / 1000.0) * 0.7
        target_recovery = target_recovery_pct / 100.0

        if simulation_mode == "constant_recovery":
            # Bisection for feed pressure
            low_p = max(1.0, est_osmotic - 5.0)
            high_p = max(120.0, est_osmotic + 80.0)
            tol = 0.005

            ro_res = None
            converged_p = (low_p + high_p) / 2.0

            for _ in range(30):
                mid_p = (low_p + high_p) / 2.0
                ro_res = self.ro_engine.simulate_system(
                    feed_flow_m3h=feed_flow_m3h,
                    feed_pressure_bar=mid_p,
                    feed_ions=feed_ions,
                    temp_c=temp_c,
                    membrane_model=membrane_model,
                    stages=stages,
                    vessels_per_stage=vessels_per_stage,
                    elements_per_vessel=elements_per_vessel,
                    aged_params=aged_params
                )
                rec = ro_res["summary"]["total_recovery"]
                if abs(rec - target_recovery) < tol:
                    converged_p = mid_p
                    break
                if rec < target_recovery:
                    low_p = mid_p
                else:
                    high_p = mid_p
                converged_p = mid_p

            ro_res["feed_pressure_bar"] = converged_p
            return ro_res

        else:
            # constant_pressure mode — just run at design pressure
            p_run = design_pressure if design_pressure is not None else (est_osmotic + 5.0)
            ro_res = self.ro_engine.simulate_system(
                feed_flow_m3h=feed_flow_m3h,
                feed_pressure_bar=p_run,
                feed_ions=feed_ions,
                temp_c=temp_c,
                membrane_model=membrane_model,
                stages=stages,
                vessels_per_stage=vessels_per_stage,
                elements_per_vessel=elements_per_vessel,
                aged_params=aged_params
            )
            return ro_res

    # ──────────────────────────────────────────────────────────────────────
    # 9. MAIN AGING SIMULATION LOOP
    # ──────────────────────────────────────────────────────────────────────

    def run_aging_simulation(
        self,
        feed_ions: Dict[str, float],
        temp_c: float,
        ph: float,
        membrane_model: str,
        stages: int,
        vessels_per_stage: List[int],
        elements_per_vessel: int,
        target_recovery_pct: float,
        feed_flow_m3h: float,
        aging_config: Dict[str, Any],
        feed_history: Dict[str, float],
        model_params: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Full time-stepping aging simulation (§10).

        Returns:
          aging_profile: list of monthly snapshots
          cip_events: list of months where CIP occurred
          end_of_life_month: month when NPF < 0.70 permanently
          dominant_mechanism: FRI component with highest value at EOL
          element_autopsy: final-state FRI values by position
        """
        if model_params is None:
            model_params = dict(DEFAULT_MODEL_PARAMS)
        else:
            # Merge with defaults
            merged = dict(DEFAULT_MODEL_PARAMS)
            merged.update(model_params)
            model_params = merged

        design_life_months = aging_config.get("design_life_months", 60)
        time_step_months = aging_config.get("time_step_months", 1)
        dt_h = time_step_months * 720.0  # hours per step
        simulation_mode = aging_config.get("simulation_mode", "constant_recovery")
        cip_trigger = aging_config.get("cip_trigger", "scheduled")
        cip_interval_days = aging_config.get("cip_interval_days", 90)
        cip_interval_h = cip_interval_days * 24.0
        antiscalant_dosed = aging_config.get("antiscalant_dosed", True)

        sdi_feed = feed_history.get("sdi15", 3.0)

        membrane = MembraneDatabase.get_ro_membrane(membrane_model)

        # ── Step 1: Baseline simulation (t = 0) ──
        baseline = self.compute_baseline_profile(
            feed_ions, temp_c, ph, membrane_model,
            stages, vessels_per_stage, elements_per_vessel,
            target_recovery_pct, feed_flow_m3h
        )

        baseline_result = baseline["baseline_result"]
        baseline_pressure = baseline["feed_pressure_bar"]

        # Extract baseline performance metrics
        baseline_perm_flow = baseline_result["summary"]["perm_flow"]
        baseline_perm_tds = baseline_result["summary"]["perm_tds"]
        baseline_dp = sum(
            el["dp"] for el in baseline_result["elements"]
        )

        # ── Step 2: Compute local conditions ──
        local_conditions = self.compute_local_conditions(
            baseline_result, membrane, feed_ions, feed_flow_m3h,
            stages, vessels_per_stage, elements_per_vessel,
            sdi_feed, model_params
        )

        # ── Step 3: Compute SI matrix (once for constant-recovery) ──
        si_matrix = self.compute_element_wise_si(
            feed_ions, local_conditions, temp_c, ph, antiscalant_dosed
        )

        # ── Step 4: Initialize state matrix ──
        state_matrix = self._init_state_matrix(stages, elements_per_vessel, vessels_per_stage)

        # ── Step 5: Time-stepping loop ──
        aging_profile = []
        cip_events = []
        end_of_life_month = None
        eol_by_pressure = False
        n_steps = design_life_months // time_step_months

        # Record month 0
        aging_profile.append({
            "month": 0,
            "p_feed_bar": round(baseline_pressure, 2),
            "npf": 1.0,
            "nsr": 1.0,
            "delta_p_ratio": 1.0,
            "flux_lmh": round(baseline_result["summary"]["avg_flux_lmh"], 1),
            "recovery_pct": round(baseline_result["summary"]["total_recovery"] * 100, 2),
            "cip_event": False,
            "fri_matrix": {},
            "a_eff_matrix": {},
        })

        for step in range(1, n_steps + 1):
            month = step * time_step_months

            # Step A–C: Update element states
            state_matrix = self.update_element_state(
                state_matrix, local_conditions, si_matrix,
                membrane, feed_history, model_params, dt_h
            )

            # Step F: Check CIP trigger
            cip_this_step = False

            if cip_trigger == "scheduled":
                # Check if cumulative inter-CIP time exceeds interval
                # Use element (1,1) as representative
                sample_state = state_matrix.get((1, 1), {})
                if sample_state.get("t_net_h", 0) >= cip_interval_h:
                    cip_this_step = True

            # Step D: Compute effective parameters
            eff_params = self.compute_effective_params(state_matrix, membrane, model_params)

            # Step E: Re-run simulation with aged parameters
            try:
                aged_result = self.simulate_aged_system(
                    feed_ions, temp_c, membrane_model,
                    stages, vessels_per_stage, elements_per_vessel,
                    target_recovery_pct, feed_flow_m3h,
                    eff_params, simulation_mode,
                    design_pressure=baseline_pressure
                )
            except Exception:
                # If simulation fails, use last known values
                aged_result = baseline_result

            # Compute performance metrics
            aged_perm_flow = aged_result["summary"]["perm_flow"]
            npf = aged_perm_flow / baseline_perm_flow if baseline_perm_flow > 0 else 1.0

            aged_perm_tds = aged_result["summary"]["perm_tds"]
            nsr = 1.0
            if baseline_perm_tds > 0 and baseline_result["summary"]["feed_tds"] > 0:
                baseline_rej = 1.0 - baseline_perm_tds / baseline_result["summary"]["feed_tds"]
                aged_rej = 1.0 - aged_perm_tds / aged_result["summary"]["feed_tds"]
                nsr = aged_rej / baseline_rej if baseline_rej > 0 else 1.0

            aged_dp = sum(el["dp"] for el in aged_result["elements"])
            dp_ratio = aged_dp / baseline_dp if baseline_dp > 0 else 1.0

            # Performance-triggered CIP check
            if cip_trigger == "performance":
                npf_trig = model_params.get("npf_trigger", DEFAULT_MODEL_PARAMS["npf_trigger"])
                dp_trig = model_params.get("dp_ratio_trigger", DEFAULT_MODEL_PARAMS["dp_ratio_trigger"])
                if npf < npf_trig or dp_ratio > dp_trig:
                    cip_this_step = True

            # Apply CIP if triggered
            if cip_this_step:
                state_matrix = self.apply_cip(state_matrix, model_params)
                cip_events.append(month)

                # Recompute after CIP
                eff_params = self.compute_effective_params(state_matrix, membrane, model_params)
                try:
                    aged_result = self.simulate_aged_system(
                        feed_ions, temp_c, membrane_model,
                        stages, vessels_per_stage, elements_per_vessel,
                        target_recovery_pct, feed_flow_m3h,
                        eff_params, simulation_mode,
                        design_pressure=baseline_pressure
                    )
                    aged_perm_flow = aged_result["summary"]["perm_flow"]
                    npf = aged_perm_flow / baseline_perm_flow if baseline_perm_flow > 0 else 1.0
                except Exception:
                    pass

            # Build FRI and A_eff matrices for output
            fri_out = {}
            a_eff_out = {}
            for (s, e), ep in eff_params.items():
                key = f"s{s}_e{e}"
                fri_out[key] = round(ep["fri_total"], 4)
                a_eff_out[key] = round(ep["A_eff"], 4)

            aged_pressure = aged_result.get("feed_pressure_bar",
                                            aged_result["summary"].get("feed_pressure_bar", baseline_pressure))

            # Record monthly snapshot
            aging_profile.append({
                "month": month,
                "p_feed_bar": round(aged_pressure, 2),
                "npf": round(npf, 4),
                "nsr": round(nsr, 4),
                "delta_p_ratio": round(dp_ratio, 2),
                "flux_lmh": round(aged_result["summary"]["avg_flux_lmh"], 1),
                "recovery_pct": round(aged_result["summary"]["total_recovery"] * 100, 2),
                "cip_event": cip_this_step,
                "fri_matrix": fri_out,
                "a_eff_matrix": a_eff_out,
            })

            # End-of-life check
            max_p_limit = membrane.get("max_pressure_bar", 41.0)
            if (npf < 0.70 or aged_pressure > max_p_limit) and end_of_life_month is None:
                end_of_life_month = month
                if aged_pressure > max_p_limit:
                    eol_by_pressure = True
                break

        # ── Final analysis ──
        # Determine dominant mechanism from final state
        final_eff = self.compute_effective_params(state_matrix, membrane, model_params)
        total_cake = sum(ep["fri_cake"] for ep in final_eff.values())
        total_bio = sum(ep["fri_bio"] for ep in final_eff.values())
        total_nom = sum(ep["fri_nom_rev"] + ep["fri_nom_irrev"] for ep in final_eff.values())
        total_scale = sum(ep["fri_scale_total"] for ep in final_eff.values())
        total_irrev = sum((1.0 / max(ep["comp_factor"], 0.01) - 1.0) + (1.0 / max(ep["a_ox_factor"], 0.01) - 1.0) for ep in final_eff.values())

        mechanism_totals = {
            "cake_fouling": total_cake,
            "biofouling": total_bio,
            "NOM_adsorption": total_nom,
            "scaling": total_scale,
            "cake": total_cake,
            "bio": total_bio,
            "nom": total_nom,
            "scale": total_scale,
            "irreversible": total_irrev,
        }
        if eol_by_pressure:
            dominant_mechanism = "Feed Pressure Exceedance"
        else:
            dominant_mechanism = max(
                ["cake_fouling", "biofouling", "NOM_adsorption", "scaling", "irreversible"],
                key=lambda k: mechanism_totals[k]
            )

        # Element autopsy — final FRI values by position
        A0 = membrane.get("permeability_A", 3.213)
        if A0 <= 0:
            A0 = 3.213
        element_autopsy = {}
        for (s, e), ep in final_eff.items():
            key = f"s{s}_e{e}"
            element_autopsy[key] = {
                "fri_cake": round(ep["fri_cake"], 4),
                "fri_bio": round(ep["fri_bio"], 4),
                "fri_nom": round(ep["fri_nom_rev"] + ep["fri_nom_irrev"], 4),
                "fri_scale": round(ep["fri_scale_total"], 4),
                "fri_total": round(ep["fri_total"], 4),
                "a_eff": round(ep["A_eff"] / A0, 4),
                "comp_factor": round(ep["comp_factor"], 4),
            }

        return {
            "aging_profile": aging_profile,
            "cip_events": cip_events,
            "end_of_life_month": end_of_life_month,
            "dominant_mechanism": dominant_mechanism,
            "mechanism_totals": {k: round(v, 4) for k, v in mechanism_totals.items()},
            "element_autopsy": element_autopsy,
            "baseline_pressure_bar": round(baseline_pressure, 2),
            "baseline_npf": 1.0,
        }
