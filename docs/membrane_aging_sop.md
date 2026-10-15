# Standard Operating Procedure (SOP): Year-Wise Performance and Membrane Aging Module

## 1. Introduction and Scope
This document details the **Standard Operating Procedure (SOP)** and internal mathematical architecture for the **Year-Wise Performance and Membrane Aging Module** within the PACE backend engine.

This SOP is written explicitly for developers and process engineers. It contains **every equation, algorithmic step, computational loop, and engineering rationale** used in the codebase (`physics_aging_engine.py`). A developer reading this document will be able to replicate the exact code logic directly from the text provided here.

---

## 2. Core Algorithmic Architecture
The aging module projects membrane performance over $N$ years by simulating fouling accumulation, chemical degradation, and physical compaction. 

The architecture relies on three nested loops:
1. **Year Loop** (1 to $N$ years): Loops through the lifespan of the plant.
2. **Month Loop** (1 to 12 months): Time-steps the ordinary differential equations (ODEs) for fouling models using a monthly interval ($dt = 730$ hours).
3. **Spatial Discretization Loop** (Stages $\rightarrow$ Vessels $\rightarrow$ Elements $\rightarrow$ $NZ$ Segments): Solves spatial transport mechanics across 10 axial segments ($NZ=10$) per RO element to capture localized concentration polarization and flux variations.

At the end of each simulated year, a **Bisection Root-Finding Algorithm** is executed to calculate the new elevated feed pressure required to maintain the system's target recovery against the newly calculated fouling resistance.

---

## 3. Spatial Transport Solver (Axial Discretization)
**File Location:** `PhysicsAgingEngine._spatial_transport()`

Before calculating the fouling rate for a given month, the system calculates the local hydraulic and concentration conditions at the membrane wall for each segment.

### 3.1. Discretization Parameters
Each element is broken down into $NZ = 10$ segments.
- $dz = L_{element} / NZ$
- $Q_{in}$ = Feed flow into the element ($m^3/s$).
- For each segment, the local crossflow diminishes as permeate is extracted.

### 3.2. Crossflow and Mass Transfer
The crossflow velocity $v_{cross}$ and mass transfer coefficient $k_M$ are calculated using the Schock-Miquel correlation for spacer-filled channels.

**Equations:**
1. **Velocity:** $v_{cross} = \frac{Q_{loc}}{w_{total} \cdot t_{fs} \cdot \epsilon_{ch}}$
2. **Reynolds Number ($Re$):** $Re = \frac{\rho_w \cdot v_{cross} \cdot d_h}{\mu}$
3. **Schmidt Number ($Sc$):** $Sc = \frac{\mu}{\rho_w \cdot D_s}$
4. **Sherwood Number ($Sh$):** $Sh = 0.065 \cdot Re^{0.875} \cdot Sc^{0.25}$
5. **Mass Transfer Coefficient ($k_M$):** $k_M = \frac{Sh \cdot D_s}{d_h}$

**Variables Computed:**
- $\mu$: Water viscosity at operating temperature (Pa·s) via `_mu_water(T) = 1.0e-3 * exp(1808 / (T+273.15) - 6.354)`.
- $D_s$: Solute diffusivity corrected for temperature via Stokes-Einstein.
- $d_h$: Hydraulic diameter of the spacer channel.

### 3.3. Concentration Polarization (CP) and Wall Stress
**Equations:**
1. **Transmembrane Pressure (TMP):** $TMP = P_{feed, local} - P_{permeate} - \pi_{osmotic}$
2. **Local Flux ($J_w$):** $J_w = \frac{TMP}{\mu \cdot R_{total, local}}$ 
3. **CP Factor ($\beta$):** $\beta = \exp\left(\frac{J_w}{k_M}\right)$
4. **Wall Concentration ($C_{wall}$):** $C_{wall} = C_{bulk} \cdot \beta$
5. **Wall Shear Stress ($\tau_w$):** $\tau_w = 0.5 \cdot \left( 6.23 \cdot Re^{-0.3} \right) \cdot \rho_w \cdot v_{cross}^2$

