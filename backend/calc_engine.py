"""
RO/NF Element-wise Calculation Engine
Implements Solution-Diffusion and Spiegler-Kedem mass transport models.
"""

import math
from typing import Dict, List, Any, Optional
from membrane_database import MembraneDatabase

# (molar mass, |charge|) used for permeate/reject charge balance — shared by RO and NF
CATIONS_MW_Z = {"Ca": (40.078, 2), "Mg": (24.305, 2), "Na": (22.990, 1),
                "K": (39.098, 1), "Ba": (137.327, 2), "Sr": (87.62, 2),
                "NH4": (18.04, 1), "Fe": (55.845, 2), "Mn": (54.938, 2),
                "Al": (26.982, 3)}
ANIONS_MW_Z = {"Cl": (35.45, 1), "SO4": (96.06, 2), "HCO3": (61.017, 1),
               "CO3": (60.009, 2), "NO3": (62.00, 1), "F": (18.998, 1),
               "PO4": (94.97, 3), "Br": (79.904, 1)}
CARBONATE = ("HCO3", "CO3", "CO2")

# Species excluded from TDS (Toray DS2 basis: TDS = all ions + SiO2 + B + CO3; CO2 excluded)
TDS_EXCLUDE = ("CO2",)


# ---------------------------------------------------------------------------
# Carbonate chemistry (activity-corrected, matches Toray DS2 to ~2-5 %)
# ---------------------------------------------------------------------------
def carbonic_pk1(temp_c: float) -> float:
    """pK1 of carbonic acid (Harned & Davis 1943). 6.35 at 25 C."""
    t = temp_c + 273.15
    return 3404.71 / t + 0.032786 * t - 14.8435


def carbonic_pk2(temp_c: float) -> float:
    """pK2 of carbonic acid (Harned & Scholes 1941). 10.33 at 25 C."""
    t = temp_c + 273.15
    return 2902.39 / t + 0.02379 * t - 6.498


def water_pkw(temp_c: float) -> float:
    """pKw of water. 14.00 at 25 C."""
    t = temp_c + 273.15
    return 4470.99 / t - 6.0875 + 0.01706 * t


def ionic_strength(ions: Dict[str, float]) -> float:
    """Ionic strength (mol/L) from an ion dict in mg/L."""
    i = 0.0
    for tbl in (CATIONS_MW_Z, ANIONS_MW_Z):
        for ion, (mw, z) in tbl.items():
            c = ions.get(ion, 0.0)
            if c > 0:
                i += (c / 1000.0 / mw) * z * z
    return 0.5 * i


def log_gamma(z: int, I: float, temp_c: float, a_ang: float = 4.5) -> float:
    """Extended Debye-Hueckel (ion size 4.5 A for HCO3/CO3); valid to seawater I~0.7."""
    A = 0.4883 + 8.074e-4 * temp_c
    Bd = 0.3241 + 1.600e-4 * temp_c
    sI = math.sqrt(max(I, 0.0))
    return -A * z * z * sI / (1.0 + Bd * a_ang * sI)


def split_carbonate(ions: Dict[str, float], ph: float, temp_c: float) -> Dict[str, float]:
    """
    Add free CO2 and CO3 (mg/L) to a feed ion dict from HCO3 and the measured pH
    (pH = -log aH, activity-corrected).  HCO3 is kept as the HCO3 ion.
        [CO2] = aH * g1 * [HCO3] / K1
        [CO3] = K2 * g1 * [HCO3] / (aH * g2)
    Call this on the RO feed BEFORE simulate_system.
    """
    out = dict(ions)
    hco3 = out.get("HCO3", 0.0)
    if hco3 <= 0:
        out.setdefault("CO2", 0.0)
        out.setdefault("CO3", 0.0)
        return out
    I = ionic_strength(out)
    g1 = 10 ** log_gamma(1, I, temp_c)
    g2 = 10 ** log_gamma(2, I, temp_c)
    aH = 10 ** (-ph)
    K1 = 10 ** (-carbonic_pk1(temp_c))
    K2 = 10 ** (-carbonic_pk2(temp_c))
    m_hco3 = hco3 / 61.017
    out["CO2"] = aH * g1 * m_hco3 / K1 * 44.01
    out["CO3"] = K2 * g1 * m_hco3 / (aH * g2) * 60.009
    return out


def carbonate_ph(hco3_mg_l: float, co2_mg_l: float, temp_c: float, I: float = 0.0) -> Optional[float]:
    """pH (activity scale) from HCO3 and CO2: pH = pK1 + log10(g1*[HCO3]/[CO2])."""
    if hco3_mg_l <= 0 or co2_mg_l <= 0:
        return None
    g1 = 10 ** log_gamma(1, I, temp_c)
    return carbonic_pk1(temp_c) + math.log10(g1 * (hco3_mg_l / 61.017) / (co2_mg_l / 44.01))


def respeciate_carbonate(ions: Dict[str, float], ct_mmol: float, alk_meq: float,
                         temp_c: float) -> Dict[str, float]:
    """
    Re-split total carbonate (CT, mmol/L) into CO2 / HCO3 / CO3 for a given
    carbonate alkalinity (HCO3 + 2 CO3, meq/L) by solving for pH.
    Used on the reject of every element (CO2 builds up, pH rises, as in DS2).
    """
    out = dict(ions)
    if ct_mmol <= 0:
        return out
    I = ionic_strength(out)
    g1 = 10 ** log_gamma(1, I, temp_c)
    g2 = 10 ** log_gamma(2, I, temp_c)
    K1 = 10 ** (-carbonic_pk1(temp_c))
    K2 = 10 ** (-carbonic_pk2(temp_c))

    def species(ph):
        aH = 10 ** (-ph)
        r_co2 = aH * g1 / K1           # CO2 / HCO3 (molar)
        r_co3 = K2 * g1 / (aH * g2)    # CO3 / HCO3
        hco3 = ct_mmol / (1.0 + r_co2 + r_co3)
        return hco3 * r_co2, hco3, hco3 * r_co3

    lo, hi = 2.0, 12.5
    for _ in range(80):                # alkalinity rises monotonically with pH
        mid = 0.5 * (lo + hi)
        co2, hco3, co3 = species(mid)
        if hco3 + 2 * co3 < alk_meq:
            lo = mid
        else:
            hi = mid
    co2, hco3, co3 = species(0.5 * (lo + hi))
    out["CO2"], out["HCO3"], out["CO3"] = co2 * 44.01, hco3 * 61.017, co3 * 60.009
    return out


