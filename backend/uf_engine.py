"""
UF System Calculation Engine
Handles UF sizing, TMP, backwash, CEB, and CIP calculations.
"""

import math
from typing import Dict, Any
from membrane_database import MembraneDatabase

class UFEngine:
    def __init__(self):
        pass
        
    def _viscosity_correction(self, temp_c: float) -> float:
        """
        Calculates dynamic viscosity correction factor relative to 20°C.
        Uses the empirical Arrhenius equation of state to determine viscosity 
        changes as a function of temperature (K).
        """
        # Dynamic viscosity of water (Pa.s)
        mu_T = 1.0e-3 * math.exp(1808.0 / (temp_c + 273.15) - 6.354)
        mu_20 = 1.0e-3 * math.exp(1808.0 / (20.0 + 273.15) - 6.354)
        return mu_T / mu_20

    def simulate_uf(self, 
                    gross_feed_flow_m3h: float, 
                    temp_c: float,
                    module_name: str,
                    feed_turbidity: float = 20.0,
                    feed_tss: float = 30.0,
                    feed_tds: float = 4000.0,
                    feed_ph: float = 7.3) -> Dict[str, Any]:
        """
        Simulates Ultrafiltration (UF) system behavior.
        Estimates required modules, actual operating flux, backwash and forward-flush water losses,
        net product flow, system recovery, clean/fouled Trans-Membrane Pressure (TMP) 
        across varying operating temperatures, and generates safety limit warnings.
        """
        module = MembraneDatabase.get_uf_module(module_name)
        
        # 1. Number of Modules
        area = module["membrane_area_m2"]
        design_flux = module["design_flux_lmh"]
        
        # Intake is fixed, so use gross flow directly to calculate modules
        exact_modules = (gross_feed_flow_m3h * 1000.0) / (design_flux * area)
        n_modules = math.ceil(exact_modules)
        
        # Recalculate actual filtration flux based on gross flow
        actual_flux = (gross_feed_flow_m3h * 1000.0) / (n_modules * area)
        
        # 2. Operating Cycles
        t_filt_min = 90.0
        t_bw_min = module["backwash_duration_s"] / 60.0
        bw_flux = module["backwash_flux_lmh"]
        
        # Backwash volume per module per cycle
        v_bw_module = (bw_flux * area * (module["backwash_duration_s"] / 3600.0)) / 1000.0 # m3
        v_bw_total = v_bw_module * n_modules
        
        # Refine gross flow and recovery based on backwash consumption
        cycles_per_hour = 60.0 / (t_filt_min + t_bw_min)
        bw_loss_m3h = v_bw_total * cycles_per_hour
        
        # Add forward flush loss (assume 1 min per cycle)
        ff_flow_module = module["min_forward_flush_m3h"] * 1.5 # 50% safety
        ff_loss_m3h = (ff_flow_module * n_modules * (1.0/60.0)) * cycles_per_hour
        
        total_loss_m3h = bw_loss_m3h + ff_loss_m3h
        
        net_flow_m3h = gross_feed_flow_m3h - total_loss_m3h
        
        system_recovery = (net_flow_m3h / gross_feed_flow_m3h) * 100.0
        
        # 3. TMP Calculations
        visc_ratio = self._viscosity_correction(temp_c)
        Lp_T = module["permeability_Lp20"] / visc_ratio
        
        clean_tmp = actual_flux / Lp_T
        fouled_tmp = clean_tmp * 2.0 # Approximation for fouled state
        
        # Min/Max temperature TMPs (assuming 10C min, 35C max)
        visc_min = self._viscosity_correction(10.0)
        clean_tmp_tmin = actual_flux / (module["permeability_Lp20"] / visc_min)
        fouled_tmp_tmin = clean_tmp_tmin * 2.0
        
        visc_max = self._viscosity_correction(35.0)
        clean_tmp_tmax = actual_flux / (module["permeability_Lp20"] / visc_max)
        
        # 4. Warnings Generation
        warnings = []
        
        def add_warning(name, unit, limit, est):
            warnings.append({
                "type": name,
                "unit": unit,
                "limit": round(limit, 2),
                "estimate": round(est, 2),
                "status": "FAIL" if est > limit else "PASS"
            })
            
        add_warning("Filtration Flux > Max", "LMH", module["max_filtration_flux_lmh"], actual_flux)
        add_warning("Forward Flush Flow < Min", "m3/h/mod", module["min_forward_flush_m3h"], ff_flow_module)
        add_warning("Clean Membrane TMP @ TMin > Max", "bar", module["clean_tmp_max_bar"], clean_tmp_tmin)
        add_warning("Clean Membrane TMP @ TDesign > Max", "bar", module["clean_tmp_max_bar"], clean_tmp)
        add_warning("Clean Membrane TMP @ TMax > Max", "bar", module["clean_tmp_max_bar"], clean_tmp_tmax)
        add_warning("Fouled Membrane TMP @ TMin > Max", "bar", module["fouled_tmp_max_bar"], fouled_tmp_tmin)
        add_warning("Fouled Membrane TMP @ TDesign > Max", "bar", module["fouled_tmp_max_bar"], fouled_tmp)
        
        return {
            "overview": {
                "module_type": module_name,
                "online_units": 1,
                "total_modules": n_modules,
                "gross_feed_m3h": round(gross_feed_flow_m3h, 1),
                "net_product_m3h": round(net_flow_m3h, 1),
                "recovery_pct": round(system_recovery, 2),
                "tmp_design_bar": round(clean_tmp, 2),
                "tmp_tmin_bar": round(clean_tmp_tmin, 2)
            },
            "operating_conditions": {
                "filtration_duration_min": t_filt_min,
                "filtration_flux_lmh": round(actual_flux, 1),
                "backwash_duration_min": round(t_bw_min, 1),
                "backwash_flux_lmh": bw_flux,
                "acid_ceb_interval_h": 168,
                "alkali_ceb_interval_h": 168,
                "cip_interval_d": 90
            },
            "water_quality": {
                "temperature_c": temp_c,
                "feed_turbidity_ntu": feed_turbidity,
                "prod_turbidity_ntu": 0.1,
                "feed_tss_mgl": feed_tss,
                "prod_tss_mgl": 0.0,
                "feed_tds_mgl": feed_tds,
                "prod_tds_mgl": feed_tds, # UF doesn't remove TDS
                "ph": feed_ph
            },
            "warnings": warnings
        }
