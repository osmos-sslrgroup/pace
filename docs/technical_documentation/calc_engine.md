# PACE — `calc_engine.py` Technical Documentation

**File:** `backend/calc_engine.py` | 659 lines | 29,801 bytes
**Docstring:** "Implements Solution-Diffusion and Spiegler-Kedem mass transport models."

---

## 1. Purpose & Scope

`calc_engine.py` is the fundamental physics layer of PACE. It implements element-level RO and NF membrane simulation using the **Solution-Diffusion model** for water transport and the **Spiegler–Kedem–Katchalsky (SKK) model** for solute transport. Every higher-level engine (`system_engine.py`, `aging_engine.py`, `physics_aging_engine.py`) calls this module to simulate individual membrane elements.

**Pipeline position:** Feed conditions (flow, pressure, ion concentrations, temperature) → returns permeate/concentrate compositions, flux, NDP, ΔP, and CP factor. Has no knowledge of multi-stage topology — that is handled by `simulate_system`.

---

## 2. Class: `ROEngine`

### 2.1 `__init__` (Lines 11–21)

**Constants:**
- `self.R_gas = 0.08314` — Universal gas constant, L·bar/(mol·K)

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

## 3. Every Equation

### 3.1 `_calculate_osmotic_pressure` (Lines 23–55)

**Purpose:** Osmotic pressure (bar) via van't Hoff with piecewise osmotic coefficient.

Absolute temperature:
$$T_K = T_{°C} + 273.15 \text{ K}$$

Molar concentration of ion $i$:
$$m_i = \frac{C_i [\text{mg/L}]}{1000 \times MW_i} \text{ mol/L}$$

Total molar concentration:
$$C_{total} = \sum_i m_i \text{ mol/L}$$

**Piecewise osmotic coefficient** $\varphi$ (function of TDS = $\sum_i C_i$):

| TDS Range (mg/L) | $\varphi$ |
|---|---|
| ≤ 100 | 1.000 |
| 100–500 | $0.98 - \frac{\text{TDS}-100}{400} \times 0.03$ |
| 500–1000 | 0.950 |
| 1000–10000 | 0.930 |
| 10000–35000 | $0.93 - \frac{\text{TDS}-10000}{25000} \times 0.03$ |
| ≥ 35000 | 0.900 |

Van't Hoff osmotic pressure:
$$\pi = C_{total} \times R_{gas} \times T_K \times \varphi \text{ (bar)}$$

**Source:** Van't Hoff (1887). Piecewise φ: [INTERNAL METHOD — Permionics-developed calibration]

**Edge cases:** Ions not in `self.MM` silently skipped. Zero/negative concentrations skipped.

---

### 3.2 `_calculate_tcf` (Lines 57–70)

**Purpose:** Temperature Correction Factor for water permeability A.

**NF path** (when `E_Aw_over_R` is provided):
$$TCF_{NF} = \exp\left[\frac{E_{Aw}}{R} \times \left(\frac{1}{298.15} - \frac{1}{T_K}\right)\right]$$

**RO path** (when `E_Aw_over_R` is None):
$$TCF_{RO} = \exp\left[U \times \left(\frac{1}{298.15} - \frac{1}{T_K}\right)\right]$$

where:
$$U = \begin{cases} 2640 \text{ K} & T_{°C} \leq 25 \\ 3020 \text{ K} & T_{°C} > 25 \end{cases}$$

Reference temperature = 298.15 K (25°C) for both paths.

**Source:** [INTERNAL METHOD — U values consistent with DuPont FILMTEC TCF conventions]

---

### 3.3 `_calculate_cp_beta` (Lines 72–149)

**Purpose:** Concentration polarisation factor $\beta = C_m / C_b$ using film theory + Schock–Miquel.

**Spacer hydraulic diameter:**
$$t_{fs} = \text{spacer\_mil} \times 2.54 \times 10^{-5} \text{ m}$$
$$d_h = 2 \times t_{fs} \text{ m}$$

**Channel cross-section (void fraction $\varepsilon = 0.90$):**
$$W = \frac{A_{active}}{2 \times L_{element}} \text{ m}$$
$$A_{cross} = W \times t_{fs} \times 0.90 \text{ m}^2$$

**Cross-flow velocity:**
$$v = \frac{Q_{m^3/s}}{A_{cross}} \text{ m/s}$$

**Andrade viscosity:**
$$\mu(T) = 10^{-3} \times \exp\left(\frac{1808.0}{T_K} - 6.354\right) \text{ Pa·s}$$

**Reynolds number:**
$$Re = \frac{d_h \times v}{\nu}, \quad \nu = \frac{\mu_T}{1000}$$

