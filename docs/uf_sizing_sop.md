# SOP & Specification Update: Intake-Limited UF Sizing

This document summarizes the mathematical formulas and systemic logic updates made to transition the Ultrafiltration (UF) simulation module from **Net Product-Targeted** sizing to **Intake-Limited** sizing.

---

## 1. Logic Comparison

| Design Philosophy | Sizing Origin | Recovery Treatment | Downstream RO/NF Feed |
| :--- | :--- | :--- | :--- |
| **Old: Net-Product Targeted** | User inputs a target net product flow ($Q_{\text{net}}$). The system estimates a higher gross intake flow ($Q_{\text{gross}}$) to satisfy this target. | Losses are added on top of the target product flow, increasing the required raw water intake. | RO is sized first. The UF net target is then locked to the RO feed requirement. |
| **New: Intake-Limited (Corrected)** | User inputs a fixed raw water feed rate (Intake $Q_{\text{gross}}$). Sizing is constrained by this maximum intake. | Losses (backwash and forward flush) are subtracted directly from the fixed intake to calculate the net output. | UF is sized first using the raw intake. The resulting UF net output is then passed as the RO feed. |

---

## 2. Mathematical Formula Changes

### 2.1 Initial Module Sizing
* **Old Formula (Estimation):**
  $$Q_{\text{gross}} \approx \frac{Q_{\text{net}}}{0.95} \quad (\text{Assuming 95\% initial recovery})$$
  $$N_{\text{modules}} = \left\lceil \frac{Q_{\text{gross}} \times 1000}{\text{Design Flux} \times A_{\text{module}}} \right\rceil$$

* **New Formula (Direct Sizing):**
  $$Q_{\text{gross}} = \text{Specified Intake Flow Rate (Fixed)}$$
  $$N_{\text{modules}} = \left\lceil \frac{Q_{\text{gross}} \times 1000}{\text{Design Flux} \times A_{\text{module}}} \right\rceil$$

---

### 2.2 System Flow Balance
* **Old Formula (Additive Losses):**
  $$Q_{\text{gross}} = Q_{\text{net}} + Q_{\text{BW loss}} + Q_{\text{FF loss}}$$

* **New Formula (Subtractive Losses):**
  $$Q_{\text{net}} = Q_{\text{gross}} - (Q_{\text{BW loss}} + Q_{\text{FF loss}})$$

---

### 2.3 Water Losses Definitions
* **Backwash Loss Rate ($Q_{\text{BW loss}}$):**
  $$V_{\text{BW,module}} = \frac{\text{BW Flux} \times A_{\text{module}} \times t_{\text{BW,s}}}{1000 \times 3600} \quad [\text{m}^3]$$
  $$Q_{\text{BW loss}} = V_{\text{BW,module}} \times N_{\text{modules}} \times f_{\text{cycles}} \quad [\text{m}^3/\text{h}]$$
* **Forward Flush Loss Rate ($Q_{\text{FF loss}}$):**
  $$Q_{\text{FF loss}} = Q_{\text{FF,module}} \times 1.5 \times N_{\text{modules}} \times \frac{t_{\text{FF,min}}}{60} \times f_{\text{cycles}} \quad [\text{m}^3/\text{h}]$$

---

## 3. Technology Chaining Logic (Multi-Train Staging)

When the technology train includes both **UF** and **RO/NF**, the data flow sequence changes as follows:

```
OLD SEQUENCE (Net-Product Sized):
1. Target Flow input (e.g. 50 m3/h) set as RO Permeate Target.
2. RO is simulated -> Requires ~66.7 m3/h RO Feed.
3. UF target net product (Q_net) is set to 66.7 m3/h.
4. UF is sized -> Calculates Q_gross = ~70.2 m3/h required intake.

NEW SEQUENCE (Intake-Limited):
1. Target Flow input (e.g. 50 m3/h) set as raw Intake (UF Gross Feed).
2. UF is sized directly -> Calculates Q_loss = ~3.5 m3/h.
3. UF Net Product (Q_net) is calculated: 50 - 3.5 = 46.5 m3/h.
4. RO Feed is set to 46.5 m3/h -> RO is simulated to achieve target recovery.
```

---

## 4. Summary of Impacted Modules

The above logic changes and formulas are implemented in:
- `backend/uf_engine.py` — core UF sizing and flow balance calculations
- `backend/system_engine.py` — technology chaining (UF → RO feed handoff)
- `backend/server_impl.py` — API payload construction and result assembly