**Rationale:**
Calculating exact local $J_w$ and $C_{wall}$ is critical. Fouling scales exponentially with CP. We use the Resistance-in-Series model where $R_{total, local} = R_m + R_c + R_b + R_s + R_n + R_{comp}$. 

---

## 4. Fouling ODE Sub-Models (The 5 Mechanisms)
For every segment, 5 Ordinary Differential Equations (ODEs) dictate how fouling material accumulates over the monthly timestep ($dt = 730$ hours).

### Sub-Model I: Cake / Colloidal Filtration
**File Location:** `_ode_cake()`

**Equation:**
$$ \frac{dm_c}{dt} = K_d \cdot J_w \cdot C_b - K_{rem} \cdot \tau_w \cdot m_c $$

**Algorithm & Computation:**
- $m_c$: Cake mass per unit area ($kg/m^2$).
- **Deposition term:** Directly proportional to flux $J_w$, bulk particle concentration $C_b$ (derived from SDI), and deposition coefficient $K_d$.
- **Removal term:** Proportional to wall shear stress $\tau_w$, current cake mass $m_c$, and removal coefficient $K_{rem}$.

**Rationale:**
The Hermia-Tung cake filtration model balances particle convective deposition against crossflow shear-induced erosion. This perfectly represents spiral-wound RO elements where velocity prevents infinite cake growth.

### Sub-Model II: Biofouling (Biofilm Growth)
**File Location:** `_ode_biofilm()`

**Equation:**
$$ \frac{dL_b}{dt} = \mu_{eff} \cdot L_b + J_{b,seed} - b_d \cdot L_b $$
$$ \mu_{eff} = \mu_{max} \cdot \exp\left[\frac{E_{a,bio}}{R} \left(\frac{1}{T_{ref}} - \frac{1}{T}\right)\right] \cdot \frac{BDOC}{K_s + BDOC} $$

**Algorithm & Computation:**
- $L_b$: Biofilm thickness ($m$).
- Uses **Monod Kinetics** to limit biological growth based on available Biodegradable Dissolved Organic Carbon ($BDOC$).
- Applies the **Arrhenius Equation** to scale growth rate by temperature.
- $J_{b,seed}$ represents constant bacterial seeding from the feed.
- $b_d$ represents detachment and death rate.

**Rationale:**
Biological growth is exponential but substrate-limited. Monod kinetics is the undisputed industry standard for modeling bioreactor and biofilm growth rates.

### Sub-Model III: Inorganic Scaling (Classical Nucleation Theory)
**File Location:** `_ode_scaling()`

**Equation:**
1. **Saturation Index (SI) at wall:** $SI_{wall} = \log_{10}(CP) + SI_{bulk}$
2. **Induction Time ($t_{ind}$):** $t_{ind} = A_{ind} \cdot \exp(\Delta G_{kT}) \cdot t_{ind\_factor}$
3. **Growth Rate (only if elapsed time $t_{SI} > t_{ind}$):**
   $$ \frac{d\delta_s}{dt} = \frac{k_g \cdot (SI_{wall})^{n_s}}{\rho_{scale}} $$

**Algorithm & Computation:**
- $\delta_s$: Scale layer thickness ($m$).
- A separate state variable $t_{SI}$ tracks how long the segment has been exposed to supersaturated conditions.
- If antiscalant is dosed, $t_{ind\_factor} = 10.0$ artificially extending the induction time.

**Rationale:**
Unlike colloids, scale does not form immediately. **Classical Nucleation Theory (CNT)** is selected because it accurately captures the "induction period"—scale will only form if the supersaturation persists longer than the time required for crystals to nucleate.

### Sub-Model IV: NOM Adsorption
**File Location:** `_ode_nom()`