**Ion-specific diffusivities at 25°C (m²/s):**
Na=1.33e-9, Cl=2.03e-9, Ca=0.79e-9, Mg=0.71e-9, SO4=1.07e-9, HCO3=1.19e-9, K=1.96e-9, B=1.10e-9, NO3=1.90e-9; default=1.6e-9

**Weighted diffusivity at 25°C:**
$$D_{AB,25} = \frac{\sum_i C_i \times D_i}{\sum_i C_i}$$

**Stokes–Einstein T-correction:**
$$D_{AB}(T) = D_{AB,25} \times \frac{T_K}{298.15} \times \frac{\mu_{25}}{\mu(T)}$$

**Schock–Miquel Sherwood number:**
$$Sh = 0.04 \times Re^{0.75} \times Sc^{0.33}, \quad Sc = \frac{\nu}{D_{AB}}$$

**Mass transfer coefficient:**
$$k_M = \frac{Sh \times D_{AB}}{d_h} \text{ m/s}$$

**CP factor (film theory):**
$$\beta = \exp\left(\frac{J_v}{k_M}\right), \quad J_v = \frac{J_{LMH}}{1000 \times 3600} \text{ m/s}$$

Returns 1.0 if $k_M \leq 0$.

**Source:** Schock & Miquel (1987), Desalination 64:339–352 [VERIFIED — External]; Film theory CP: Brian (1966) [VERIFIED — External]

---

### 3.4 `_calculate_pressure_drop` (Lines 151–182)

**Purpose:** Element pressure drop via Darcy–Weisbach with Schock–Miquel friction factor.

Same geometry and Re as `_calculate_cp_beta`, then:

**Friction factor:**
$$\lambda = 6.23 \times Re^{-0.30}$$

**Darcy–Weisbach:**
$$\Delta P_{Pa} = \lambda \times \frac{L_{element}}{d_h} \times \frac{\rho_w v^2}{2}$$
$$\Delta P_{bar} = \frac{\Delta P_{Pa}}{100000}$$

**Clipping:** `max(0.001, min(ΔP_bar, 1.5))`

**Source:** Schock & Miquel (1987) [VERIFIED — External]

---

### 3.5 `simulate_element` — Spiegler–Kedem Solute Transport (Lines 250–295)

**Reflection coefficient** $\sigma_i$: RO default = 0.99; NF default = 0.347.

**RO salt permeability (from B):**
$$P_{s,ms} = \frac{B \times (1-\sigma)}{0.01} \text{ m/s}, \quad P_{s,mh} = P_{s,ms} \times 3600 \text{ m/h}$$

**Spiegler–Kedem true rejection:**
$$\text{exponent} = -\frac{J_{v,mh} \times (1-\sigma)}{P_{s,mh}}$$
$$F_i = \frac{1-\sigma}{1 - \sigma \cdot e^{\text{exponent}}}$$
$$R_{true} = 1 - F_i$$

Edge cases: `OverflowError` → $R_{true} = \sigma$; $J_{v,mh} \leq 0$ or $P_{s,mh} \leq 0$ → $R_{true} = 0$.

**Flow ratio:**
$$r = \frac{Q_{perm}}{2 \times \max(0.001, Q_{feed} - Q_{perm})}$$

**Self-consistent concentrations:**
$$\text{denom} = R_{true} + \beta_{calc} \times (1 - R_{true})$$
$$F_{factor} = \frac{\beta_{calc} \times (1-R_{true})}{\text{denom}}$$
$$C_{perm,i} = C_{f,i} \times \frac{F_{factor}(1+r)}{1 + F_{factor} \cdot r}$$
$$C_{bulk,i} = C_{f,i} \times \frac{1+r}{1 + F_{factor} \cdot r}$$
$$C_{membrane,i} = \frac{C_{bulk,i} \times \beta_{calc}}{\text{denom}}$$

**Source:** Spiegler & Kedem (1966), Desalination 1(4):311–326 [VERIFIED — External]

---

### 3.6 `simulate_element` — Water Transport (Lines 302–330)

**NDP:**
$$NDP = \max(0, P_{avg} - 0.5 - \Delta\pi) \text{ bar}$$

$P_{avg} = \max(1.0, P_{feed} - dp/2)$; 0.5 bar = fixed permeate backpressure.

**Solution-Diffusion flux:**
$$J_{v,new} = A \times NDP \times TCF \text{ LMH}$$

**Damped iteration update:**
$$Q_{perm} \leftarrow 0.7 \times Q_{perm,old} + 0.3 \times Q_{perm,new}$$
$$Q_{perm} = \min(Q_{perm}, 0.99 \times Q_{feed})$$

