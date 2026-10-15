# PACE Calculation Module — Complete Technical Documentation

**Project:** Permionics Automated Calculation Engine (PACE)
**Source of truth:** `backend/` Python source code (not specification documents)
**Generated from:** Direct source code analysis
**Scope:** All backend calculation modules

---

# TABLE OF CONTENTS

1. [Architecture Overview](#1-architecture-overview)
2. [calc_engine.py — Core Element Simulation](#2-calc_enginepy--core-element-simulation)
3. [system_engine.py — System Orchestration & Economics](#3-system_enginepy--system-orchestration--economics)
4. [physics_aging_engine.py — Multi-Year Physics Projection](#4-physics_aging_enginepy--multi-year-physics-projection)
5. [conditioning.py — Interstage Chemical Conditioning](#5-conditioningpy--interstage-chemical-conditioning)
6. [membrane_recommender.py — Membrane Scoring Engine](#6-membrane_recommenderpy--membrane-scoring-engine)
7. [server_impl.py — API Layer & Chemistry](#7-server_implpy--api-layer--chemistry)
8. [Traceability Matrix](#8-traceability-matrix)

---

# 1. Architecture Overview

```
server_impl.py  (FastAPI endpoints)
      │
      ├── /api/calculate-system ──────► system_engine.py
      │                                      │
      │                                      └──► calc_engine.py (ROEngine)
      │                                               └── simulate_element()
      │                                               └── simulate_system()
      │
      ├── /api/simulate-aging ─────────► _run_projection_core()
      ├── /api/calculate-system-physics ►      │
      │                                        └──► physics_aging_engine.py
      │                                                     │
      │                                                     └──► calc_engine.py (aged_params)
      │
      ├── /api/recommend-membrane ─────► membrane_recommender.py
      │                                      └──► system_engine.py (per membrane)
      │
      ├── /api/process-recommendation ─► process_engine.py + PHREEQC
      ├── /api/calculate-scaling ──────► PHREEQC (direct)
      └── /api/auto-balance ───────────► Inline CBE logic (server_impl.py)
```

**Technology train routing (`system_engine.py`):**
- `RO`, `UF+RO`, `NF`, `UF+NF` → `calculate_system()`
- `2P-RO`, `UF+2P-RO` → `simulate_two_pass_system()`
- Any train + recycle → `calculate_system_with_recycle()`

**Module-level physics constants (`physics_aging_engine.py`):**

| Constant | Value | Units | Meaning |
|---|---|---|---|
| `NZ` | 10 | — | Axial segments per element |
| `DT_H` | 730.0 | h | Monthly timestep (~1 month) |
| `R_GAS` | 8.314 | J/(mol·K) | Universal gas constant |
| `Ds_25` | 1.6×10⁻⁹ | m²/s | Solute diffusivity at 25°C |
| `MU_25` | 8.9×10⁻⁴ | Pa·s | Water viscosity at 25°C |
| `RHO_W` | 1000.0 | kg/m³ | Water density |

---

# 2. `calc_engine.py` — Core Element Simulation

**File:** `backend/calc_engine.py` | 659 lines | 29,801 bytes
**Docstring:** "Implements Solution-Diffusion and Spiegler-Kedem mass transport models."

## 2.1 Purpose

Element-level RO/NF physics. Every higher-level engine calls this. Has no knowledge of multi-stage topology.

## 2.2 Class `ROEngine` — Constants

`self.R_gas = 0.08314` L·bar/(mol·K)

**Molar mass table `self.MM` (g/mol):**

| Ion | MW | Ion | MW | Ion | MW |
|---|---|---|---|---|---|
| Ca | 40.078 | Cl | 35.45 | SiO2 | 60.08 |
| Mg | 24.305 | SO4 | 96.06 | B | 10.81 |
| Na | 22.990 | HCO3 | 61.0168 | NO3 | 62.00 |
| K | 39.098 | Ba | 137.327 | PO4 | 94.97 |
| Sr | 87.62 | F | 18.998 | NH4 | 18.04 |
| Al | 26.982 | Fe | 55.845 | Mn | 54.938 |

---

## 2.3 `_calculate_osmotic_pressure` (Lines 23–55)

**Inputs:** `ions` (mg/L dict), `temp_c` (°C)
**Output:** osmotic pressure (bar)

$$T_K = T_{°C} + 273.15$$

$$m_i = \frac{C_i \,[\text{mg/L}]}{1000 \times MW_i} \quad \text{mol/L}$$

$$C_{total} = \sum_i m_i$$

**Piecewise osmotic coefficient** $\varphi$ (TDS = $\sum C_i$ mg/L):

| TDS (mg/L) | $\varphi$ |
|---|---|
| ≤ 100 | 1.000 |
| 100–500 | $0.98 - \frac{\text{TDS}-100}{400} \times 0.03$ |
| 500–1,000 | 0.950 |
| 1,000–10,000 | 0.930 |
| 10,000–35,000 | $0.93 - \frac{\text{TDS}-10000}{25000} \times 0.03$ |
| ≥ 35,000 | 0.900 |

$$\boxed{\pi = C_{total} \times R_{gas} \times T_K \times \varphi \quad \text{(bar)}}$$

**Source:** Van't Hoff (1887). Piecewise φ: [INTERNAL METHOD — Permionics calibration]

---

## 2.4 `_calculate_tcf` (Lines 57–70)

**NF path** (`E_Aw_over_R` provided):
$$TCF_{NF} = \exp\!\left[\frac{E_{Aw}}{R} \times \left(\frac{1}{298.15} - \frac{1}{T_K}\right)\right]$$

**RO path** (`E_Aw_over_R` = None):
$$TCF_{RO} = \exp\!\left[U \times \left(\frac{1}{298.15} - \frac{1}{T_K}\right)\right]$$

$$U = \begin{cases} 2640\,\text{K} & T_{°C} \leq 25 \\ 3020\,\text{K} & T_{°C} > 25 \end{cases}$$

**Source:** [INTERNAL METHOD — based on DuPont FILMTEC TCF conventions]

---

## 2.5 `_calculate_cp_beta` (Lines 72–149)

**Purpose:** Concentration polarisation factor $\beta = C_{membrane}/C_{bulk}$

**Spacer geometry:**
$$t_{fs} = \text{spacer\_mil} \times 2.54 \times 10^{-5}\,\text{m}, \quad d_h = 2\,t_{fs}$$

**Channel cross-section (void fraction $\varepsilon = 0.90$):**
$$W = \frac{A_{active}}{2\,L_{elem}}, \quad A_{cross} = W \times t_{fs} \times 0.90\,\text{m}^2$$

**Andrade viscosity:**
$$\mu(T) = 10^{-3} \exp\!\left(\frac{1808.0}{T_K} - 6.354\right) \text{Pa·s}$$

**Reynolds number:**
$$Re = \frac{d_h \cdot v}{\nu}, \quad v = \frac{Q_{m^3/s}}{A_{cross}}, \quad \nu = \frac{\mu}{1000}$$

**Ion-specific diffusivities at 25°C (m²/s):**
Na=1.33e-9, Cl=2.03e-9, Ca=0.79e-9, Mg=0.71e-9, SO4=1.07e-9, HCO3=1.19e-9, K=1.96e-9, B=1.10e-9, NO3=1.90e-9; default=1.6e-9

**Concentration-weighted diffusivity:**
$$D_{AB,25} = \frac{\sum_i C_i D_i}{\sum_i C_i}$$

**Stokes–Einstein T-correction:**
$$D_{AB}(T) = D_{AB,25} \times \frac{T_K}{298.15} \times \frac{\mu_{25}}{\mu(T)}$$

**Schock–Miquel correlation:**
$$Sh = 0.04 \times Re^{0.75} \times Sc^{0.33}, \quad Sc = \frac{\nu}{D_{AB}}$$

$$k_M = \frac{Sh \times D_{AB}}{d_h}\,\text{m/s}$$

**Film-theory CP:**
$$\boxed{\beta = \exp\!\left(\frac{J_v}{k_M}\right)}, \quad J_v = \frac{J_{LMH}}{3.6 \times 10^6}\,\text{m/s}$$

Returns 1.0 if $k_M \leq 0$. Capped at `beta_cap` (default 1.25).

**Source:** Schock & Miquel (1987), Desalination 64:339–352 [VERIFIED — External]

---

## 2.6 `_calculate_pressure_drop` (Lines 151–182)

Same geometry as CP calculation, then:

**Schock–Miquel friction factor:**
$$\lambda = 6.23 \times Re^{-0.30}$$

**Darcy–Weisbach:**
$$\Delta P_{Pa} = \lambda \times \frac{L_{elem}}{d_h} \times \frac{\rho_w v^2}{2}$$
$$\Delta P_{bar} = \frac{\Delta P_{Pa}}{10^5}, \quad \text{clipped to } [0.001,\,1.5]$$

**Source:** Schock & Miquel (1987) [VERIFIED — External]

---

## 2.7 `simulate_element` — Spiegler–Kedem Solute Transport (Lines 250–295)

**Reflection coefficient** $\sigma_i$: RO global default = 0.99; NF global default = 0.347 (ion-specific values from `MembraneDatabase`).

**RO salt permeability from B (m/s):**
$$P_{s,mh} = \frac{B \times (1-\sigma)}{0.01} \times 3600\,\text{m/h}$$

**Spiegler–Kedem true rejection:**
$$\text{exp} = -\frac{J_{v,mh} \times (1-\sigma)}{P_{s,mh}}, \quad F_i = \frac{1-\sigma}{1-\sigma\,e^{\text{exp}}}$$
$$\boxed{R_{true} = 1 - F_i}$$

Edge cases: `OverflowError` → $R_{true} = \sigma$; $J_v \leq 0$ or $P_s \leq 0$ → $R_{true} = 0$.

**Self-consistent bulk/permeate concentrations:**
$$r = \frac{Q_{perm}}{2\,\max(0.001,\,Q_{feed}-Q_{perm})}, \quad \text{denom} = R_{true} + \beta(1-R_{true})$$
$$F_{factor} = \frac{\beta(1-R_{true})}{\text{denom}}$$
$$C_{perm,i} = C_{f,i} \times \frac{F_{factor}(1+r)}{1 + F_{factor}\,r}$$

**Source:** Spiegler & Kedem (1966), Desalination 1(4):311–326 [VERIFIED — External]

---

## 2.8 `simulate_element` — Water Transport & Iteration (Lines 302–330)

**Net Driving Pressure:**
$$NDP = \max(0,\,P_{avg} - 0.5 - \Delta\pi)\,\text{bar}$$

$P_{avg} = \max(1.0,\,P_{feed} - dp/2)$; 0.5 bar = permeate backpressure.

**Solution-Diffusion flux:**
$$J_{v,new} = A \times NDP \times TCF\,\text{LMH}$$

**Damped fixed-point iteration:**
$$Q_{perm} \leftarrow 0.7\,Q_{perm,old} + 0.3\,Q_{perm,new}, \quad Q_{perm} \leq 0.99\,Q_{feed}$$

- Initial guess: $Q_{perm,0} = 0.10\,Q_{feed}$
- Max 20 iterations; tolerance: $|Q_{new}-Q_{old}| < 0.001$ m³/h
- Damping required because flux→CP→osmotic pressure→NDP→flux is a positively-coupled loop

**Source:** Wijmans & Baker (1995), J. Membr. Sci. 107:1–21 [VERIFIED — External]

---

## 2.9 Donnan Electroneutrality Correction for NF (Lines 353–378)

Applied only when `is_nf = True` AND feed Cl > 0.

$$\Sigma_{cat} = \frac{Ca\cdot2 + Mg\cdot2 + Na + K + Ba\cdot2 + Sr\cdot2 + NH_4 + Fe\cdot2 + Mn\cdot2 + Al\cdot3}{MW_i}\,\text{meq/L}$$

$$\Sigma_{an} = \frac{SO_4\cdot2 + HCO_3 + NO_3 + F + PO_4\cdot3}{MW_i}\,\text{meq/L}$$

$$C_{p,Cl} = \max\!\left(0,\,(\Sigma_{cat}-\Sigma_{an})\times35.45\right)\,\text{mg/L}$$

Physical cap: $C_{p,Cl} \leq 1.05\,C_{f,Cl}$

**Source:** [INTERNAL METHOD — based on Donnan (1911)]

---

## 2.10 `simulate_system` — Topology, Pumps & SEC (Lines 546–656)

**Topology:**
- Each stage: $N_{vessels}$ parallel vessels receiving $Q_{stage}/N_{vessels}$ each
- Within a vessel: elements in series; concentrate of element $e$ → feed of element $e+1$
- Results scaled by vessel count for stage totals

**Inter-stage booster pump:**
$$\Delta P_{boost} = \max(0,\,\pi_{conc} + NDP_{avg,stage} + 0.5 - P_{stage\_exit})\,\text{bar}$$
$$P_{boost,kW} = \frac{Q_{conc} \times \Delta P_{boost}}{36.0 \times 0.75}$$

**HP pump and Specific Energy Consumption:**
$$P_{HP,kW} = \frac{Q_{feed} \times P_{feed}}{36.0 \times 0.80}$$
$$\boxed{SEC = \frac{P_{HP} + P_{boost,total}}{Q_{perm}}\,\text{kWh/m}^3}$$

$\eta_{HP} = 0.80$, $\eta_{boost} = 0.75$ [INTERNAL METHOD — design assumptions]

---

## 2.11 Change / Validation History

| Issue | Fix |
|---|---|
| CP divergence at low crossflow | `beta_cap` = 1.25 introduced |
| Iteration oscillation at high flux | Damping w=0.30 applied |
| φ=1.0 for all salinity | Piecewise φ added for seawater range |
| Sh variant divergence | `calc_engine` uses `0.04·Re^0.75·Sc^0.33`; `physics_aging_engine` uses `0.065·Re^0.875·Sc^0.25` — intentional separate calibrations |

---

# 3. `system_engine.py` — System Orchestration & Economics

**File:** `backend/system_engine.py` | 993 lines | 47,620 bytes

## 3.1 Module Function: `_compute_nf_concentrate_scaling`

**Davies equation for activity coefficients (A=0.509 at 25°C):**
$$\log\gamma(z) = -0.509\,z^2\!\left(\frac{\sqrt{I}}{1+\sqrt{I}} - 0.3I\right)$$

**Ionic strength:**
$$I = 0.5\sum_i \frac{C_i}{MW_i \times 1000} \times z_i^2\,\text{mol/L}$$

**Source:** Davies (1962), Ion Association [VERIFIED — External]. Valid to I ≈ 0.5 M.

**Scalant Saturation Indices:**

| Scalant | $K_{sp}$ | Ion Product |
|---|---|---|
| CaSO₄ (Gypsum) | 4.93×10⁻⁵ | $[Ca][SO_4]\,\gamma(2)^2$ |
| BaSO₄ (Barite) | 1.08×10⁻¹⁰ | $[Ba][SO_4]\,\gamma(2)^2$ |
| SrSO₄ (Celestite) | 3.44×10⁻⁷ | $[Sr][SO_4]\,\gamma(2)^2$ |
| CaF₂ (Fluorite) | 3.45×10⁻¹¹ | $[Ca][F]^2\,\gamma(2)\,\gamma(1)^2$ |

$$SI = \log_{10}(IP/K_{sp})$$

**SiO₂ amorphous solubility:**
$$S_{SiO_2} = 100.0 + \max(0,\,T_{°C}-25)\times0.5\,\text{mg/L}$$

[INTERNAL METHOD — linear T-correction]

**Langelier Saturation Index:**
$$pH_s = (pK_2 - pK_{sp}) - \log[Ca] - \log[HCO_3] - \log\gamma(2) - \log\gamma(1)$$
$$LSI = pH_{feed} - pH_s$$

$pK_2 = 10.33$, $pK_{sp} = 8.48$ (25°C). **Source:** Langelier (1936), J. AWWA [VERIFIED — External]

---

## 3.2 `calculate_system` — Bisection Pressure Solver

**Osmotic pressure estimate (seed):**
$$\pi_{est} = \frac{\sum_i C_i}{1000} \times 0.7\,\text{bar} \quad (\approx 7\,\text{bar per 10,000 mg/L TDS})$$

**Bisection:**
- $P_{low} = \max(1.0,\,\pi_{est}-5)$, $P_{high} = \max(120,\,\pi_{est}+60)$
- 25 iterations; tolerance 0.005 (0.5% on recovery fraction)
- Each iteration: full `simulate_system` call → compare recovery to target

**NF Feed Quality Hard-Stop Thresholds:**

| Parameter | CRITICAL | WARNING |
|---|---|---|
| TDS (mg/L) | > 8,000 | 5,000–8,000 |
| SDI₁₅ | > 5 | > 3 |
| Fe (mg/L) | > 0.3 | > 0.05 |
| Free Cl₂ (ppm) | > 0.1 | > 0.05 |
| TOC (mg/L) | > 10 | > 3 |
| pH | < 4 | < 6 or > 9 |
| Feed pressure | > 41 bar | — (hard stop NF-W-HYD-10) |

---

## 3.3 Economics

**Membrane element price (INR):**

| Membrane | Price |
|---|---|
| NF | 19,200 |
| SWRO or rejection ≥ 99.5% | 30,240 |
| BWRO (default) | 26,880 |

**CAPEX:**
$$CAPEX = C_{equip}(1 + f_{IC})(1 + f_{cont})$$

$f_{IC} = 0.15$ (instrumentation & civil), $f_{cont} = 0.10$ (contingency)

**Capital Recovery Factor:**
$$CRF = \frac{d(1+d)^n}{(1+d)^n - 1}, \quad d=0.10,\;n=20\,\text{yr}$$

**OPEX — RO:**
$$OPEX_{RO} = E_{RO,pa} + \frac{C_{memb}}{5}\quad (5\text{-yr membrane life})$$

**OPEX — UF:**
$$OPEX_{UF} = E_{UF,pa} + \frac{C_{UF}}{7} + \underbrace{0.007\,Q_{UF}\,h_{pa}\times30\,\text{INR/kg}}_{\text{CEB chemical}}$$

**Cost per KL:**
$$\text{Cost/KL} = \frac{CAPEX \times CRF + OPEX_{pa}}{Q_{perm} \times 0.90 \times 8760}\,\text{INR/KL}$$

**Source:** CRF: standard engineering economics [VERIFIED — External]. INR unit costs: [INTERNAL METHOD]

---

## 3.4 `calculate_system_with_recycle`

**Blended feed:**
$$C_{blend,i} = \frac{C_{fresh,i}\,Q_{fresh} + C_{recycle,i}\,Q_{recycle}}{Q_{fresh}+Q_{recycle}}$$

Convergence: $\delta < 0.002$; max 15 iterations.

**Effective recovery:**
$$R_{eff} = Q_{perm}/Q_{fresh\_feed}$$

---

## 3.5 `simulate_two_pass_system`

**Pass 2 auto-sizing (Lines 794–814):**

The Pass 2 membrane model is read from `pass2_cfg["membrane"]`, then its `active_area_m2` is fetched directly from `MembraneDatabase`:

```python
p2_mem_model = pass2_cfg.get("membrane", "BW30-400")
p2_membrane  = MembraneDatabase.get_ro_membrane(p2_mem_model)
elem_area_m2 = p2_membrane.get("active_area_m2", 37.0) if p2_membrane else 37.0
```

Fallback is 37.0 m² only if the DB lookup fails.

$$\text{perm per elem} = \frac{A_{elem}\,[\text{m}^2] \times 20\,\text{LMH}}{1000}\,\text{m}^3/\text{h}$$

$$n_{elem,min} = \max\!\left(1,\,\left\lfloor\frac{Q_{P1}\times R_{P2,target}}{\text{perm per elem}}\right\rfloor + 1\right)$$

$$n_{vessels,min} = \max\!\left(1,\,\left\lfloor\frac{n_{elem,min}}{n_{elem/vessel}}\right\rfloor + 1\right)$$

If user-specified vessel count < $n_{vessels,min}$, vessels are scaled proportionally across stages. If user count ≥ minimum, user config is used as-is.

**2-Pass SEC:**
$$SEC_{2P} = \frac{P1_{kW} + P2_{kW}}{Q_{P2,perm}}\,\text{kWh/m}^3$$

---

# 4. `physics_aging_engine.py` — Multi-Year Physics Projection

**File:** `backend/physics_aging_engine.py` | 1,702 lines | 83,432 bytes
**Spec:** PACE-FEAT-MPP-002 Rev-A

## 4.1 Overview

Five coupled fouling sub-models advanced monthly via numerical integration, anchored to Year 0 by a bisection calibration of A₀, and reported as ASTM D4516-19a normalised metrics.

**Key structural constants:**
- NZ = 10 axial segments per element
- DT_H = 730 h per timestep (≈1 month)
- One representative vessel per stage; results generalised across all vessels in that stage

---

## 4.2 Calibrated Physics Parameters (Default Values, Lines 39–161)

### Sub-model I — Cake/Colloid Filtration

| Parameter | Symbol | Default Value | Units |
|---|---|---|---|
| Deposition rate | $K_d$ | 3.0×10⁻⁶ | s/m |
| Removal rate | $K_{rem}$ | 5.0×10⁻⁷ | m²/(Pa·s) |
| Bulk particle conc (from SDI) | $C_b$ | SDI/300 × 0.05 | kg/m³ |
| Specific cake resistance (ref TMP) | $\alpha_0$ | 5.0×10¹¹ | m/kg |
| Cake compressibility exponent | $s_c$ | 0.30 | — |
| Cake porosity | $\varepsilon_{cake}$ | 0.40 | — |
| Particle density | $\rho_p$ | 1,500 | kg/m³ |
| Particle diameter | $d_p$ | 1.0×10⁻⁷ | m |
| Reference TMP | $TMP_{ref}$ | 10.0 | bar |

### Sub-model II — Biofouling

| Parameter | Symbol | Default Value | Units | Source |
|---|---|---|---|---|
| Max specific growth rate | $\mu_{max}$ | 0.003 | h⁻¹ | Calibrated: Bereschenko 2010, Vrouwenvelder 2010 |
| Biodegradable DOC | $BDOC$ | 0.4 × TOC | kg/m³ | — |
| Monod half-saturation | $K_s$ | 0.8 | mg/L | Oligotrophic RO community |
| Decay/detachment rate | $b_d$ | 5.0×10⁻⁴ | h⁻¹ | — |
| Seeding flux | $J_{b,seed}$ | 5.0×10⁻¹² | m/h | — |
| EPS fibre diameter | $d_{p,EPS}$ | 8.0×10⁻⁸ | m | — |
| Biofilm porosity | $\varepsilon_{bf}$ | 0.70 | — | — |
| Biofilm tortuosity | $\tau_{bf}$ | 2.0 | — | — |
| Biofilm carrying capacity | $L_{b,max}$ | 1.5×10⁻⁴ | m | 150 µm; Vrouwenvelder 2010 CLSM |
| Activation energy | $E_{a,bio}$ | 45,000 | J/mol | — |

### Sub-model III — Scaling (CNT, Calcite defaults)

| Parameter | Symbol | Default Value | Units |
|---|---|---|---|
| Solid-liquid interfacial energy | $\gamma_{sl}$ | 0.034 | J/m² |
| Contact angle | $\theta$ | 40° | — |
| Nucleation pre-exponential | $A_{ind}$ | 1.0×10³ | s |
| Calcite molar volume | $V_m$ | 3.69×10⁻⁵ | m³/mol |
| Crystal growth rate | $k_{g,calcite}$ | 3.5×10⁻¹³ | m/s (driving force $(S-1)^2$) |
| Growth order | $n_s$ | 2.0 | — |
| Specific scale resistance | $\alpha_{scale}$ | 2.0×10¹³ | m/kg |
| Calcite density | $\rho_{calcite}$ | 2,710 | kg/m³ |

### Sub-model IV — NOM Adsorption

| Parameter | Symbol | Default | Units |
|---|---|---|---|
| Max NOM loading | $q_{max}$ | 5.0×10⁻⁴ | kg/m² |
| Langmuir constant | $K_L$ | 10.0 | m³/kg |
| Adsorption rate | $k_{ads}$ | 3.0×10⁻⁵ | s⁻¹ |
| Reference shear stress | $\tau_{w,ref}$ | 0.5 | Pa |
| Specific NOM resistance | $r_{NOM}$ | 8.0×10¹⁰ | m/kg |

### Sub-model V — Compaction (Kelvin-Voigt)

| Parameter | Symbol | Default | Units |
|---|---|---|---|
| Elastic modulus | $E_m$ | 2.0×10⁸ | Pa |
| Creep retardation time | $\tau_c$ | 500.0 | h |
| Viscous creep coefficient | $\eta_v$ | 1.0×10¹² | Pa·h |
| Stress fraction | $f_{stress}$ | 0.50 | — |

### Salt Permeability Degradation (Sub-model VI / C6.1)

| Parameter | Symbol | Default | Units |
|---|---|---|---|
| Chemical degradation rate | $k_{B,chem}$ | 0.015 | yr⁻¹ (1.5%/yr) |
| Activation energy | $E_{a,B}$ | 60,000 | J/mol |
| Reference temperature | $T_{ref,B}$ | 298.15 | K |

**Chlorine-damage rate (Lines 396–402):**
$$k_{B,chem} = \underbrace{0.03 \times \frac{0.1}{max\_cl}}_{\text{baseline hydrolysis}} + \underbrace{Cl_{actual} \times \frac{1.0}{max\_cl}}_{\text{oxidative attack}}$$

---

## 4.3 Helper Functions (Lines 168–196)

$$\mu_w(T) = 10^{-3}\exp\!\left(\frac{1808.0}{T_K} - 6.354\right)\,\text{Pa·s}$$

$$D_s(T) = 1.6\times10^{-9} \times \frac{T_K}{298.15} \times \frac{8.9\times10^{-4}}{\mu_w(T)}\,\text{m}^2/\text{s}$$

$$\text{Arrhenius}(E_a,T,T_{ref}) = \exp\!\left[\frac{E_a}{R}\left(\frac{1}{T_{ref}}-\frac{1}{T}\right)\right]$$

**RK4 step (generic, Line 189):**
$$y_{n+1} = y_n + \frac{\Delta t}{6}(k_1 + 2k_2 + 2k_3 + k_4)$$

---

## 4.4 A₀ Calibration (Lines 481–504)

The membrane catalog A₀ is adjusted via 20-iteration bisection to reproduce the exact Year 0 baseline pressure $P_0$:

$$A_{lo} = 0.2\,A_{0,catalog},\quad A_{hi} = 5.0\,A_{0,catalog}$$

At each step: run `ROEngine.simulate_system` at $P_0$ with $A_{mid}$; if recovery $< r_0$ → raise $A_{lo}$, else lower $A_{hi}$.

This ensures Year 0 NPF = 1.0 exactly.

---

## 4.5 ODE State Variables (per element, per axial segment)

| Variable | Symbol | Units | Mechanism |
|---|---|---|---|
| Cake mass | $m_c$ | kg/m² | Sub-model I |
| Biofilm thickness | $L_b$ | m | Sub-model II |
| Scale layer thickness | $\delta_s$ | m | Sub-model III |
| NOM loading | $q$ | kg/m² | Sub-model IV |
| SI accumulation time | $t_{SI}$ | h | Sub-model III |
| Compaction strain | $\varepsilon_{comp}$ | — | Sub-model V (element-uniform) |
| Relative B factor | $B_{IRR}$ | — | Sub-model VI (element-uniform) |

---

## 4.6 Sub-model I: Cake Filtration ODE (Lines 1095–1111)

**ODE (net deposition rate):**
$$\frac{dm_c}{dt} = K_d \cdot J_w \cdot C_b - K_{rem} \cdot \tau_w \cdot m_c\,\text{[kg/(m}^2\text{·s)]}$$

**Compressible cake specific resistance:**
$$\alpha = \alpha_0 \times \left(\frac{TMP}{TMP_{ref}}\right)^{s_c}$$

**Integration method:** Analytical exact (avoids Euler instability):
$$m_{c,ss} = \frac{K_d J_w C_b}{K_{rem}\,\tau_w}, \quad m_c^{new} = m_{c,ss} + (m_c - m_{c,ss})\,e^{-K_{rem}\,\tau_w\,\Delta t}$$

**Cake resistance:**
$$\boxed{R_c = \alpha \cdot m_c\,\text{[m}^{-1}\text{]}}$$

**Source:** Hermia (1982); Tung & Mukherjee (1984) [VERIFIED — External]; Analytical integration: stability measure [INTERNAL METHOD]

---

## 4.7 Sub-model II: Biofouling ODE (Lines 1113–1142)

**Logistic Monod growth ODE:**
$$\frac{dL_b}{dt} = \underbrace{\mu_{max} \cdot \text{Arr}(E_{a,bio}) \cdot \frac{BDOC}{K_s+BDOC}}_{\mu_{eff}} \cdot L_b \cdot \underbrace{\left(1-\frac{L_b}{L_{b,max}}\right)}_{\text{logistic}} + J_{b,seed} - b_d \cdot L_b$$

The logistic term $(1-L_b/L_{b,max})$ prevents unbounded exponential growth (without it, biofilm would reach cm scale by Year 3, which is unphysical).

$L_{b,max} = 150\,\mu\text{m}$ (CLSM autopsy data: Vrouwenvelder 2010)

**Integration method:** Sub-stepped Euler with $n_{steps}=73$ substeps per monthly timestep ($\Delta t_{bio} = 730/73 \approx 10\,\text{h}$).

**Biofilm resistance (Kozeny–Carman for fibrous EPS matrix):**
$$\boxed{R_b = \frac{180\,(1-\varepsilon_{bf})^2\,\tau_{bf}\,L_b}{d_{p,EPS}^2\,\varepsilon_{bf}^3}}$$

Threshold: $R_b = 0$ if $L_b < L_{b,min} = 1\,\mu\text{m}$.

**Source:** Monod kinetics: Monod (1949) [VERIFIED — External]; Logistic growth: van Loosdrecht (1995), Vrouwenvelder (2010) [VERIFIED — External]; Kozeny–Carman: Blake (1922) [VERIFIED — External]

---

## 4.8 Sub-model III: Scaling via Classical Nucleation Theory (Lines 1144–1229)

**Wall supersaturation:**
$$CP_{wall} = \exp\!\left(\frac{J_w\,[\text{m/h}]}{k_M\,[\text{m/h}]}\right)$$
$$SI_{wall} = SI_{bulk,calcite} + \log_{10}(CP_{wall})$$

Only drives scaling when $SI_{wall} > 0$.

**Heterogeneous nucleation correction (CNT):**
$$f_{het} = 0.25(2+\cos\theta)(1-\cos\theta)^2, \quad \theta=40°$$

**Gibbs free energy barrier:**
$$S = 10^{SI_{wall}}, \quad \ln S = SI_{wall} \times \ln 10$$
$$\Delta G^*/kT = f_{het} \times \frac{4}{3\,(\ln S)^2}$$

**Induction time:**
$$t_{ind} = A_{ind} \times \exp(\Delta G^*/kT) \times t_{ind,factor}/3600\,\text{h}$$

$t_{ind,factor} = 10$ when antiscalant is dosed (10× delay); = 1 otherwise.

If membrane datasheet saturation limits exceeded: $t_{ind} = 0$ (instant nucleation).

**Crystal growth after induction (Nielsen 1984 / Hasson 1998 parabolic rate):**
$$\frac{d\delta_s}{dt} = k_{g,calcite} \times (S-1)^{n_s} \times f_{suppression}$$

$f_{suppression} = 0.20$ with antiscalant (80% growth rate reduction), = 1.0 without.

**Scale resistance:**
$$\boxed{R_s = \alpha_{scale} \times \rho_{calcite} \times \delta_s\,\text{[m}^{-1}\text{]}}$$

**Integration:** Forward Euler on $\delta_s$; $t_{SI}$ accumulates +1 h per timestep.

**Source:** Classical Nucleation Theory: Turnbull & Fisher (1949) [VERIFIED — External]; Crystal growth: Nielsen (1984), Hasson et al. (1998) [VERIFIED — External]

---

## 4.9 Sub-model IV: NOM Adsorption (Lines 1231–1248)

**Langmuir-type NOM wall concentration:**
$$C_{nom,wall} = C_{nom,bulk} \times \exp\!\left(\frac{J_w}{k_M}\right)$$

**Langmuir equilibrium loading:**
$$q_{eq} = q_{max} \times \frac{K_L\,C_{nom,wall}}{1+K_L\,C_{nom,wall}}$$

**ODE with shear desorption modifier:**
$$\frac{dq}{dt} = k_{ads} \times (q_{eq}-q) \times \underbrace{\min\!\left(1,\,\frac{\tau_{w,ref}}{\tau_w}\right)}_{\text{shear modifier}}$$

$C_{nom,bulk} = 0.6 \times TOC\,[\text{mg/L}] / 10^6\,\text{kg/m}^3$

**Integration:** Analytical exact (same form as cake):
$$q^{new} = q_{eq} + (q-q_{eq})\,e^{-k_{eff}\,\Delta t}, \quad q \leq q_{max}$$

**NOM resistance:**
$$\boxed{R_n = r_{NOM} \times q\,\text{[m}^{-1}\text{]}}$$

**Source:** Langmuir (1918) [VERIFIED — External]; Intermediate blocking + NOM fouling: Hermia (1982) [VERIFIED — External]

---

## 4.10 Sub-model V: Membrane Compaction (Lines 665–671)

**Kelvin-Voigt viscoelastic creep (incremental):**
$$\sigma_{stress} = TMP_{Pa} \times f_{stress}$$
$$\varepsilon_{\infty} = \frac{\sigma_{stress}}{E_m}$$
$$\varepsilon_{comp}^{new} = \varepsilon_{comp} + (\varepsilon_\infty - \varepsilon_{comp})\left(1-e^{-\Delta t/\tau_c}\right)$$

**Compaction resistance:**
$$\boxed{R_{comp} = \varepsilon_{comp} \times R_{m,base}\,\text{[m}^{-1}\text{]}}$$

**Effective A due to compaction:**
$$A_{eff} = A_0 \times (1 - \varepsilon_{comp})$$

**Source:** Kelvin-Voigt creep model: standard viscoelastic mechanics [VERIFIED — External]

---

## 4.11 Sub-model VI: Salt Permeability Degradation (Lines 689–693)

**Monthly B factor update:**
$$k_{B,eff} = k_{B,chem} \times \text{Arr}(E_{a,B},T_K,T_{ref,B}) / 12$$
$$B_{IRR}^{new} = \min(3.0,\,B_{IRR} \times (1 + k_{B,eff}))$$

$B_{IRR}$ capped at 3.0 (300% of initial — physical limit).

---

## 4.12 Resistance-in-Series Framework

Total resistance at each segment:
$$R_{total} = R_m + R_c + R_b + R_s + R_n + R_{comp}$$

Local flux from Darcy's law:
$$J_w = \frac{TMP_{Pa}}{\mu_T \times R_{total}}\,\text{m/s}, \quad \text{capped at } 5\times10^{-5}\,\text{m/s}$$

**Effective A per element for year-end bisection:**
$$A_{eff} = \frac{A_0}{1 + R_{f,ei}/R_{m,base}} \times (1-\varepsilon_{comp,ei}), \quad \text{floor: }0.1\,A_0$$

$$B_{eff} = B_0 \times B_{IRR,ei}$$

---

## 4.13 Concentration-Enhanced Osmotic Pressure (CEOP) — Year-End

Used in year-end FRI and `aged_params` computation:

$$R_{mt,bf} = \frac{L_{b,avg}\,\tau_{bf}}{D_s\,\varepsilon_{bf}}, \quad R_{mt,cake} = \frac{L_{c,avg}\,\tau_{cake}}{D_s\,\varepsilon_{cake}}$$

$$CP_{fouled} = \exp\!\left(\min\!\left[J_{w,avg}\left(\frac{1}{k_M} + R_{mt,bf} + R_{mt,cake}\right),\,15\right]\right)$$

$$\Delta\pi_{CEOP} = \pi_{feed}\,(CP_{fouled} - CP_{clean}), \quad R_{CEOP} = \frac{\Delta\pi_{CEOP}}{\mu_T\,J_{w,avg}}$$

Total fouling resistance per element:
$$R_{f,ei} = R_c + R_b + R_s + R_n + R_{comp} + R_{CEOP}$$

**Source:** CEOP concept: Hoek & Elimelech (2003), Environ. Sci. Technol. [VERIFIED — External]

---

## 4.14 Fouling Resistance Index (FRI)

$$FRI_{ei} = \frac{R_{f,ei} - R_{comp,ei}}{R_{m,base} + R_{f,ei} - R_{comp,ei}}$$

(Compaction excluded from reversible fouling component.)

$$FRI_{sys} = \frac{1}{N_{elem}}\sum_{ei} FRI_{ei}$$

---

## 4.15 ASTM D4516-19a Normalised Metrics (Lines 1526–1576)

**NPF (Normalised Permeate Flow) — constant-flow bisection mode:**
$$\boxed{NPF = \frac{Q_{p,y}}{Q_{p,0}} \times \underbrace{TCF_{ratio}}_{=1,\;\text{same T}} \times \frac{NDP_0}{NDP_y}}$$

Since bisection forces $Q_{p,y} \approx Q_{p,0}$, the NDP ratio carries the signal:
$$NDP_y = \frac{1}{N_{elem}}\sum_e NDP_e\,\text{(from year-end simulation)}$$

**NSP (Normalised Salt Passage) — constant-flow mode:**
$$NSP = \frac{SP_y}{SP_0} = \frac{TDS_y}{TDS_0}$$

where $TDS_y = TDS_{y,raw} \times B_{IRR,avg}$ (explicit B-degradation scaling applied).

**NSP (fouling component only):**
$$NSP_{fouling} = NSP_{total}/B_{IRR,avg}$$

**Wall-level SI tracking (year-end):**
$$kM_{avg} = 5\times10^{-6}\times(1 - 0.5\,FRI_{sys})\,\text{m/s}$$
$$CP_{avg} = \exp(J_{w,avg}/kM_{avg}), \quad cp\_log_{10} = \log_{10}(CP_{avg})$$
$$SI_{X,wall} = SI_{X,bulk} + cp\_log_{10}$$

**Source:** ASTM D4516-19a [VERIFIED — External: Standard Practice for Standardizing RO Performance Data]

---

## 4.16 Year-End Bisection Pressure Solver (Lines 1470–1510)

$$P_{lo} = \max(0.5\,P_0,\,2.0), \quad P_{hi} = 2.5\,P_0$$

25 iterations; tolerance $|R_{mid} - R_{target}| < 10^{-5}$.

On convergence failure: fallback snapshot using $FRI_{sys}$ proportional degradation.

---

## 4.17 CIP Kinetics (Lines 1289–1350)

**Maturation penalty** (older biofilm harder to remove):
$$\eta_{age} = 0.6 + 0.4\,e^{-t_{elapsed}/15\,\text{months}}$$

**Sequential two-step protocol:**

Step 1 — Alkaline:
$$OH^- = 10^{-(14-pH_{alk})}\,\text{M}$$
$$k_{Lb,alk} = k_{d,bio} \times \text{Arr}(E_{a,bio\_rem}) \times OH^-$$
$$L_b \leftarrow L_b \times \exp(-k_{Lb,alk}\,\eta_{age}\,t_{alk}\times3600)$$

Step 2 — Acid:
$$H^+ = 10^{-pH_{acid}}\,\text{M}$$
$$k_{ds,acid} = k_{d,acid} \times \text{Arr}(E_{a,dis}) \times H^+$$
$$\delta_s \leftarrow \delta_s \times \exp(-k_{ds,acid}\,\eta_{age}\,t_{acid}\times3600)$$

**Affinity matrix (removal priorities):**

| Foulant | Alkaline removes | Acid removes |
|---|---|---|
| $L_b$ (biofilm) | Primary (k_Lb_alk) | 1% of alkaline rate |
| $q$ (NOM) | Primary (k_q_alk) | 20% of alkaline rate |
| $\delta_s$ (scale) | 1% of acid rate | Primary (k_ds_acid) |
| $m_c$ (cake) | 50% of chelant rate | k_d_coll × chelant_conc |

**CIP mode — scheduled only (Lines 703–728):**

Auto-CIP (condition-triggered) has been **removed from the codebase** (Line 774: `# Auto-CIP feature removed per user request`). The threshold constants (`NPF_cip_trigger = 0.90`, `NDP_ratio_cip_trigger = 1.15`, `NSP_ratio_cip_trigger = 1.10`, `FRI_cip_trigger = 0.60`) remain in `DEFAULT_PHYSICS_PARAMS` but are **never evaluated** during a run.

The only CIP that executes is **scheduled CIP** — triggered every `interval_months` months as set by the user:

```python
scheduled_cip = (self.p.get("interval_months", 0) > 0 and
                 elapsed_months % self.p["interval_months"] == 0)
```

If a scheduled CIP falls on the **last month of the year** (month 12), it is **deferred** until after the year-end snapshot is taken, so the snapshot captures the true fouled state before cleaning.

**Replacement triggers:**

| Metric | Threshold |
|---|---|
| NPF < 0.70 | 30% flux decline |
| SEC increase > 50% | — |
| Operating time > 43,800 h | (5 years) |

---

## 4.18 Spatial Transport Model `_spatial_transport` (Lines 953–1089)

NZ-segment axial model per element:

**Sherwood number (Schock–Miquel variant B):**
$$Sh = 0.065 \times Re^{0.875} \times Sc^{0.25}$$

*Note: differs from `calc_engine.py` which uses $Sh = 0.04\,Re^{0.75}\,Sc^{0.33}$ — these are two separate calibrations of the Schock–Miquel family. The `physics_aging_engine` variant matches higher-Re conditions.*

**Local crossflow velocity (axial decay):**
$$v_{cross,zi} = \frac{Q_{in}\,(1 - 0.15\,zi/NZ)}{A_{cross}}\,\text{m/s}$$

**Wall shear stress:**
$$f_f = 6.23\,Re^{-0.30}, \quad \tau_w = 0.5\,f_f\,\rho_w\,v_{cross}^2\,\text{Pa}$$

**Approximate element pressure drop per element:** 0.15 bar (hardcoded in spatial transport; more accurate ΔP uses Darcy–Weisbach in `calc_engine.py`).

---

## 4.19 Monthly Profile Interpolation (Lines 864–909)

Monthly pressure is linearly interpolated between year-end bisection results:
$$P_{m} = P_{start} + (P_{end} - P_{start}) \times \frac{m_{in\_year}+1}{12}$$

$$NPF_{m} = NPF_{start} + (NPF_{end} - NPF_{start}) \times \frac{m_{in\_year}+1}{12}$$

Monthly NSP approximated as $B_{IRR,avg}$ for that month (no intra-year bisection).

---

# 5. `conditioning.py` — Interstage Chemical Conditioning

**File:** `backend/conditioning.py` | 58 lines | 2,496 bytes

## 5.1 `compute_chemical_dose` (Lines 9–23)

Dead-band: $|\Delta pH| < 0.1$ → dose = 0

$$\text{dose} = |\Delta pH| \times 2.5\,\text{mg/L}\quad (\Delta pH = pH_{target} - pH_{current})$$

Condition: NaOH for $\Delta pH > 0$; H₂SO₄ or HCl for $\Delta pH < 0$; wrong direction → 0.

[INTERNAL METHOD — 2.5 mg/L/pH unit empirical constant, no alkalinity correction]

## 5.2 `apply_conditioning` (Lines 25–57)

**CO₂ degassing:** $C_{CO_2} = 0$ (binary 100% stripping — no partial model)

**Stoichiometric ion additions:**

| Chemical | Ion | Equation |
|---|---|---|
| NaOH | Na⁺ | $\Delta C_{Na} = \text{dose} \times 22.99/40.00$ |
| H₂SO₄ | SO₄²⁻ | $\Delta C_{SO_4} = \text{dose} \times 96.06/98.08$ |
| HCl | Cl⁻ | $\Delta C_{Cl} = \text{dose} \times 35.45/36.46$ |

pH set directly to $pH_{target}$ (no equilibrium calculation).

---

# 6. `membrane_recommender.py` — Membrane Scoring Engine

**File:** `backend/membrane_recommender.py` | 238 lines | 11,012 bytes

## 6.1 Scoring Weights

| Criterion | Weight | Description |
|---|---|---|
| Rejection | **30 pts** | Permeate TDS vs target |
| Hydraulic | **20 pts** | Feed/concentrate flow limits |
| Energy | **30 pts** | Specific Energy Consumption |
| Envelope | **20 pts** | Pressure limits & CP |

## 6.2 Criterion Formulas

**Rejection (30 pts):**
$$\text{score} = \begin{cases}30 & TDS_{perm} \leq TDS_{target}\\ \max(0,\,30-\min(30,\,(TDS_{perm}-TDS_{target})\times0.5)) & \text{otherwise}\end{cases}$$
DQ if gap > 50 mg/L or score = 0.

**Energy (30 pts):**
$$\text{score} = \max(0,\,\min(30,\,30-(SEC-1.0)\times8))$$

Zero at SEC ≥ 4.75 kWh/m³; max at SEC ≤ 1.0 kWh/m³.

**Hydraulic (20 pts):**
- Vessel feed > `max_feed_flow_m3h`: −10 pts + DQ
- Vessel concentrate < `min_concentrate_flow_m3h`: −5 pts

**Envelope (20 pts):**
- Feed pressure > `max_pressure_bar`: score=0, DQ
- Feed pressure > 90% of max: −5 pts
- $\beta_{max} > 1.20$: $-\min(10,\,(\beta_{max}-1.20)\times50)$ pts
- Source type SEAWATER + non-SWRO membrane: DQ
- Feed TDS > 20,000 + BWRO: DQ

**Sorting:** Non-DQ first, then by total score descending.

---

# 7. `server_impl.py` — API Layer & Chemistry

**File:** `backend/server_impl.py` | 1,185 lines | 49,956 bytes

## 7.1 PHREEQC Scaling Endpoint (`/api/calculate-scaling`)

Creates PHREEQC solution with exact species notation:

| Ion | PHREEQC Field | Format |
|---|---|---|
| NH₄⁺ | `N(-3)` | `{value} as NH4` |
| SO₄²⁻ | `S(6)` | `{value} as SO4` |
| Alkalinity | `Alkalinity` | `{value} as CaCO3` |
| NO₃⁻ | `N(5)` | `{value} as NO3` |
| SiO₂ | `Si` | `{value} as SiO2` |
| PO₄³⁻ | `P` | `{value} as PO4` |

Returns SI for 13 mineral phases: Gypsum, Calcite, Aragonite, Barite, Celestite, Fluorite, Anhydrite, SiO₂(a), Fe(OH)₃(a), Al(OH)₃(a), Pyrolusite, Hydroxyapatite.

**Note:** `lsi = sol.si("Calcite")` — Calcite SI is the rigorous thermodynamic LSI.

**Source:** Parkhurst & Appelo (2013), USGS TM Book 6 Ch. A43 [VERIFIED — External]

---

## 7.2 Auto-Balance / Charge Balance Error (`/api/auto-balance`)

**Alkalinity input is in mg/L as CaCO₃:**
$$\text{alk\_meq} = \frac{\text{bicarbonate\_as\_CaCO}_3}{50.04}$$

**Carbonate split at pH 8.3:**
$$\text{fraction}_{CO_3} = \frac{10^{pH-10.3}}{1+10^{pH-10.3}}$$

(pKa₂ of carbonic acid = 10.3 at 25°C)

**Cation sum (meq/L):**
$$\Sigma_{cat} = \frac{Ca\cdot2}{40.08}+\frac{Mg\cdot2}{24.31}+\frac{Na}{22.99}+\frac{K}{39.10}+\frac{NH_4}{18.04}+\frac{Ba\cdot2}{137.33}+\frac{Sr\cdot2}{87.62}$$

**Anion sum (meq/L):**
$$\Sigma_{an} = \frac{Cl}{35.45}+\frac{SO_4\cdot2}{96.06}+\text{hco3\_meq}+\text{co3\_meq}\cdot2+\frac{NO_3}{62.00}+\frac{F}{19.00}+\frac{PO_4\cdot3}{94.97}$$

**Charge Balance Error:**
$$CBE_{meq} = \Sigma_{cat} - \Sigma_{an}$$
$$CBE\% = \frac{CBE_{meq}}{\max(\Sigma_{cat}+\Sigma_{an},\,0.1)}\times100$$

**Auto-correction** when $|CBE\%| > 2.0$:
- $CBE_{meq} > 0$ (excess cations) → inject Cl⁻: $\Delta C_{Cl} = CBE_{meq}\times35.45$ mg/L
- $CBE_{meq} < 0$ (excess anions) → inject Na⁺: $\Delta C_{Na} = |CBE_{meq}|\times22.99$ mg/L

**Source:** CBE formula: Freeze & Cherry (1979) [VERIFIED — External]. Na/Cl injection convention: [INTERNAL METHOD — industry standard]

---

## 7.3 Physics Projection Core `_run_projection_core` (Lines 688–1017)

Shared by both `/api/simulate-aging` and `/api/calculate-system-physics`.

**Recycle feed ion resolution (three-level fallback):**

1. Solver result: `baseline["recycle"]["blended_feed_ions"]` (most accurate)
2. `baseline["feed_water_used"]` if TDS > fresh feed TDS
3. Analytical fallback:
$$CF = \frac{1}{\max(1-R_{frac},\,0.05)}, \quad C_{blend,i} = C_{fresh,i}\times\frac{Q_{fresh}\,TDS_{fresh}+Q_{recycle}\,CF\,TDS_{fresh}}{Q_{blend}\,TDS_{fresh}}$$

**SDI-from-TSS heuristic (when SDI not supplied):**
$$SDI_{15} = \min(\text{TSS}\times0.5,\,6.0)$$
[INTERNAL METHOD — empirical approximation]

**Year 0 snapshot correction:** After physics engine returns, snapshot[0] values overwritten with true system-level metrics (vital for 2P-RO where Pass 1 pressure ≠ overall system pressure).

**CIP interval conversion:**
$$\text{months} = \begin{cases}0 & \text{(dynamic trigger)} \\ \max(1,\,\text{round}(days/30)) & \text{otherwise}\end{cases}$$

---

# 8. Traceability Matrix

| Equation | Module | Lines | Tier | Citation |
|---|---|---|---|---|
| Van't Hoff osmotic pressure | calc_engine | 23–55 | External | Van't Hoff (1887) |
| Piecewise osmotic coefficient φ | calc_engine | 30–49 | Internal Method | Permionics calibration |
| TCF (U=2640/3020 K) | calc_engine | 57–70 | Internal Method | Based on DuPont FILMTEC |
| Andrade viscosity | calc_engine, physics_aging | 100, 168 | External | Standard empirical |
| Stokes–Einstein diffusivity | calc_engine, physics_aging | 129, 173 | External | Standard |
| Schock–Miquel Sh (calc_engine: 0.04·Re⁰·⁷⁵·Sc⁰·³³) | calc_engine | 135 | External | Schock & Miquel (1987) |
| Schock–Miquel Sh (physics_aging: 0.065·Re⁰·⁸⁷⁵·Sc⁰·²⁵) | physics_aging | 1030 | External | Schock & Miquel (1987) variant |
| Schock–Miquel friction factor (λ=6.23·Re⁻⁰·³⁰) | calc_engine, physics_aging | 178, 1056 | External | Schock & Miquel (1987) |
| Spiegler–Kedem–Katchalsky transport | calc_engine | 250–295 | External | Spiegler & Kedem (1966) |
| Solution-Diffusion model | calc_engine | 302–330 | External | Wijmans & Baker (1995) |
| Donnan electroneutrality correction (NF) | calc_engine | 353–378 | Internal Method | Based on Donnan (1911) |
| HP pump SEC (η=0.80) | calc_engine, physics_aging | 656, 1522 | Internal Method | Engineering assumption |
| Booster pump (η=0.75) | calc_engine | 599 | Internal Method | Engineering assumption |
| Davies activity coefficients | system_engine | 13–133 | External | Davies (1962) |
| Ksp values (gypsum, barite, celestite, fluorite) | system_engine | ~50–90 | External | NIST databases |
| SiO₂ solubility T-correction | system_engine | ~100 | Internal Method | Permionics calibration |
| Langelier SI formula | system_engine, server_impl | ~110, 258 | External | Langelier (1936) |
| CRF formula | system_engine | ~430 | External | Standard engineering economics |
| Cake filtration ODE (Hermia-Tung) | physics_aging | 1095–1111 | External | Hermia (1982); Tung & Mukherjee (1984) |
| Analytical cake integration | physics_aging | 629–634 | Internal Method | Numerical stability |
| Biofilm logistic-Monod ODE | physics_aging | 1113–1142 | External | Monod (1949); van Loosdrecht (1995) |
| Kozeny–Carman biofilm resistance | physics_aging | 1261–1271 | External | Blake (1922) |
| Classical Nucleation Theory (scaling) | physics_aging | 1144–1229 | External | Turnbull & Fisher (1949) |
| Crystal growth rate (Nielsen/Hasson) | physics_aging | 1214–1228 | External | Nielsen (1984); Hasson et al. (1998) |
| Langmuir NOM adsorption ODE | physics_aging | 1231–1248 | External | Langmuir (1918) |
| Kelvin-Voigt compaction | physics_aging | 665–671 | External | Standard viscoelastic mechanics |
| CEOP resistance | physics_aging | 1420–1430 | External | Hoek & Elimelech (2003) |
| ASTM D4516-19a NPF | physics_aging | 1526–1553 | External | ASTM D4516-19a |
| ASTM D4516-19a NSP | physics_aging | 1564–1576 | External | ASTM D4516-19a |
| CIP kinetics (Arrhenius dissolution) | physics_aging | 1289–1350 | Internal Method | Calibrated to 95% removal target |
| PHREEQC speciation | server_impl | 229–267 | External | Parkhurst & Appelo (2013) |
| Charge Balance Error | server_impl | 332–334 | External | Freeze & Cherry (1979) |
| Carbonate alkalinity split | server_impl | 303–311 | External | Stumm & Morgan (1996) |
| Membrane scoring weights (30/20/30/20) | membrane_recommender | 12–15 | Internal Method | Permionics engineering judgment |
| Chemical dose (2.5 mg/L/pH unit) | conditioning | 9–23 | Internal Method | Permionics empirical |
| CO₂ degassing = 100% | conditioning | 40 | Internal Method | Simplifying assumption |
| UF module count (ceiling) | uf_engine | 46–47 | External | Standard sizing |
| UF TMP (Darcy's law) | uf_engine | 79 | External | Darcy (1856) |
| UF fouled TMP = 2× clean | uf_engine | 80 | Internal Method | Conservative approximation |
| UF viscosity correction (Andrade) | uf_engine | 21–23 | External | Andrade (1930) |
| UF backwash/FF water loss accounting | uf_engine | 57–69 | Internal Method | Permionics design practice |

---

# 9. `uf_engine.py` — UF System Sizing

**File:** `backend/uf_engine.py` | 142 lines | 6,247 bytes

## 9.1 Purpose

Sizes an Ultrafiltration pre-treatment system. Called by `SystemEngine.calculate_system()` whenever `"UF"` appears in the technology train string. Outputs net product flow to RO/NF feed.

## 9.2 `_viscosity_correction` (Lines 14–23)

Andrade viscosity ratio relative to 20°C reference:

$$\mu(T) = 10^{-3}\exp\!\left(\frac{1808.0}{T_K} - 6.354\right)\,\text{Pa·s}$$

$$VCF = \frac{\mu(T)}{\mu(20°C)}$$

**Source:** Andrade (1930) empirical relation [VERIFIED — External]

## 9.3 `simulate_uf` — All Equations (Lines 25–141)

### Inputs

| Parameter | Units | Notes |
|---|---|---|
| `gross_feed_flow_m3h` | m³/h | System intake flow |
| `temp_c` | °C | Feed temperature |
| `module_name` | — | MembraneDatabase key |
| `feed_turbidity` | NTU | Default 20 |
| `feed_tss` | mg/L | Default 30 |
| `feed_tds` | mg/L | Used for water quality report only; UF does not remove TDS |
| `feed_ph` | — | Default 7.3 |

### Step 1: Number of Modules (Lines 41–50)

Fetches `membrane_area_m2` and `design_flux_lmh` from `MembraneDatabase`.

$$n_{modules} = \left\lceil\frac{Q_{gross}\times1000}{J_{design}\times A_{module}}\right\rceil$$

Actual filtration flux (recalculated against ceiling-rounded module count):

$$J_{actual} = \frac{Q_{gross}\times1000}{n_{modules}\times A_{module}}\,\text{LMH}$$

### Step 2: Operating Cycle Water Losses (Lines 52–73)

Fixed filtration cycle time: $t_{filt} = 90$ min (hardcoded).

**Backwash volume per module per cycle:**
$$V_{BW,mod} = \frac{J_{BW}\times A_{module}\times t_{BW}}{3600\times1000}\,\text{m}^3$$

**Total backwash flow loss:**
$$Q_{BW,loss} = V_{BW,mod}\times n_{modules}\times\frac{60}{t_{filt}+t_{BW}}\,\text{m}^3/\text{h}$$

**Forward flush loss** (50% safety margin applied to module minimum FF flow):
$$Q_{FF,loss} = \underbrace{1.5\times Q_{FF,min}}_{\text{safety factor}}\times n_{modules}\times\frac{1\,\text{min}}{60}\times\frac{60}{t_{filt}+t_{BW}}\,\text{m}^3/\text{h}$$

**Net product flow and system recovery:**
$$Q_{net} = Q_{gross} - Q_{BW,loss} - Q_{FF,loss}$$
$$R_{UF} = \frac{Q_{net}}{Q_{gross}}\times100\,\%$$

### Step 3: TMP Calculations (Lines 75–88)

Temperature-corrected permeability:
$$L_{p,T} = \frac{L_{p,20}}{VCF(T)}$$

**Clean membrane TMP:**
$$TMP_{clean} = \frac{J_{actual}}{L_{p,T}}\,\text{bar}$$

**Fouled membrane TMP** [INTERNAL METHOD — conservative approximation]:
$$TMP_{fouled} = 2\times TMP_{clean}$$

TMP is also evaluated at $T_{min}=10°C$ and $T_{max}=35°C$ for warning checks.

### Step 4: Safety Limit Warnings (Lines 90–108)

| Check | Limit source | Status |
|---|---|---|
| Filtration flux > max | `max_filtration_flux_lmh` from DB | PASS/FAIL |
| Forward flush flow < min | `min_forward_flush_m3h` from DB | PASS/FAIL |
| Clean TMP at Tmin > max | `clean_tmp_max_bar` from DB | PASS/FAIL |
| Clean TMP at Tdesign > max | `clean_tmp_max_bar` from DB | PASS/FAIL |
| Clean TMP at Tmax > max | `clean_tmp_max_bar` from DB | PASS/FAIL |
| Fouled TMP at Tmin > max | `fouled_tmp_max_bar` from DB | PASS/FAIL |
| Fouled TMP at Tdesign > max | `fouled_tmp_max_bar` from DB | PASS/FAIL |

### Hardcoded Operating Schedule

| Parameter | Value | Notes |
|---|---|---|
| Filtration cycle duration | 90 min | Hardcoded |
| CEB acid interval | 168 h | Hardcoded (weekly) |
| CEB alkali interval | 168 h | Hardcoded (weekly) |
| CIP interval | 90 days | Hardcoded (quarterly) |
| FF safety factor | 1.5× | Applied to `min_forward_flush_m3h` |
| Fouled TMP multiplier | 2× clean | Hardcoded approximation |

### Outputs

```json
{
  "overview": {
    "module_type", "online_units": 1, "total_modules",
    "gross_feed_m3h", "net_product_m3h", "recovery_pct",
    "tmp_design_bar", "tmp_tmin_bar"
  },
  "operating_conditions": {
    "filtration_duration_min": 90,
    "filtration_flux_lmh", "backwash_duration_min", "backwash_flux_lmh",
    "acid_ceb_interval_h": 168, "alkali_ceb_interval_h": 168, "cip_interval_d": 90
  },
  "water_quality": {
    "temperature_c", "feed_turbidity_ntu", "prod_turbidity_ntu": 0.1,
    "feed_tss_mgl", "prod_tss_mgl": 0.0,
    "feed_tds_mgl", "prod_tds_mgl": feed_tds  // UF does NOT remove TDS
  },
  "warnings": [{"type", "unit", "limit", "estimate", "status"}]
}
```

> **Note:** `prod_tds_mgl` = `feed_tds` — UF membranes pass dissolved solids completely. TDS rejection is zero by design.
