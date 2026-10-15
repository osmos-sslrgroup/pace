# Physics-Based Aging Models Documentation

The `physics_aging_engine.py` implements a strictly mechanistic Ordinary Differential Equation (ODE) framework. It discretizes the array into spatial segments and uses a 4th-order Runge-Kutta (RK4) solver to integrate the ODEs over time.

Below are the exact mathematical models and logic implemented in the backend, utilizing LaTeX math notation for the governing equations.

## 1. Sub-model I: Cake Filtration (Colloidal & Particulate)
**Mechanism:** Particulate deposition driven by convective flux vs. shear-induced detachment.
**ODE Formulation:**
\[\frac{dm_c}{dt} = K_d \cdot J_w \cdot C_b - K_{rem} \cdot \tau_w \cdot m_c\]
*   \(m_c\): Cake mass per unit area (\(kg/m^2\))
*   \(K_d, K_{rem}\): Deposition and removal rate constants
*   \(J_w\): Local water flux
*   \(\tau_w\): Wall shear stress (driven by crossflow)

**Resistance (Compressible Cake):**
\[R_c = \alpha_0 \left( \frac{TMP}{TMP_{ref}} \right)^{s_c} \cdot m_c\]

## 2. Sub-model II: Biofouling (Biofilm Growth)
**Mechanism:** Bacteria attach and multiply, creating an EPS matrix. Modeled via Monod kinetics coupled with Logistic Growth to enforce a physical carrying capacity limit (preventing unbounded exponential explosions).
**ODE Formulation:**
\[\frac{dL_b}{dt} = \mu_{eff} \cdot L_b \cdot \left(1 - \frac{L_b}{L_{b,max}}\right) + J_{b,seed} - b_d \cdot L_b\]
Where the effective growth rate \(\mu_{eff}\) follows Monod kinetics based on TOC (nutrient) concentration:
\[\mu_{eff} = \mu_{max} \cdot \left( \frac{C_{toc}}{K_s + C_{toc}} \right) \cdot \exp\left( \frac{E_a}{R} \left( \frac{1}{T_{ref}} - \frac{1}{T} \right) \right)\]

**Resistance (Kozeny-Carman for fibrous biofilm):**
\[R_b = \frac{180 \cdot (1 - \epsilon_{bf})^2 \cdot \tau_{bf} \cdot L_b}{d_p^2 \cdot \epsilon_{bf}^3}\]

## 3. Sub-model III: Mineral Scaling (Classical Nucleation Theory)
**Mechanism:** Salts exceed solubility limits at the membrane wall. Scaling only initiates after an induction time \(t_{ind}\) (which is significantly extended by antiscalant).
**ODE Formulation:**
Once \(t > t_{ind}\), parabolic crystal growth applies based on the true supersaturation ratio \(S\):
\[S = 10^{SI_{wall}}\]
\[\frac{d(\delta_s)}{dt} = k_g \cdot \frac{(S - 1)^{n_s}}{\rho_{scale}}\]
*   \(\delta_s\): Scale thickness (\(m\))
*   \(SI_{wall}\): Saturation Index at the wall (including Concentration Polarization)

**Resistance:**
\[R_s = \alpha_s \cdot \rho_{scale} \cdot \delta_s\]

## 4. Sub-model IV: Organic Fouling (NOM Adsorption)
**Mechanism:** Natural Organic Matter (NOM) adsorbs onto the membrane surface via a Langmuir isotherm.
**ODE Formulation:**
\[\frac{dq}{dt} = k_{ads} \cdot (q_{eq} - q) \cdot f_{shear}\]
Where the equilibrium adsorption \(q_{eq}\) is:
\[q_{eq} = q_{max} \cdot \frac{K_L \cdot C_{nom,w}}{1 + K_L \cdot C_{nom,w}}\]

**Resistance:**
\[R_n = r_{NOM} \cdot q\]

## 5. Sub-model V: Membrane Compaction
**Mechanism:** The polymer structure visco-elastically creeps under the applied trans-membrane pressure (TMP), permanently losing permeability.
**Kelvin-Voigt Creep Formula (Incremental):**
\[\epsilon_{comp}(t+\Delta t) = \epsilon_{comp}(t) + (\epsilon_{\infty} - \epsilon_{comp}(t)) \cdot \left(1 - \exp\left(-\frac{\Delta t}{\tau_c}\right)\right)\]
Where the asymptotic maximum compaction strain is driven by stress:
\[\epsilon_{\infty} = \frac{TMP \cdot f_{stress}}{E_m}\]

## 6. Chemical Cleaning (CIP) Kinetics
**Mechanism:** Acid washes dissolve scale and cake; alkaline washes dissolve biofilm and organics.
**Logic:** When CIP is triggered, the states (\(m_c, L_b, \delta_s, q\)) are reduced via Arrhenius-modified, pH-dependent first-order dissolution kinetics:
\[X_{post-CIP} = X_{pre-CIP} \cdot \exp(-k_{dis} \cdot t_{duration})\]

## Translating to ASTM Metrics
The discrete resistances are summed: 
\[R_{total} = R_m + R_c + R_b + R_s + R_n + R_{comp}\]
The `system_engine` then iteratively solves for the `P_feed` required to achieve the target flux against this dynamically shifting \(R_{total}\). From there, standard ASTM D4516-19a metrics (NPF, NSP, FRI) are back-calculated for the UI.
