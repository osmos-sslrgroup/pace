"""
PACE Feed Water Conditioning / pH Adjustment Module
====================================================
Estimates chemical dosing requirements (NaOH, H2SO4, HCl) to adjust pH, 
including carbon dioxide (CO2) degassing simulation.
"""
import math

def compute_chemical_dose(ions, target_ph, chemical):
    """
    Estimates the chemical dosing requirement (in mg/L active chemical)
    using alkalinity buffer equilibrium (Henderson-Hasselbalch / carbonate system).
    NaOH is used for pH elevation; H2SO4 or HCl are used for pH depression.
    """
    current_ph = ions.get("pH", ions.get("ph", 7.0))
    if target_ph is None or abs(current_ph - target_ph) < 0.05:
        return 0.0
    
    delta_ph = target_ph - current_ph
    hco3_mg = ions.get("HCO3", ions.get("bicarbonate", 0.0))
    alk_meq = hco3_mg / 61.0168  # Bicarbonate alkalinity in meq/L

    if chemical in ["H2SO4", "HCl"] and delta_ph < 0:
        # Stoichiometric acid neutralization of bicarbonate (pK1 ≈ 6.35)
        # Fraction of carbonate system as H2CO3:
        alpha_target = 1.0 / (1.0 + math.pow(10.0, target_ph - 6.35))
        alpha_current = 1.0 / (1.0 + math.pow(10.0, current_ph - 6.35))
        d_meq = max(0.0, (alpha_target - alpha_current) * alk_meq) + 0.05 * abs(delta_ph)
        if chemical == "H2SO4":
            return round(d_meq * 49.04, 2)  # MW 98.08 / 2 equivalents
        elif chemical == "HCl":
            return round(d_meq * 36.46, 2)  # MW 36.46 / 1 equivalent
    elif chemical == "NaOH" and delta_ph > 0:
        # Caustic dosing: neutralizes dissolved CO2 and shifts bicarbonate equilibrium
        co2_mg = ions.get("CO2", 0.0)
        co2_meq = co2_mg / 44.01
        d_meq = co2_meq * max(0.0, 1.0 - math.pow(10.0, 6.35 - target_ph)) + 0.08 * delta_ph
        return round(max(0.0, d_meq * 40.00), 2)  # MW 40.00 / 1 equivalent
    return 0.0

def apply_conditioning(p1_permeate_ions, cond_cfg, degasser_cfg=None):
    """
    Applies conditioning parameters to a water profile.
    Simulates partial or full CO2 degasification and adjusts ion
    concentrations based on calculated chemical dosage requirements.
    """
    ions = p1_permeate_ions.copy()
    enabled = cond_cfg.get("enabled", False) if isinstance(cond_cfg, dict) else getattr(cond_cfg, "enabled", False)
    degas_enabled = (degasser_cfg.get("enabled", False) if isinstance(degasser_cfg, dict) else getattr(degasser_cfg, "enabled", False)) if degasser_cfg else False
    
    # Degasser model: partial stripping with efficiency and residual limit
    co2_degassing = cond_cfg.get("co2_degassing", False) if isinstance(cond_cfg, dict) else getattr(cond_cfg, "co2_degassing", False)
    if co2_degassing or degas_enabled:
        eff = 0.95
        residual_limit = 3.0
        if isinstance(degasser_cfg, dict):
            eff = degasser_cfg.get("efficiency", 0.95)
            residual_limit = degasser_cfg.get("residual_co2_mg_l", 3.0)
        cur_co2 = ions.get("CO2", 0.0)
        if cur_co2 > residual_limit:
            ions["CO2"] = max(residual_limit, cur_co2 * (1.0 - eff))
        elif co2_degassing and not degasser_cfg:
            ions["CO2"] = 0.0
            
    if not enabled and not degas_enabled:
        return ions, 0.0, ions.get("pH", 7.0)
        
    target_ph = cond_cfg.get("target_ph") if isinstance(cond_cfg, dict) else getattr(cond_cfg, "target_ph", None)
    chemical = cond_cfg.get("chemical") if isinstance(cond_cfg, dict) else getattr(cond_cfg, "chemical", None)
        
    dose = 0.0
    if target_ph is not None and chemical:
        dose = compute_chemical_dose(ions, target_ph, chemical)
        ions["pH"] = target_ph
        # Adjust sodium, sulfate, or chloride concentrations based on dosage stoichiometry
        if chemical == "NaOH":
            ions["Na"] = ions.get("Na", 0.0) + dose * (22.99 / 40.00)
        elif chemical == "H2SO4":
            ions["SO4"] = ions.get("SO4", 0.0) + dose * (96.06 / 98.08)
        elif chemical == "HCl":
            ions["Cl"] = ions.get("Cl", 0.0) + dose * (35.45 / 36.46)
            
    return ions, dose, target_ph or ions.get("pH", 7.0)
