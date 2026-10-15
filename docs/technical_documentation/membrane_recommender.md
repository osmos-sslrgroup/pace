# PACE — `membrane_recommender.py` Technical Documentation

**File:** `backend/membrane_recommender.py` | 238 lines | 11,012 bytes

---

## 1. Purpose & Scope

`membrane_recommender.py` implements a multi-criteria membrane scoring and ranking engine. For every candidate Permionics membrane, it runs a full system simulation (`SystemEngine.calculate_system`) and scores the results against four weighted criteria. It is the engine behind the `/api/recommend-membrane` endpoint.

**Pipeline position:** User request → candidate membrane selection → per-membrane simulation loop → scoring → sorted ranked list.

---

## 2. Class: `MembraneRecommender`

### 2.1 Scoring Weights (Module-Level Constants, Lines 12–15)

| Criterion | Weight (points) | Description |
|---|---|---|
| `W_REJECTION` | 30 | Permeate TDS vs target |
| `W_HYDRAULIC` | 20 | Feed/concentrate flow limits |
| `W_ENERGY` | 30 | Specific Energy Consumption |
| `W_ENVELOPE` | 20 | Pressure limits & CP |

Total maximum score: **100 points**

**Source:** [INTERNAL METHOD — Permionics-developed weighting scheme; rationale: rejection and energy are considered equally dominant; hydraulic and envelope are secondary hard constraints]

---

### 2.2 `recommend` (Lines 17–124)

#### Purpose
Iterates over all matching candidate membranes, runs full simulation on each, scores, and returns sorted list.

#### Candidate Filtering Algorithm (Lines 27–54)

**NF train:** Candidates = all entries in `MembraneDatabase.RO_MEMBRANES` where `type == "NF"`.

**RO train — approximate TDS pre-filter:**
$$\text{TDS}_{approx} = \sum_i C_i \text{ (all numeric feed\_water values excluding metadata fields)}$$

Pre-filter rules:
| Approx TDS (mg/L) | Included Types |
|---|---|
| > 20,000 | SWRO only |
| 15,000–20,000 | SWRO + BWRO |
| < 15,000 | BWRO only (no SWRO) |

Only Permionics membranes are considered (manufacturer filter).

#### Simulation & Scoring Loop (Lines 59–113)
For each candidate:
1. Run `SystemEngine.calculate_system(test_inputs)` with candidate membrane injected
2. Call `_evaluate_results()` → score card
3. On exception: membrane marked as disqualified with reason = exception text

#### Sorting (Line 115)
```
results.sort(key=lambda x: (x["is_disqualified"], -x["total_score"]))
```
Non-disqualified membranes first, then by total score descending. Best membrane = first non-disqualified result.

---

### 2.3 `_evaluate_results` — Scoring Algorithm (Lines 126–237)

#### Criterion 1: Rejection Score (Lines 140–156) — 30 points

$$\text{rej\_score} = \begin{cases} 30 & \text{if } TDS_{perm} \leq TDS_{target} \\ \max(0,\ 30 - \min(30, (TDS_{perm} - TDS_{target}) \times 0.5)) & \text{if } TDS_{perm} > TDS_{target} \end{cases}$$

**Disqualification triggers:**
- Gap > 50 mg/L above target → `dq = True`
- `rej_score == 0` → `dq = True`
- Reason: "Cannot meet permeate quality requirements."

---

#### Criterion 2: Hydraulic Limits Score (Lines 161–179) — 20 points

Starts at 20 points; penalties deducted:

For each stage:
- `vessel_feed > max_feed_limit` → deduct 10 pts, `dq = True` (DQ: "Vessel feed flow exceeds maximum limit.")
- `vessel_conc < min_conc_limit` → deduct 5 pts

Floor: `max(0, hyd_score)`

Limit values from membrane database: `max_feed_flow_m3h` (default 15.9), `min_concentrate_flow_m3h` (default 2.0).

---

#### Criterion 3: Energy Score (Lines 183–189) — 30 points

$$\text{energy\_score} = \max(0,\ \min(30,\ 30 - (SEC - 1.0) \times 8))$$

| SEC (kWh/m³) | Energy Score |
|---|---|
| ≤ 1.0 | 30 (maximum) |
| 2.0 | 22 |
| 3.0 | 14 |
| 4.75 | 0 |
| > 4.75 | 0 |

**Source:** [INTERNAL METHOD — linear penalty of 8 pts per kWh/m³ above 1.0; reference point of 1.0 kWh/m³ corresponds to best BWRO practice]

---

#### Criterion 4: Operating Envelope & Beta Score (Lines 194–228) — 20 points

Starts at 20 points; penalties:

| Condition | Penalty | DQ? |
|---|---|---|
| `feed_pressure > max_pressure` | −20 (score = 0) | Yes: "Feed pressure exceeds max limit." |
| `feed_pressure > max_pressure × 0.9` | −5 | No (warning only) |
| `max_beta > 1.20` | $-\min(10, (\beta_{max} - 1.20) \times 50)$ | No |
| `source_type == SEAWATER` AND `mem_type != SWRO` | DQ | Yes: "Not suitable for Seawater." |
| `feed_tds > 20000` AND `mem_type != SWRO` | DQ | Yes: SWRO required. |
| `15000 ≤ feed_tds ≤ 20000` AND `mem_type == BWRO` | −5 | No (transition zone warning) |

**Beta penalty formula:**
$$\Delta_\beta = -\min(10,\ (\beta_{max} - 1.20) \times 50)$$

**Source:** [INTERNAL METHOD — Permionics-developed penalty schedule; β threshold of 1.20 consistent with general RO design practice to avoid excessive fouling rates]

---

## 3. Inputs & Outputs

**Inputs:** Complete `SystemCalcInput` payload dict (same as `/api/calculate-system`).

**Outputs:**
```json
{
  "best_membrane": "model_id or null",
  "recommendations": [
    {
      "model": "model_id",
      "name": "Display name",
      "type": "BWRO/SWRO/NF",
      "manufacturer": "Permionics",
      "total_score": 87.5,
      "is_disqualified": false,
      "disqualification_reason": null,
      "max_beta": 1.15,
      "criteria_scores": {"rejection": 30, "hydraulic": 20, "energy": 22, "envelope": 15},
      "justification": ["text strings..."],
      "calculated_metrics": {
        "permeate_tds": 45.2,
        "feed_pressure_bar": 8.3,
        "specific_energy": 2.0
      }
    }
  ]
}
```

---

## 4. Source Tags

| Item | Tier | Citation |
|---|---|---|
| 4-criterion scoring framework | Internal Method | Permionics-developed |
| Weights (30/20/30/20) | Internal Method | Permionics engineering judgment |
| Energy penalty slope (8 pts/kWh) | Internal Method | Permionics calibration |
| β penalty (50 pts/unit above 1.20) | Internal Method | Based on general RO practice |
| TDS pre-filter TDS thresholds | Internal Method | Based on membrane type applicability |
