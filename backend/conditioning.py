"""
PACE Feed Water Conditioning / pH Adjustment Module
====================================================
Estimates chemical dosing requirements (NaOH, H2SO4, HCl) to adjust pH, 
including carbon dioxide (CO2) degassing simulation.
"""
import math

def compute_chemical_dose(ions, target_ph, chemical):
    """
    Roughly estimates the dosing requirement (in mg/L active chemical) 
    to shift the pH of a water profile.
    NaOH is used for elevation, while H2SO4 or HCl are used for depression.
    """
    current_ph = ions.get("pH", 7.0)
    if target_ph is None or abs(current_ph - target_ph) < 0.1:
        return 0.0
    delta_ph = target_ph - current_ph
    if chemical == "NaOH" and delta_ph > 0:
        return delta_ph * 2.5
    elif chemical in ["H2SO4", "HCl"] and delta_ph < 0:
        return abs(delta_ph) * 2.5
    return 0.0

def apply_conditioning(p1_permeate_ions, cond_cfg):
    """
    Applies conditioning parameters to a water profile.
    Simulates CO2 degassing (wiping dissolved CO2) and adjusts ion 
    concentrations based on the calculated chemical dosage requirements.
    """
    ions = p1_permeate_ions.copy()
    enabled = cond_cfg.get("enabled", False) if isinstance(cond_cfg, dict) else (getattr(cond_cfg, "enabled", False))
    
    if not enabled:
        return ions, 0.0, ions.get("pH", 7.0)
        
    target_ph = cond_cfg.get("target_ph") if isinstance(cond_cfg, dict) else getattr(cond_cfg, "target_ph", None)
    chemical = cond_cfg.get("chemical") if isinstance(cond_cfg, dict) else getattr(cond_cfg, "chemical", None)
    co2_degassing = cond_cfg.get("co2_degassing", False) if isinstance(cond_cfg, dict) else getattr(cond_cfg, "co2_degassing", False)
    
    if co2_degassing:
        # CO2 degassing removes dissolved CO2 gas
        ions["CO2"] = 0.0
        
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