**Equation:**
$$ \frac{dq}{dt} = k_{ads} \cdot (q_{eq} - q) \cdot \text{shear\_modifier} $$
$$ q_{eq} = q_{max} \cdot \frac{K_L \cdot C_{nom,w}}{1 + K_L \cdot C_{nom,w}} $$

**Algorithm & Computation:**
- $q$: Mass of adsorbed NOM ($kg/m^2$).
- **Langmuir Isotherm:** Dictates $q_{eq}$, the maximum equilibrium capacity based on the concentration of Natural Organic Matter at the wall ($C_{nom,w}$).

**Rationale:**
Adsorption sites on a membrane are finite. The Langmuir model mathematically ensures that NOM fouling asymptotes to a maximum capacity rather than growing infinitely, accurately reflecting actual membrane surface chemistry.

### Sub-Model V: Membrane Compaction (Viscoelastic Creep)
**File Location:** (In-line in month loop)

**Equation:**
$$ \epsilon_{inf} = \frac{TMP \cdot f_{stress}}{E_m} $$
$$ \epsilon_{new} = \epsilon_{old} + (\epsilon_{inf} - \epsilon_{old}) \cdot \left(1 - \exp\left(\frac{-dt}{\tau_c}\right)\right) $$

**Algorithm & Computation:**
- $\epsilon$: Compaction strain (dimensionless).
- Modeled as a **Kelvin-Voigt** viscoelastic material.
- Uses local $TMP$ as the applied compressive stress.

**Rationale:**
Polyamide membranes physically compact under high pressure, permanently losing permeability. A Kelvin-Voigt creep model accurately represents the time-dependent deformation of polymers, showing rapid initial compaction that slowly plateaus.

---

## 5. ODE Integration Algorithm (Runge-Kutta 4th Order)
To ensure absolute numerical stability over the 1-month timestep ($dt = 730$ hours) without overshooting equilibrium states, the engine integrates the above ODEs using the **4th-Order Runge-Kutta (RK4)** method.

**Algorithm (`_rk4_step`):**
Given an ODE $\frac{dy}{dt} = f(t, y)$:
1. $k_1 = f(t, y)$
2. $k_2 = f(t + \frac{dt}{2}, y + k_1 \cdot \frac{dt}{2})$
3. $k_3 = f(t + \frac{dt}{2}, y + k_2 \cdot \frac{dt}{2})$
4. $k_4 = f(t + dt, y + k_3 \cdot dt)$
5. $y_{new} = y + \frac{dt}{6} (k_1 + 2k_2 + 2k_3 + k_4)$

**Rationale:**
Explicit Euler is too unstable for the large 730-hour timestep, often resulting in runaway fouling growth. RK4 provides robust $O(dt^4)$ accuracy, allowing us to jump a whole month accurately with low computational overhead.

---

## 6. Translating State Variables to Resistance
Once the state variables ($m_c$, $L_b$, $\delta_s$, $q$, $\epsilon$) are integrated for the month, they are converted into hydraulic resistances ($m^{-1}$).

1. **Cake Resistance ($R_c$):** $R_c = \alpha_0 \cdot \left(\frac{TMP}{TMP_{ref}}\right)^{sc} \cdot m_c$
   *(Accounts for cake compression under pressure via exponent $sc$)*
2. **Biofilm Resistance ($R_b$):** Calculated via Kozeny-Carman equation for fibrous EPS.
   $R_b = \frac{180 \cdot (1-\epsilon_{bf})^2 \cdot \tau_{bf} \cdot L_b}{d_{EPS}^2 \cdot \epsilon_{bf}^3}$
3. **Scale Resistance ($R_s$):** $R_s = \alpha_s \cdot (\rho_s \cdot \delta_s)$
4. **NOM Resistance ($R_n$):** $R_n = r_{NOM} \cdot q$
5. **Compaction Resistance ($R_{comp}$):** $R_{comp} = \epsilon \cdot R_{m,base}$

The **Fouling Resistance Index (FRI)** is then evaluated:
$$ FRI = \frac{R_c + R_b + R_s + R_n + R_{comp}}{R_{m,base} + R_c + R_b + R_s + R_n + R_{comp}} $$