def carbonate_totals(ions: Dict[str, float]):
    """(CT mmol/L, carbonate alkalinity meq/L) of an ion dict."""
    co2 = ions.get("CO2", 0.0) / 44.01
    hco3 = ions.get("HCO3", 0.0) / 61.017
    co3 = ions.get("CO3", 0.0) / 60.009
    return co2 + hco3 + co3, hco3 + 2 * co3


def charge_balance(ions: Dict[str, float]):
    """Return (cation meq/L, anion meq/L)."""
    cat = sum(ions.get(i, 0.0) / mw * z for i, (mw, z) in CATIONS_MW_Z.items())
    an = sum(ions.get(i, 0.0) / mw * z for i, (mw, z) in ANIONS_MW_Z.items())
    return cat, an

class ROEngine:
    def __init__(self):
        """Initialize ROEngine with molar mass definitions and transport constants."""
        # Universal constants
        self.R_gas = 0.08314 # L*bar/(mol*K)
        
        self.MM = {
            "Ca": 40.078, "Mg": 24.305, "Na": 22.990, "K": 39.098,
            "Cl": 35.45, "SO4": 96.06, "HCO3": 61.0168, "Ba": 137.327,
            "Sr": 87.62, "F": 18.998, "SiO2": 60.08, "B": 10.81,
            "NO3": 62.00, "PO4": 94.97, "NH4": 18.04,
            "Al": 26.982, "Fe": 55.845, "Mn": 54.938, "CO2": 44.01,
            "CO3": 60.009, "Br": 79.904
        }
        
    def _calculate_osmotic_pressure(self, ions: Dict[str, float], temp_c: float) -> float:
        """
        Calculates osmotic pressure (bar) using van't Hoff equation with a simple
        osmotic coefficient assumption for mixed electrolytes.
        ions: concentration in mg/L
        """
        temp_k = temp_c + 273.15
        total_molarity = 0.0
        
        for ion, conc_mg_l in ions.items():
            if ion in self.MM and conc_mg_l > 0:
                molarity = (conc_mg_l / 1000.0) / self.MM[ion]
                total_molarity += molarity
                
        # Calculate total TDS to determine dynamic osmotic coefficient (phi)
        tds = sum(ions.values())
        if tds >= 70000:
            phi = 0.93
        elif tds >= 35000:
            # Seawater concentrate: phi rises again above ~0.7 mol/kg (NaCl data)
            phi = 0.90 + ((tds - 35000) / 35000.0) * 0.03
        elif tds > 10000:
            # Interpolate between 10000 (0.93) and 35000 (0.90)
            phi = 0.93 - ((tds - 10000) / 25000.0) * 0.03
        elif tds > 1000:
            phi = 0.93
        elif tds > 500:
            phi = 0.95
        elif tds > 100:
            # Interpolate between 100 (0.98) and 500 (0.95)
            phi = 0.98 - ((tds - 100) / 400.0) * 0.03
        else:
            phi = 1.0
            
        pi = total_molarity * self.R_gas * temp_k * phi
        return pi
        
    def _calculate_tcf(self, temp_c: float, E_Aw_over_R: float = None) -> float:
        """Temperature Correction Factor for water permeability.
        
        For NF membranes, uses membrane-specific E_Aw/R from the database (spec eq. NF-W-02).
        For RO membranes, falls back to the legacy PACE U=2640/3020 values.
        """
        temp_k = temp_c + 273.15
        if isinstance(E_Aw_over_R, (tuple, list)):
            # Calibrated two-segment value (below / above 25 C), e.g. from Toray DS2
            E_Aw_over_R = E_Aw_over_R[0] if temp_c <= 25.0 else E_Aw_over_R[1]
        if E_Aw_over_R is not None:
            # NF-W-02: TCF_A(T) = exp(E_Aw/R × (1/T_ref − 1/T))  — T_ref = 298.15 K
            U = E_Aw_over_R
        else:
            # Legacy RO correction factor (U = 2640 for T ≤ 25°C, U = 3020 for T > 25°C)
            U = 2640.0 if temp_c <= 25.0 else 3020.0
        return math.exp(U * (1.0/298.15 - 1.0/temp_k))

    @staticmethod
    def _calculate_tcf_salt(temp_c: float, E_B_over_R: float = None) -> float:
        """
        Temperature Correction Factor for salt permeability B (new).
        Salt passage rises ~3 %/C. Default E_B/R = 2700 K; override per membrane
        with "E_B_over_R" in the database once calibrated against Toray DS2.
        """
        if isinstance(E_B_over_R, (tuple, list)):
            # Calibrated two-segment value (below / above 25 C), e.g. from Toray DS2
            E_B_over_R = E_B_over_R[0] if temp_c <= 25.0 else E_B_over_R[1]
        U = 2700.0 if E_B_over_R is None else E_B_over_R
        return math.exp(U * (1.0/298.15 - 1.0/(temp_c + 273.15)))
        
    @staticmethod
    def _water_viscosity(temp_c: float) -> float:
        """
        Dynamic viscosity of water (Pa*s) using the Vogel equation:
        mu = 2.414e-5 * 10^(247.8 / (T_K - 140.0))
        Yields 0.890 mPa*s at 25 °C.
        """
        t_k = temp_c + 273.15
        return 2.414e-5 * math.pow(10.0, 247.8 / max(1.0, t_k - 140.0))

    def _calculate_cp_beta(self, flux_lmh: float, feed_flow_m3h: float, conc_flow_m3h: float, temp_c: float, membrane: Dict[str, Any], feed_ions: Dict[str, float] = None) -> float:
        """
        Calculate Concentration Polarization factor (Beta = Cm/Cb) using film theory and Sherwood correlation:
        Sh = 0.050 * Re^0.875 * Sc^0.25
        k = Sh * D_AB / d_h
        """
        # Average volumetric flow rate in m3/h -> m3/s
        avg_flow_m3h = max(0.001, (feed_flow_m3h + conc_flow_m3h) / 2.0)
        avg_flow_m3s = avg_flow_m3h / 3600.0

        # Spacer geometry properties (31 mil HPA datasheet default)
        spacer_mil = membrane.get("feed_spacer_mil", 31)
        t_fs = spacer_mil * 2.54e-5 # spacer thickness in meters (h)
        epsilon = 0.90
        # Hydraulic diameter: 4ε / [2/h + (1-ε)*8/h] = 1.01 mm for 31 mil
        d_h = (4.0 * epsilon) / ((2.0 / t_fs) + ((1.0 - epsilon) * 8.0 / t_fs))
        
        # Unrolled feed channel width W (m) approximated from active area and element length
        area_m2 = membrane.get("active_area_m2", 37.2)
        length_m = membrane.get("length_m", 1.016)
        w_total = area_m2 / (2.0 * length_m)
        
        # Cross-sectional flow area (assuming void fraction epsilon = 0.90)
        a_cross = w_total * t_fs * epsilon
        
        # Linear cross-flow velocity v (m/s)
        v = avg_flow_m3s / a_cross if a_cross > 0 else 0.1
        
        # Water dynamic viscosity mu_T (Pa*s) at temperature temp_c via Vogel equation
        mu_T = self._water_viscosity(temp_c)
        rho = 1000.0
        nu = mu_T / rho
        
        # Reynolds number Re
        Re = (d_h * v) / nu if nu > 0 else 100.0
        
        # Diffusivity of solute (m2/s) corrected for temperature using Stokes-Einstein
        mu_25 = self._water_viscosity(25.0)
        D_AB_25 = 1.6e-9 # m2/s default
        
        # Ion-specific diffusivities for Pass 2 (Optional Fix 2)
        if feed_ions is not None:
            D_AB_ions = {
                'Na':   1.33e-9,
                'Cl':   2.03e-9,
                'Ca':   0.79e-9,
                'Mg':   0.71e-9,
                'SO4':  1.07e-9,
                'HCO3': 1.19e-9,
                'K':    1.96e-9,
                'B':    1.10e-9,
                'NO3':  1.90e-9,
            }
            total_conc = sum(feed_ions.values())
            if total_conc >= 1.0:
                weighted = sum(conc * D_AB_ions.get(ion, 1.6e-9) for ion, conc in feed_ions.items())
                D_AB_25 = weighted / total_conc
        
        D_AB = D_AB_25 * (temp_c + 273.15) / 298.15 * (mu_25 / mu_T)
        
        # Schmidt number Sc
        Sc = nu / D_AB if D_AB > 0 else 600.0
        
        # Sherwood number Sh: 0.050 * Re^0.875 * Sc^0.25
        Sh = 0.050 * math.pow(Re, 0.875) * math.pow(Sc, 0.25)
        
        # Mass transfer coefficient k (m/s); "k_factor" calibrates beta to Toray DS2
        k = Sh * D_AB / d_h * membrane.get("k_factor", 1.0)
        
        # Water flux Jv in m/s
        jv_ms = (flux_lmh / 1000.0) / 3600.0
        
        # Polarization factor Beta
        if k > 0:
            beta = math.exp(jv_ms / k)
        else:
            beta = 1.0
            
        return beta

    def _calculate_pressure_drop(self, feed_flow_m3h: float, conc_flow_m3h: float, temp_c: float, membrane: Dict[str, Any]) -> float:
        """
        Calculate pressure drop per element (bar) using the Schock-Miquel friction correlation:
        dp = lambda * (L / d_h) * (rho * v^2 / 2)
        lambda = 6.23 * Re^-0.3
        """
        avg_flow_m3h = max(0.001, (feed_flow_m3h + conc_flow_m3h) / 2.0)
        avg_flow_m3s = avg_flow_m3h / 3600.0

        spacer_mil = membrane.get("feed_spacer_mil", 31)
        t_fs = spacer_mil * 2.54e-5 # spacer thickness in meters (h)
        epsilon = 0.90
        # Hydraulic diameter: 4ε / [2/h + (1-ε)*8/h] = 1.01 mm for 31 mil
        d_h = (4.0 * epsilon) / ((2.0 / t_fs) + ((1.0 - epsilon) * 8.0 / t_fs))
        
        area_m2 = membrane.get("active_area_m2", 37.2)
        length_m = membrane.get("length_m", 1.016)
        w_total = area_m2 / (2.0 * length_m)
        
        a_cross = w_total * t_fs * epsilon
        
        v = avg_flow_m3s / a_cross if a_cross > 0 else 0.1
        
        mu_T = self._water_viscosity(temp_c)
        rho = 1000.0
        nu = mu_T / rho
        Re = (d_h * v) / nu if nu > 0 else 100.0
        
        friction_factor = 6.23 * math.pow(Re, -0.3)
        dp_pa = friction_factor * (length_m / d_h) * (rho * v**2 / 2.0)
        dp_bar = dp_pa / 100000.0 * membrane.get("dp_factor", 1.0)   # calibrated to Toray DS2
        
        return max(0.001, min(dp_bar, 1.5))


    def _ion_transport(self, feed_ions: Dict[str, float], flux_lmh: float, beta_calc: float,
                       r: float, B_eff: float, sigmas: Dict[str, float], is_nf: bool,
                       nf_ps_dict: Dict[str, float], temp_c: float = 25.0,
                       ion_E: Dict[str, Any] = None,
                       pi_wall: float = 0.0, membrane: Dict[str, Any] = None):
        """
        Per-ion Spiegler-Kedem transport with film-theory CP and element mass balance.
        Returns (permeate_ions, membrane_surface_ions) in mg/L.

        RO: P_s,i = B * (1 - sigma_i) / (1 - sigma_ref), sigma_ref = sigma(Na).
            => passage_i ~ (1 - sigma_i). sigma values come from the database
               (sigma_i = 1 - f_i*(1 - sigma_ref)); they are NOT ion rejections.
        """
        perm, surface = {}, {}
        membrane = membrane or {}
        # Carbonate mode: if the feed carries CO2 (split_carbonate was called), the
        # permeate HCO3/CO3/pH follow from CO2 equilibrium + electroneutrality
        # (Toray DS2 behaviour); otherwise HCO3 is transported like other ions.
        carb_mode = (not is_nf) and feed_ions.get("CO2", 0) > 0
        # Salinity dependence of salt passage (calibrated vs Toray DS2):
        # charged ions share one factor (pi_wall / 1 bar) ^ n  ("salt_salinity_n"["Na"]);
        # Toray DS2 keeps the ratio of every strong ion to Na constant from 500 to
        # 45,000 mg/L, while neutral SiO2 and B(OH)3 do not follow salinity.
        sal_n = membrane.get("salt_salinity_n") or {}
        pic = sal_n.get("pi_c", 0.0)          # offset (bar): flattens the curve at low TDS
        sal_x = (max(pi_wall, 0.0) + pic) / (1.0 + pic)
        sal_fac = max(sal_x, 1e-3) ** sal_n.get("Na", 0.0) if (sal_n and not is_nf) else 1.0
        # pH dependence of salt passage above the reference pH (Toray DS2: strong-ion
        # passage rises ~25 % from pH 7.5 to 8.5): exp(k * max(0, pH - pH_ref))
        ph_k = membrane.get("salt_ph_k")
        if ph_k and not is_nf and feed_ions.get("CO2", 0) > 0 and feed_ions.get("HCO3", 0) > 0:
            ph_loc = carbonate_ph(feed_ions["HCO3"], feed_ions["CO2"], temp_c, ionic_strength(feed_ions))
            if ph_loc is not None and ph_loc > ph_k[1]:
                sal_fac *= math.exp(ph_k[0] * (ph_loc - ph_k[1]))
        # FIX: reference sigma read from the database (was hard-coded 0.9995)
        ref_sigma = sigmas.get("Na", 0.9995)
        jv_mh = flux_lmh / 1000.0
        for ion, feed_c in feed_ions.items():
            if feed_c <= 0:
                perm[ion] = 0.0
                surface[ion] = 0.0
                continue

            if (ion == "CO3" and not is_nf) or (carb_mode and ion == "HCO3"):
                # CO3 in the permeate is set by carbonate equilibrium afterwards
                perm[ion] = 0.0
                surface[ion] = feed_c * beta_calc
                continue

            sigma = sigmas.get(ion, ref_sigma if not is_nf else 0.347)

            # Ion-specific temperature behaviour relative to Na (calibrated vs Toray DS2):
            # (1 - sigma_i) is scaled by exp[dE_i/R * (1/298.15 - 1/T)]
            if ion_E and ion in ion_E and not is_nf and ion != "Na" and sigma > 0:
                e = ion_E[ion]
                e = e[0] if temp_c <= 25.0 else e[1]
                k_t = math.exp(e * (1.0/298.15 - 1.0/(temp_c + 273.15)))
                sigma = max(0.0, 1.0 - (1.0 - sigma) * k_t)

            if is_nf:
                P_s_ms = nf_ps_dict.get(ion, 5.80e-7)
            elif ion == "Na":
                # Na is the reference ion (B fitted to NaCl); Cl has its own factor
                P_s_ms = B_eff * sal_fac
                sigma = max(0.0, 1.0 - (1.0 - sigma) * sal_fac)
            else:
                P_s_ms = B_eff * (1.0 - sigma) / max(1e-6, 1.0 - ref_sigma)
                if ion in CATIONS_MW_Z or ion in ANIONS_MW_Z:
                    P_s_ms *= sal_fac
                    # keep passage proportional to (1 - sigma): scale sigma too
                    sigma = max(0.0, 1.0 - (1.0 - sigma) * sal_fac)
                elif ion in sal_n and sigma > 0:
                    # neutral species (SiO2, B) have their own salinity exponent
                    f_n = max(sal_x, 1e-3) ** sal_n[ion]
                    P_s_ms *= f_n
                    sigma = max(0.0, 1.0 - (1.0 - sigma) * f_n)
            P_s_mh = P_s_ms * 3600.0

            # Spiegler-Kedem true rejection
            if sigma <= 0.0:
                R_true = 0.0                         # dissolved gas (CO2)
            elif jv_mh > 0 and P_s_mh > 0:
                exp_val = math.exp(-(jv_mh * (1 - sigma)) / P_s_mh)
                R_true = 1.0 - (1 - sigma) / (1 - sigma * exp_val)
            else:
                R_true = 0.0

            denom = R_true + beta_calc * (1.0 - R_true)
            F_factor = (beta_calc * (1.0 - R_true)) / denom if denom > 0 else 0.0
            perm[ion] = feed_c * (F_factor * (1.0 + r)) / (1.0 + F_factor * r)
            bulk_c = feed_c * (1.0 + r) / (1.0 + F_factor * r)
            surface[ion] = bulk_c * beta_calc / denom if denom > 0 else bulk_c * beta_calc

        if carb_mode:
            perm = self._permeate_carbonate(perm, temp_c)
        return perm, surface

    @staticmethod
    def _permeate_carbonate(perm: Dict[str, float], temp_c: float) -> Dict[str, float]:
        """
        Permeate carbonate system: CO2 has passed freely; HCO3, CO3, H+ and OH-
        are set by equilibrium and electroneutrality with the strong ions:
            sum(strong cations) + H = sum(strong anions) + HCO3 + 2 CO3 + OH
        """
        out = dict(perm)
        co2 = out.get("CO2", 0.0) / 44.01 / 1000.0          # mol/L
        strong = {k: v for k, v in out.items() if k not in ("HCO3", "CO3")}
        cat, an = charge_balance(strong)
        if an > cat > 0:
            # Constant per-ion permeabilities do not conserve charge for every feed
            # mix. A strong-anion excess would otherwise be closed by H+ alone and
            # give permeate pH ~4 (not seen in DS2). Close it by a proportional
            # shift (< ~1 % per ion): cations up, anions down.
            x = (an - cat) / (an + cat)
            for k in strong:
                if k in CATIONS_MW_Z:
                    strong[k] *= (1 + x); out[k] = strong[k]
                elif k in ANIONS_MW_Z:
                    strong[k] *= (1 - x); out[k] = strong[k]
            cat, an = charge_balance(strong)
        delta = (cat - an) / 1000.0                           # eq/L
        I = ionic_strength(strong)
        g1 = 10 ** log_gamma(1, I, temp_c); g2 = 10 ** log_gamma(2, I, temp_c)
        K1 = 10 ** (-carbonic_pk1(temp_c)); K2 = 10 ** (-carbonic_pk2(temp_c)); Kw = 10 ** (-water_pkw(temp_c))

        def resid(ph):
            aH = 10 ** (-ph)
            hco3 = K1 * co2 / (aH * g1)
            co3 = K2 * hco3 * g1 / (aH * g2)
            return delta + aH / g1 - hco3 - 2 * co3 - Kw / (aH * g1), hco3, co3

        lo, hi = 2.0, 12.0                                     # resid decreases with pH
        for _ in range(80):
            mid = 0.5 * (lo + hi)
            if resid(mid)[0] > 0:
                lo = mid
            else:
                hi = mid
        _, hco3, co3 = resid(0.5 * (lo + hi))
        out["HCO3"] = hco3 * 61.017 * 1000.0
        out["CO3"] = co3 * 60.009 * 1000.0
        return out

    def simulate_element(self,
                         feed_flow_m3h: float, 
                         feed_pressure_bar: float,
                         feed_ions: Dict[str, float],
                         temp_c: float,
                         membrane: Dict[str, Any],
                         element_idx: int,
                         beta_cap: float = None,
                         max_flux_lmh: float = None,
                         A_override: float = None,
                         B_override: float = None,
                         perm_pressure_bar: float = 0.0) -> Dict[str, Any]:
        """
        Simulate a single RO/NF element performance.
        Self-consistent mass-balanced solver for flux and permeate concentration.
        
        A_override, B_override: if provided, use these aged values instead of
        the membrane database values (for aging engine integration).
        """
        # Initial guesses
        recovery = 0.10
        perm_flow_m3h = feed_flow_m3h * recovery
        conc_flow_m3h = feed_flow_m3h - perm_flow_m3h
        
        A = A_override if A_override is not None else membrane["permeability_A"]
        B = B_override if B_override is not None else membrane["permeability_B"]
        area = membrane["active_area_m2"]
        sigmas = membrane.get("sigma", {})

        # NF-specific transport: detect membrane type and extract Ps dict + E_Aw/R
        is_nf = membrane.get("type", "").upper() == "NF"
        nf_ps_dict = membrane.get("nf_ps", {})       # per-ion Ps (m/s) — NF only
        E_Aw_over_R = membrane.get("E_Aw_over_R")    # None for RO → legacy U fallback

        # NF-W-02: membrane-specific TCF for NF; legacy formula for RO
        tcf = self._calculate_tcf(temp_c, E_Aw_over_R)
        # FIX: salt permeability B was never temperature-corrected (RO only;
        # NF uses its own Ps table, left unchanged)
        tcf_b = 1.0 if is_nf else self._calculate_tcf_salt(temp_c, membrane.get("E_B_over_R"))
        # Osmotic pressure at the membrane wall (feed-side), used for the salinity
        # dependence of salt passage; updated each iteration with beta
        pi_feed_elem = self._calculate_osmotic_pressure(feed_ions, temp_c)
        pi_wall = pi_feed_elem
        converged = False

        # Iterative loop to converge on permeate flow and pressure
        max_iter = 20
        tolerance = 0.001
        
        current_perm_flow = perm_flow_m3h
        
        # We will compute these in the loop
        perm_ions = {}
        rej_ions = {}
        beta_actual = 1.0
        ndp = 0.0
        dp = 0.0
        
        for i in range(max_iter):
            # Estimate permeate flow -> flux
            flux_lmh = (current_perm_flow * 1000.0) / area

            
            # Calculate CP Beta
            beta_actual = self._calculate_cp_beta(flux_lmh, feed_flow_m3h, conc_flow_m3h, temp_c, membrane, feed_ions)
            beta_calc = min(beta_actual, beta_cap) if beta_cap is not None else beta_actual
            pi_wall = pi_feed_elem * beta_calc
            
            # Ratio r = Qp / (2 * Qc)
            r = current_perm_flow / (2.0 * max(0.001, feed_flow_m3h - current_perm_flow))
            
            # Calculate concentrations self-consistently
            loop_perm_ions, surface_ions = self._ion_transport(
                feed_ions, flux_lmh, beta_calc, r, B * tcf_b, sigmas, is_nf, nf_ps_dict,
                temp_c, membrane.get("ion_E_over_R"), pi_wall=pi_wall, membrane=membrane)

            # Osmotic pressure at surface and permeate
            pi_surface = self._calculate_osmotic_pressure(surface_ions, temp_c)
            pi_perm = self._calculate_osmotic_pressure(loop_perm_ions, temp_c)
            delta_pi = max(0.0, pi_surface - pi_perm)
            
            # Pressure drop across element (Schock-Miquel friction correlation)
            dp = self._calculate_pressure_drop(feed_flow_m3h, conc_flow_m3h, temp_c, membrane)
            
            avg_feed_pressure = feed_pressure_bar - dp/2.0
            if avg_feed_pressure < 1.0:
                avg_feed_pressure = 1.0
                
            perm_pressure = perm_pressure_bar
            
            # Net Driving Pressure
            ndp = avg_feed_pressure - perm_pressure - delta_pi
            if ndp < 0:
                ndp = 0
                
            # Calculate new flux
            # Water permeability falls with salinity at the membrane wall (seen in
            # Toray DS2: A at ~40-53 bar osmotic is ~0.55-0.6x A in brackish water).
            # S = 1 / (1 + (pi_m / pi0)^m); membrane key "A_salinity" = (pi0, m)
            sal = membrane.get("A_salinity")
            s_fac = 1.0 / (1.0 + (pi_surface / sal[0]) ** sal[1]) if sal and pi_surface > 0 else 1.0
            new_flux_lmh = A * ndp * tcf * s_fac
            if max_flux_lmh is not None:
                new_flux_lmh = min(new_flux_lmh, max_flux_lmh)
                
            new_perm_flow = (new_flux_lmh * area) / 1000.0
            
            # Update flows
            old_perm_flow = current_perm_flow
            current_perm_flow = 0.7 * current_perm_flow + 0.3 * new_perm_flow
            
            if current_perm_flow > 0.99 * feed_flow_m3h:
                current_perm_flow = 0.99 * feed_flow_m3h
                
            conc_flow_m3h = feed_flow_m3h - current_perm_flow
            
            if abs(new_perm_flow - old_perm_flow) < tolerance:
                converged = True
                break

        # Final flow state
        perm_flow_m3h = current_perm_flow
        flux_lmh = (perm_flow_m3h * 1000.0) / area
        element_recovery = perm_flow_m3h / feed_flow_m3h

        # FIX: recompute concentrations at the FINAL flow (previously the last
        # loop's concentrations, computed at the old flow, were used -> small
        # mass-balance error in the reject)
        beta_actual = self._calculate_cp_beta(flux_lmh, feed_flow_m3h, conc_flow_m3h, temp_c, membrane, feed_ions)
        beta_calc = min(beta_actual, beta_cap) if beta_cap is not None else beta_actual
        r = perm_flow_m3h / (2.0 * max(0.001, conc_flow_m3h))
        perm_ions, _ = self._ion_transport(
            feed_ions, flux_lmh, beta_calc, r, B * tcf_b, sigmas, is_nf, nf_ps_dict,
            temp_c, membrane.get("ion_E_over_R"), pi_wall=pi_wall, membrane=membrane)

        # Permeate CO3 from carbonate equilibrium (HCO3 and CO2 come from transport)
        if (not is_nf and perm_ions.get("HCO3", 0) > 0 and perm_ions.get("CO2", 0) > 0
                and "CO3" in feed_ions and feed_ions.get("CO2", 0) <= 0):
            I_p = ionic_strength(perm_ions)
            ph_p = carbonate_ph(perm_ions["HCO3"], perm_ions["CO2"], temp_c, I_p)
            g1 = 10 ** log_gamma(1, I_p, temp_c); g2 = 10 ** log_gamma(2, I_p, temp_c)
            perm_ions["CO3"] = (10 ** (-carbonic_pk2(temp_c)) * g1 * perm_ions["HCO3"] / 61.017
                                / (10 ** (-ph_p) * g2) * 60.009)

        # Final reject concentrations via mass balance
        for ion in feed_ions.keys():
            if feed_flow_m3h > 0 and conc_flow_m3h > 0:
                mass_in = feed_flow_m3h * feed_ions[ion]
                mass_perm = perm_flow_m3h * perm_ions[ion]
                rej_c = (mass_in - mass_perm) / conc_flow_m3h
                rej_ions[ion] = max(0.0, rej_c)
            else:
                rej_ions[ion] = 0.0

        # Reject: total carbonate and alkalinity are mass-balanced above; re-split
        # them into CO2/HCO3/CO3 at the reject composition (CO2 builds up, pH rises)
        if not is_nf and feed_ions.get("CO2", 0) > 0 and conc_flow_m3h > 0:
            ct, alk = carbonate_totals(rej_ions)
            rej_ions = respeciate_carbonate(rej_ions, ct, alk, temp_c)

        # --- Donnan Electroneutrality Correction for NF (spec Section 3.6) ---
        # NF membranes selectively reject divalent anions (SO4) over monovalent anions (Cl).
        # This creates a charge imbalance in the permeate. Cl- is adjusted to ensure
        # electroneutrality: sum(cation meq) = sum(anion meq including Cl).
        if is_nf and feed_ions.get("Cl", 0) > 0 and perm_flow_m3h > 0:
            _cat_mw_z = CATIONS_MW_Z
            _an_mw_z = {k: v for k, v in ANIONS_MW_Z.items() if k != "Cl"}
            sum_cat_meq = sum(perm_ions.get(ion, 0) / mw * z
                             for ion, (mw, z) in _cat_mw_z.items())
            sum_an_meq  = sum(perm_ions.get(ion, 0) / mw * z
                             for ion, (mw, z) in _an_mw_z.items())
            cl_required_meq = sum_cat_meq - sum_an_meq
            cl_perm_donnan = max(0.0, cl_required_meq * 35.45)  # meq/L → mg/L
            # Physical cap: Cl permeate cannot exceed feed Cl concentration
            cl_perm_donnan = min(cl_perm_donnan, feed_ions.get("Cl", 0) * 1.05)
            if cl_perm_donnan > 0:
                perm_ions["Cl"] = cl_perm_donnan
                # Recompute concentrate Cl via mass balance
                if conc_flow_m3h > 0:
                    mass_cl_in   = feed_flow_m3h * feed_ions.get("Cl", 0)
                    mass_cl_perm = perm_flow_m3h * cl_perm_donnan
                    rej_ions["Cl"] = max(0.0, (mass_cl_in - mass_cl_perm) / conc_flow_m3h)
                
        return {
            "element_idx": element_idx,
            "feed_flow": feed_flow_m3h,
            "perm_flow": perm_flow_m3h,
            "conc_flow": conc_flow_m3h,
            "feed_pressure": feed_pressure_bar,
            "conc_pressure": feed_pressure_bar - dp,
            "dp": dp,
            "flux": flux_lmh,
            "ndp": ndp,
            "beta": beta_actual,
            "recovery": element_recovery,
            "converged": converged,
            "feed_ions": feed_ions,
            "perm_ions": perm_ions,
            "rej_ions": rej_ions
        }

    def simulate_system(self,
                        feed_flow_m3h: float,
                        feed_pressure_bar: float,
                        feed_ions: Dict[str, float],
                        temp_c: float,
                        membrane_model: str,
                        stages: int,
                        vessels_per_stage: List[int],
                        elements_per_vessel: int,
                        beta_cap: float = None,
                        max_flux_lmh: float = None,
                        aged_params: Dict = None,
                        permeate_pressure_bar: float = 0.0,
                        enable_booster: bool = False,
                        interboost_dp_bar: float = None,
                        erd_efficiency: float = None,
                        age_years: float = 0.0,
                        flow_factor: float = None) -> Dict[str, Any]:
        """
        Simulate an entire RO/NF array with interstage booster pump calculations.
        vessels_per_stage: e.g., [4, 2] for a 2-stage system
        
        aged_params: optional dict keyed by (stage, element) tuples containing
        {"A": float, "B": float, "dh": float} for aged membrane simulation.
        If provided, element-wise A and B are overridden from this dict.

        feed_ions may include "CO2" (use split_carbonate() with the feed pH first);
        CO2 then passes at 0 % rejection and permeate/reject pH are reported.
        erd_efficiency: optional energy-recovery device efficiency (e.g. 0.95 for
        an isobaric PX device on SWRO). None = no ERD (previous behaviour).
        age_years: membrane age for a guarantee projection (Toray DS2 uses 3 years).
            B_aged = B * (1 + SPI)^age, A_aged = A * (1 - flux decline)^age,
            with "spi_pct_per_yr" / "flux_decline_pct_per_yr" from the database.
        flow_factor: fouling / flow allowance applied to A on top of ageing
            (Toray DS2 "Flow Allowance" by water type, e.g. 0.861 for filtered
            tertiary waste at age 0). None = 1.0.
        """
        membrane = MembraneDatabase.get_ro_membrane(membrane_model)

        # Ageing for guarantee projections (same convention as Toray DS2)
        age_A = age_B = None
        if age_years and age_years > 0:
            spi = membrane.get("spi_pct_per_yr", 10.0) / 100.0
            fdec = membrane.get("flux_decline_pct_per_yr", 5.3) / 100.0
            age_B = membrane["permeability_B"] * (1.0 + spi) ** age_years
            age_A = membrane["permeability_A"] * (1.0 - fdec) ** age_years
        if flow_factor:
            age_A = (age_A if age_A is not None else membrane["permeability_A"]) * flow_factor
        
        # Normalize permeate backpressure to 0.0 if omitted or passed as None
        permeate_pressure_bar = 0.0 if permeate_pressure_bar is None else float(permeate_pressure_bar)
        
        system_results = {
            "stages": [],
            "elements": [],
            "booster_pumps": [],
            "warnings": []
        }
        
        current_feed_flow = feed_flow_m3h
        current_feed_pressure = feed_pressure_bar
        current_ions = feed_ions.copy()
        
        total_perm_flow = 0.0
        total_perm_mass = {k: 0.0 for k in feed_ions.keys()}
        total_booster_power_kw = 0.0
        
        for stage_idx in range(stages):
            vessels = vessels_per_stage[stage_idx] if stage_idx < len(vessels_per_stage) else 1
            
            # Flow per vessel
            vessel_feed_flow = current_feed_flow / vessels
            
            stage_perm_flow = 0.0
            stage_perm_mass = {k: 0.0 for k in feed_ions.keys()}
            
            vessel_current_flow = vessel_feed_flow
            vessel_current_pressure = current_feed_pressure
            vessel_current_ions = current_ions.copy()
            
            for elem_idx in range(elements_per_vessel):
                global_elem_idx = stage_idx * elements_per_vessel + elem_idx + 1
                
                # Check limits
                if vessel_current_flow > membrane["max_feed_flow_m3h"]:
                    system_results["warnings"].append({
                        "type": f"Feed Flow > Max (S{stage_idx+1}-E{elem_idx+1})",
                        "element": f"S{stage_idx+1}-E{elem_idx+1}",
                        "limit": membrane["max_feed_flow_m3h"],
                        "value": vessel_current_flow
                    })
                
                if vessel_current_flow < membrane["min_conc_flow_m3h"]:
                     system_results["warnings"].append({
                        "type": f"Flow < Min Conc Flow (S{stage_idx+1}-E{elem_idx+1})",
                        "element": f"S{stage_idx+1}-E{elem_idx+1}",
                        "limit": membrane["min_conc_flow_m3h"],
                        "value": vessel_current_flow
                    })

                # Apply aged parameter overrides if provided
                a_ovr = age_A
                b_ovr = age_B
                if aged_params:
                    key = (stage_idx + 1, elem_idx + 1)
                    if key in aged_params:
                        a_ovr = aged_params[key].get("A")
                        b_ovr = aged_params[key].get("B")

                res = self.simulate_element(
                    vessel_current_flow, vessel_current_pressure, vessel_current_ions,
                    temp_c, membrane, global_elem_idx, beta_cap, max_flux_lmh,
                    A_override=a_ovr, B_override=b_ovr, perm_pressure_bar=permeate_pressure_bar
                )
                
                # Check feed pressure limit
                max_p = membrane.get("max_pressure_bar", 41.0)   # FIX: same default used in the message (was KeyError)
                if vessel_current_pressure > max_p:
                    system_results["warnings"].append({
                        "type": f"Feed Pressure > Max (S{stage_idx+1}-E{elem_idx+1})",
                        "element": f"S{stage_idx+1}-E{elem_idx+1}",
                        "limit": max_p,
                        "value": vessel_current_pressure
                    })
                    
                # Check element recovery limit
                elem_rec_pct = res["recovery"] * 100.0
                max_rec = membrane.get("max_recovery_pct", 15.0)   # FIX: was KeyError if missing
                if elem_rec_pct > max_rec:
                    system_results["warnings"].append({
                        "type": f"Element Recovery > Max (S{stage_idx+1}-E{elem_idx+1})",
                        "element": f"S{stage_idx+1}-E{elem_idx+1}",
                        "limit": max_rec,
                        "value": elem_rec_pct
                    })

                # FIX: flag elements whose flux/pressure solver did not converge
                if not res.get("converged", True):
                    system_results["warnings"].append({
                        "type": f"Solver not converged (S{stage_idx+1}-E{elem_idx+1})",
                        "element": f"S{stage_idx+1}-E{elem_idx+1}",
                        "limit": "20 iterations", "value": res["perm_flow"]
                    })

                # Check Concentration Polarization limit (beta >= 1.20)
                beta_val = res["beta"]
                if beta_val >= 1.20:
                    system_results["warnings"].append({
                        "type": f"Concentration Polarization (\u03b2) > 1.20 (S{stage_idx+1}-E{elem_idx+1})",
                        "element": f"S{stage_idx+1}-E{elem_idx+1}",
                        "limit": 1.20,
                        "value": beta_val
                    })
                
                # Element-wise results scaled up by number of vessels in stage for system view
                elem_sys_view = res.copy()
                elem_sys_view["stage"] = stage_idx + 1
                elem_sys_view["position"] = elem_idx + 1
                
                system_results["elements"].append(elem_sys_view)
                
                # Accumulate permeate
                stage_perm_flow += res["perm_flow"] * vessels
                for ion in current_ions.keys():
                    stage_perm_mass[ion] += res["perm_ions"][ion] * res["perm_flow"] * vessels
                    
                # Setup next element in series
                vessel_current_flow = res["conc_flow"]
                vessel_current_pressure = res["conc_pressure"]
                vessel_current_ions = res["rej_ions"].copy()
                
            # Stage completed. Capture exit conditions before inter-stage transition
            stage_exit_pressure = vessel_current_pressure
            stage_exit_flow = vessel_current_flow * vessels  # Total concentrate flow from all vessels
            stage_exit_ions = vessel_current_ions.copy()
            
            # Accumulate to system total
            total_perm_flow += stage_perm_flow
            for ion in current_ions.keys():
                total_perm_mass[ion] += stage_perm_mass[ion]
                
            system_results["stages"].append({
                "stage": stage_idx + 1,
                "feed_flow": vessel_feed_flow * vessels,
                "perm_flow": stage_perm_flow,
                "conc_flow": stage_exit_flow,
                "recovery": stage_perm_flow / (vessel_feed_flow * vessels)
            })
            
            # --- INTERSTAGE BOOSTER PUMP CALCULATION ---
            if stage_idx < stages - 1:
                # Calculate osmotic pressure of the concentrate leaving this stage
                pi_conc = self._calculate_osmotic_pressure(stage_exit_ions, temp_c)
                
                # Required feed pressure for the next stage:
                # Need enough NDP to maintain balanced flux across stages.
                # Target NDP: set to average NDP of the preceding stage.
                stage_elements = [el for el in system_results["elements"] if el["stage"] == stage_idx + 1]
                avg_stage_ndp = sum(el["ndp"] for el in stage_elements) / len(stage_elements) if stage_elements else 1.0
                target_ndp = max(0.5, avg_stage_ndp) # ensure at least positive NDP
                
                permeate_backpressure = permeate_pressure_bar  # bar
                piping_loss = 0.5  # bar, inter-stage piping friction
                
                p_required = pi_conc + target_ndp + permeate_backpressure
                p_available = stage_exit_pressure - piping_loss
                
                # Booster pump is OFF by default; only active if enable_booster is True
                if enable_booster and interboost_dp_bar is not None:
                    boost_dp = max(0.0, float(interboost_dp_bar))
                elif enable_booster:
                    boost_dp = max(0.0, p_required - p_available)
                else:
                    boost_dp = 0.0
                
                # Booster pump power: P = Q * ΔP / (36 * η)
                # η = 0.75 for typical centrifugal booster pump
                pump_efficiency = 0.75
                booster_flow = stage_exit_flow  # Total concentrate flow through booster
                
                if boost_dp > 0:
                    booster_power_kw = (booster_flow * boost_dp) / (36.0 * pump_efficiency)
                    booster_required = True
                else:
                    booster_power_kw = 0.0
                    booster_required = False
                
                total_booster_power_kw += booster_power_kw

                # FIX: booster is OFF by default; warn when the next stage is
                # starved of pressure (seen in BIDCO: stage-2 flux drop, S1-E6 recovery warning)
                if not enable_booster and p_available < p_required:
                    system_results["warnings"].append({
                        "type": f"Interstage pressure low (Stage {stage_idx+2}) - consider booster",
                        "element": f"Stage {stage_idx+2}",
                        "limit": round(p_required, 2), "value": round(p_available, 2)
                    })
                
                booster_data = {
                    "location": f"Between Stage {stage_idx + 1} and Stage {stage_idx + 2}",
                    "from_stage": stage_idx + 1,
                    "to_stage": stage_idx + 2,
                    "flow_m3h": round(booster_flow, 2),
                    "inlet_pressure_bar": round(p_available, 2),
                    "osmotic_pressure_bar": round(pi_conc, 2),
                    "required_pressure_bar": round(p_required, 2),
                    "outlet_pressure_bar": round(p_available + boost_dp, 2),
                    "boost_dp_bar": round(boost_dp, 2),
                    "power_kw": round(booster_power_kw, 2),
                    "required": booster_required,
                    "status": "ACTIVE" if booster_required else ("BYPASSED" if not enable_booster else "NOT_REQUIRED"),
                    "reason": f"NDP target {target_ndp:.1f} bar" if boost_dp > 0 else "Pressure sufficient without booster",
                    "pump_efficiency": pump_efficiency
                }
                
                system_results["booster_pumps"].append(booster_data)
                
                # Update feed conditions for next stage
                current_feed_flow = stage_exit_flow
                current_feed_pressure = p_available + boost_dp  # Pressure after booster (or p_available when booster off)
                current_ions = stage_exit_ions.copy()
            else:
                # Last stage — no booster needed
                current_feed_flow = stage_exit_flow
                current_ions = stage_exit_ions.copy()
            
        # Final System summary
        # FIX: TDS on Toray DS2 basis = all ions + SiO2 + B; only CO2 excluded
        # (previously B was excluded, and the report footnote said SiO2 was excluded)
        system_perm_ions = {}
        system_perm_tds = 0.0
        feed_tds = sum(v for k, v in feed_ions.items() if k not in TDS_EXCLUDE)
        conc_tds = sum(v for k, v in current_ions.items() if k not in TDS_EXCLUDE)
        
        for ion in feed_ions.keys():
            if total_perm_flow > 0:
                c = total_perm_mass[ion] / total_perm_flow
                system_perm_ions[ion] = c
                if ion not in TDS_EXCLUDE:
                    system_perm_tds += c
            else:
                system_perm_ions[ion] = 0.0
                
        # Mixed permeate re-equilibrated: carbonate follows CO2 + electroneutrality
        # of the blended strong ions (element permeates are not additive in pH)
        if feed_ions.get("CO2", 0) > 0 and total_perm_flow > 0 and membrane.get("type", "").upper() != "NF":
            system_perm_ions = self._permeate_carbonate(system_perm_ions, temp_c)
            system_perm_tds = sum(v for k, v in system_perm_ions.items() if k not in TDS_EXCLUDE)

        total_area = sum(vessels_per_stage) * elements_per_vessel * membrane["active_area_m2"]
        avg_flux = (total_perm_flow * 1000.0) / total_area
        system_recovery = total_perm_flow / feed_flow_m3h
        
        # SEC Calculation — includes high pressure pump + all booster pumps
        # High pressure pump: Power = Q * P / (36 * efficiency)
        hp_pump_efficiency = 0.80
        hp_pump_power_kw = (feed_flow_m3h * feed_pressure_bar) / (36.0 * hp_pump_efficiency)
        # FIX (new option): energy recovery device on the reject (SWRO)
        erd_recovered_kw = 0.0
        if erd_efficiency:
            erd_recovered_kw = current_feed_flow * max(0.0, stage_exit_pressure) * erd_efficiency / 36.0
        total_power_kw = hp_pump_power_kw + total_booster_power_kw - erd_recovered_kw
        sec = total_power_kw / total_perm_flow if total_perm_flow > 0 else 0
        
        # Calculate total differential pressure across the system
        total_boost_dp = sum(b.get("boost_dp_bar", 0.0) for b in system_results.get("booster_pumps", []))
        total_dp_bar = feed_pressure_bar - stage_exit_pressure + total_boost_dp
        total_tmp_bar = feed_pressure_bar - (total_dp_bar / 2.0)

        system_results["summary"] = {
            "total_recovery": system_recovery,
            "feed_flow": feed_flow_m3h,
            "perm_flow": total_perm_flow,
            "conc_flow": current_feed_flow,
            "avg_flux_lmh": avg_flux,
            "feed_pressure_bar": feed_pressure_bar,
            "conc_pressure_bar": stage_exit_pressure,
            "permeate_pressure_bar": permeate_pressure_bar,
            "total_dp_bar": round(total_dp_bar, 2),
            "total_tmp_bar": round(total_tmp_bar, 2),
            "hp_pump_power_kw": round(hp_pump_power_kw, 2),
            "booster_pump_power_kw": round(total_booster_power_kw, 2),
            "erd_recovered_kw": round(erd_recovered_kw, 2),
            "total_power_kw": round(total_power_kw, 2),
            "sec_kwh_m3": sec,
            "feed_tds": feed_tds,
            "perm_tds": system_perm_tds,
            "conc_tds": conc_tds,
            "perm_ions": system_perm_ions,
            # NEW: charge balance check (cation meq/L, anion meq/L) and pH from CO2/HCO3
            "perm_charge_balance_meq": tuple(round(x, 4) for x in charge_balance(system_perm_ions)),
            "perm_ph": carbonate_ph(system_perm_ions.get("HCO3", 0), system_perm_ions.get("CO2", 0), temp_c,
                                    ionic_strength(system_perm_ions)),
            "conc_ph": carbonate_ph(current_ions.get("HCO3", 0), current_ions.get("CO2", 0), temp_c,
                                    ionic_strength(current_ions)),
            "age_years": age_years,
            "conc_ions": current_ions,
            "vessels_per_stage": vessels_per_stage
        }
        
        return system_results