Convergence: $|Q_{perm,new} - Q_{perm,old}| < 0.001$ m³/h; max 20 iterations.

**Source:** Wijmans & Baker (1995), J. Membr. Sci. 107:1–21 [VERIFIED — External]

---

### 3.7 Donnan Electroneutrality Correction for NF (Lines 353–378)

Applied only when `is_nf = True` AND feed Cl > 0.

$$\Sigma_{cat} = \sum_{cat}\frac{C_{p,i}}{MW_i} \times z_i \text{ meq/L}$$

Cations: Ca²⁺(z=2), Mg²⁺, Na⁺(z=1), K⁺, Ba²⁺, Sr²⁺, NH₄⁺, Fe²⁺, Mn²⁺, Al³⁺(z=3)

$$\Sigma_{an} = \sum_{an}\frac{C_{p,i}}{MW_i} \times z_i \text{ meq/L}$$

Anions: SO₄²⁻(z=2), HCO₃⁻(z=1), NO₃⁻, F⁻, PO₄³⁻(z=3)

$$C_{p,Cl} = \max(0, (\Sigma_{cat} - \Sigma_{an}) \times 35.45) \text{ mg/L}$$

Physical cap: $C_{p,Cl} \leq C_{f,Cl} \times 1.05$

**Source:** [INTERNAL METHOD — Donnan charge balance; based on Donnan (1911)]

---

### 3.8 Booster Pump & Energy (Lines 546–656)

**Booster pump:**
$$\Delta P_{boost} = \max(0, P_{required} - P_{available})$$
$$P_{required} = \pi_{conc} + NDP_{avg} + 0.5 \text{ bar}$$
$$P_{boost,kW} = \frac{Q_{conc} \times \Delta P_{boost}}{36.0 \times 0.75}$$

**HP pump and SEC:**
$$P_{HP,kW} = \frac{Q_{feed} \times P_{feed}}{36.0 \times 0.80}$$
$$SEC = \frac{P_{HP} + P_{boost,total}}{Q_{perm}} \text{ kWh/m}^3$$

**Source:** [INTERNAL METHOD — engineering design assumptions; η_HP=0.80, η_boost=0.75]

---

## 4. Algorithms

### 4.1 Iterative Self-Consistent Solver (`simulate_element`)

- **Method:** Damped fixed-point iteration
- **Initial guess:** $Q_{perm,0} = Q_{feed} \times 0.10$
- **Damping:** 0.30 weight on new estimate
- **Max iterations:** 20 | **Tolerance:** 0.001 m³/h
- **Ceiling:** $Q_{perm} \leq 0.99 Q_{feed}$
- **Rationale:** Undamped updates diverge at high flux because flux → CP → osmotic pressure → NDP → flux is a positively-coupled feedback loop.

### 4.2 Multi-Stage Topology (`simulate_system`)

- Parallel vessels in each stage receive equal feed flow (`Q_stage / vessels`)
- Elements are in series: concentrate of element $e$ is feed of element $e+1$
- Stage totals are scaled by vessel count

### 4.3 Warning Generation

Five warnings checked per element: feed flow > max, concentrate flow < min, feed pressure > max, element recovery > max, beta ≥ 1.20.

---

## 5. Change / Validation History

| Issue | Description | Fix |
|---|---|---|
| CP divergence | Unbounded β at low crossflow | `beta_cap` parameter (default 1.25) introduced |
| Iteration oscillation | Undamped updates diverged at high flux | Damping factor w=0.30 applied |
| Piecewise φ | Original used φ=1.0 throughout | Piecewise φ calibration added for seawater range |
| Sherwood variant | `calc_engine` uses `0.04·Re^0.75·Sc^0.33` vs `physics_aging_engine` `0.065·Re^0.875·Sc^0.25` | Two separate calibrations of Schock–Miquel; intentional divergence |

---

## 6. Source Tags

| Equation | Tier | Citation |
|---|---|---|
| Van't Hoff osmotic pressure | External | Standard thermodynamics |
| Piecewise φ | Internal Method | Permionics calibration |
| TCF (U=2640/3020 K) | Internal Method | Based on DuPont FILMTEC conventions |
| Andrade viscosity | External | Standard empirical correlation |
| Stokes–Einstein diffusivity | External | Standard |
| Schock–Miquel Sh/λ | External | Schock & Miquel, Desalination 64 (1987) |
| SKK transport | External | Spiegler & Kedem, Desalination 1(4) (1966) |
| Solution-Diffusion | External | Wijmans & Baker, J. Membr. Sci. 107 (1995) |
| Donnan correction (NF) | Internal Method | Based on Donnan (1911) |
| η_HP=0.80, η_boost=0.75 | Internal Method | Engineering design assumptions |