---

## 7. Salt Permeability Degradation (Chemical Aging)
While hydraulic resistance increases over time, the ability of the membrane to reject salt degrades due to gradual chemical attack (e.g., halogens, hydrolysis).

**Equation:**
$$ k_{B,eff} = \left(\frac{k_{B,chem}}{12}\right) \cdot \exp\left[\frac{E_{a,B}}{R} \left(\frac{1}{T_{ref}} - \frac{1}{T}\right)\right] $$
$$ B_{rel, new} = B_{rel, old} \cdot (1 + k_{B,eff}) $$

**Algorithm & Computation:**
- $B_{rel}$ tracks the relative increase in the B-value (salt permeability).
- The base rate $k_{B,chem}$ is calibrated to the industry average of ~1.5% degradation per year for BWRO membranes.

**Rationale:**
First-order Arrhenius kinetics accurately describe the exponential dependence of polymer chain scission (chemical degradation) on temperature.

---

## 8. Year-End System Solver (Bisection Algorithm)
**File Location:** `_year_end_snapshot()`

At the end of month 12, the system must determine the **2nd year pressure** (or Nth year). Because fouling has increased the resistance, the plant must increase feed pressure to maintain the target recovery.

### The Algorithm
1. **Calculate Effective Permeability:**
   For every element, adjust the theoretical clean A-value and B-value using the accumulated fouling and chemical aging from the ODEs:
   $$ A_{eff} = \frac{A_0}{1 + FRI_{element}} \cdot (1 - \epsilon_{comp, element}) $$
   $$ B_{eff} = B_0 \cdot B_{rel, element} $$

2. **Bisection Setup:**
   - Target = `target_recovery_pct`
   - $P_{lo} = P_{Year0} \cdot 0.5$
   - $P_{hi} = P_{Year0} \cdot 2.5$

3. **Bisection Loop (25 Iterations):**
   - $P_{mid} = (P_{lo} + P_{hi}) / 2.0$
   - Execute the core RO calculation engine (`ROEngine.simulate_system()`) using $P_{mid}$ and the arrays of $A_{eff}$ and $B_{eff}$ for all elements.
   - Extract the calculated recovery from the simulation.
   - If `calculated_recovery < target_recovery`:
     The pressure is too low to overcome the fouling. Set $P_{lo} = P_{mid}$.
   - Else: Set $P_{hi} = P_{mid}$.
   - Break early if `abs(calculated_recovery - target_recovery) < 0.0005`.

### 8.1 Year-Wise Performance Output Variables
Once the required Nth year pressure is found, the engine calculates and stores the Year-Wise Performance array (`annual_snapshots`). The following variables are explicitly computed for each year:
- **`feed_pressure_bar`**: The required feed pressure ($P_{mid}$) found via the bisection loop.
- **`perm_flow`**: Permeate flow rate ($Q_p$), extracted from the simulation.
- **`recovery`**: Final system recovery ($Q_p / Q_{feed}$), verified against the target.
- **`perm_tds`**: Total Dissolved Solids in the permeate, calculated using the degraded $B_{eff}$ values.
- **`sec_kwh_m3`**: Specific Energy Consumption. Calculated as $SEC = \frac{HP_{pump\_kw} + BP_{pump\_kw}}{Q_p}$.
- **`dominant_mechanism`**: Derived by finding the maximum hydraulic resistance across Cake ($R_c$), Biofouling ($R_b$), Scaling ($R_s$), NOM ($R_n$), and Compaction ($R_{comp}$).
- **`fri`**: The system-average Fouling Resistance Index calculated in step 6.

**Rationale:**
The RO system is highly non-linear due to osmotic pressure feedbacks. An analytical solution for the required feed pressure does not exist when elements have non-uniform $A_{eff}$ profiles. Bisection provides guaranteed, unconditionally stable convergence to find the exact pressure required by the Variable Frequency Drive (VFD) of the high-pressure pump.

---

## 9. ASTM D4516-19a Normalization Calculations
Once the new operating state is found via the Bisection solver, standard normalized metrics are generated for reporting.

1. **Normalized Permeate Flow (NPF):**
   $NPF = (Q_{p, YearN} / Q_{p, Year0}) \cdot TCF_{ratio}$
   *(Since temperature is constant in projection, TCF ratio is 1.0. If the bisection successfully restores flow, NPF remains near 1.0, but practically we report the flux-ratio NPF).*

2. **Normalized Differential Pressure Ratio (NDP Ratio):**
   $NDP_{Ratio} = \frac{NDP_{YearN}}{NDP_{Year0}}$
   *(NDP increases linearly with the Fouling Resistance Index).*

3. **Normalized Salt Passage (NSP):**
   $NSP_{total} = \frac{TDS_{YearN} \cdot Q_{p, Year0}}{TDS_{Year0} \cdot Q_{p, YearN}}$
   To isolate fouling-driven concentration polarization from chemical degradation, the codebase calculates:
   $NSP_{fouling} = NSP_{total} \cdot B_{rel, avg}$

**Rationale:**
These variables are directly mandated by ASTM D4516-19a. Field operators strictly monitor NPF, NDP, and NSP to schedule maintenance. Providing these exact metrics bridges theoretical physics modeling with practical plant operation.

---

## 10. Clean-In-Place (CIP) Logic and Kinetics
**File Location:** `_apply_cip()`

If severe fouling is detected, a chemical cleaning event is triggered, dynamically reducing the state variables.

### CIP Triggers:
A CIP is triggered at the end of the year (or scheduled monthly) if:
- $NPF < 0.85$ (15% loss)
- Feed Pressure Ratio $> 1.35$ (35% increase)
- $FRI > 0.60$ (Resistance dominates permeability)

### CIP Kinetic Equations:
CIP relies on exponential decay kinetics representing chemical dissolution and hydrolysis.
- $k_{diss} = k_{d,acid} \cdot \exp\left(\frac{E_{a,dis}}{R}(\frac{1}{T_{cip}}-\frac{1}{T})\right) \cdot [H^+]$
- $k_{bio,r} = k_{d,bio} \cdot \exp\left(\frac{E_{a,bio\_rem}}{R}(\frac{1}{T_{cip}}-\frac{1}{T})\right) \cdot [OH^-]$

**Algorithmic Update:**
1. **Acid CIP** (pH 2.5):
   - Scale thickness: $\delta_s = \delta_s \cdot \exp(-k_{diss} \cdot t_{CIP,acid})$
   - Cake colloidal mass: $m_c = m_c \cdot \exp(-k_{coll} \cdot t_{CIP,acid})$
2. **Alkaline CIP** (pH 11.5):
   - Biofilm: $L_b = L_b \cdot \exp(-k_{bio,r} \cdot t_{CIP,alk})$
   - NOM: $q = q \cdot \exp(-k_{nom,r} \cdot t_{CIP,alk})$

**Rationale:**
CIP doesn't reset the membrane to 100% clean instantly. Kinetics strictly depend on pH (activity of H+ and OH- ions) and temperature. Acid dissolves inorganics (Scale/Cake), while Alkaline hydrolyzes organics (Biofilm/NOM).

---

## 11. Membrane Replacement Logic
At the end of every year, the module checks if the membrane has reached the end of its physical life.

**Triggers:**
- $NPF < 0.70$ (30% permanent loss despite CIP).
- Specific Energy Consumption ($SEC$) increases by $> 50\%$.
- Operating hours $\geq 43,800$ (5 years hardcoded mechanical lifespan).

**Algorithm:**
If triggered, the engine records a replacement event and resets all state variables ($m_c$, $L_b$, $\delta_s$, $q$, $\epsilon_{comp}$, $B_{rel}$) to `0.0` or `1.0` appropriately, essentially inserting fresh elements into the vessels for the subsequent year's calculation.
