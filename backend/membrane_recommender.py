from typing import Dict, Any, List, Optional
from membrane_database import MembraneDatabase
from system_engine import SystemEngine

class MembraneRecommender:
    """
    Multi-criteria membrane recommendation engine.
    Runs the full calculation module for every candidate membrane and scores
    them based on precise operational outputs (TDS, Energy, Hydraulic limits).
    """
    
    W_REJECTION   = 30
    W_HYDRAULIC   = 20
    W_ENERGY      = 30
    W_ENVELOPE    = 20

    def recommend(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Expects a complete SystemCalcInput payload dict.
        Iterates over all Permionics membranes, simulates them, and scores the results.
        """
        target_tds = inputs.get("target_tds", 50.0)
        source_type = inputs.get("source_type", "LOW_TDS").upper()
        tech_train = inputs.get("technology_train", "RO").upper()
        is_nf_train = "NF" in tech_train
        
        if is_nf_train:
            # Recommend NF membranes (usually DuPont in the database)
            candidates = {
                k: v for k, v in MembraneDatabase.RO_MEMBRANES.items()
                if v.get("type") == "NF"
            }
        else:
            # Calculate approximate feed TDS to filter membrane types early
            feed_water = inputs.get("feed_water", {})
            numeric_ions = [v for k, v in feed_water.items() if isinstance(v, (int, float)) and k not in ["temperature", "ph", "turbidity", "tss", "sdi15", "toc_mg_l", "cl2_residual_mg_l", "tds"]]
            approx_tds = sum(numeric_ions)
            
            all_ro = {
                k: v for k, v in MembraneDatabase.RO_MEMBRANES.items()
                if v.get("manufacturer", "").lower() == "permionics" and v.get("type") in ["BWRO", "SWRO"]
            }
            
            candidates = {}
            for k, v in all_ro.items():
                mem_type = v.get("type", "BWRO")
                if approx_tds > 20000:
                    if mem_type == "SWRO":
                        candidates[k] = v
                elif approx_tds >= 15000:
                    candidates[k] = v
                else:
                    if mem_type != "SWRO":
                        candidates[k] = v
        
        if not candidates:
            return {"recommendations": [], "message": "No matching membranes found for the selected technology train."}
            
        results = []
        engine = SystemEngine()
        
        for model_id, mem in candidates.items():
            # Inject candidate
            test_inputs = inputs.copy()
            test_inputs["ro_membrane"] = model_id
            
            try:
                # Run the mass-balance simulation (very fast, no scaling logic overhead here)
                calc_result = engine.calculate_system(test_inputs)
                ro = calc_result.get("ro_results", {})
                if not ro:
                    continue
                
                score_card = self._evaluate_results(mem, ro, target_tds, source_type)
                
                results.append({
                    "model": model_id,
                    "name": mem.get("name", model_id),
                    "type": mem.get("type", "RO"),
                    "manufacturer": mem.get("manufacturer", "Permionics"),
                    "total_score": round(score_card["total"], 1),
                    "is_disqualified": score_card["is_disqualified"],
                    "disqualification_reason": score_card.get("dq_reason"),
                    "max_beta": score_card.get("max_beta", 1.0),
                    "criteria_scores": score_card["criteria"],
                    "justification": score_card["justification"],
                    "estimated_vessels": test_inputs.get("vessels_per_stage", [4, 2]),
                    "calculated_metrics": {
                        "permeate_tds": round(ro["summary"].get("perm_tds", 0), 2),
                        "feed_pressure_bar": round(ro["summary"].get("feed_pressure_bar", 0), 2),
                        "specific_energy": round(ro["summary"].get("sec_kwh_m3", 0), 3)
                    }
                })
            except Exception as e:
                # Mark as disqualified if calculation fails (e.g. pressure too high)
                results.append({
                    "model": model_id,
                    "name": mem.get("name", model_id),
                    "type": mem.get("type", "RO"),
                    "manufacturer": mem.get("manufacturer", "Permionics"),
                    "total_score": 0,
                    "is_disqualified": True,
                    "disqualification_reason": f"Calculation failed: {str(e)}",
                    "criteria_scores": {},
                    "justification": [],
                    "estimated_vessels": test_inputs.get("vessels_per_stage", [4, 2]),
                    "calculated_metrics": {
                        "permeate_tds": 0.0,
                        "feed_pressure_bar": 0.0,
                        "specific_energy": 0.0
                    }
                })

        # Sort results: non-disqualified first, then by score descending
        results.sort(key=lambda x: (x["is_disqualified"], -x["total_score"]))
        
        best_model = None
        if results and not results[0]["is_disqualified"]:
            best_model = results[0]["model"]
            
        return {
            "best_membrane": best_model,
            "recommendations": results
        }
        
    def _evaluate_results(self, mem: Dict[str, Any], ro: Dict[str, Any], target_tds: float, source_type: str) -> Dict[str, Any]:
        """
        Scores the actual calculated performance against limits and targets.
        """
        score = 0
        dq = False
        dq_reason = ""
        justification = []
        criteria = {}
        
        summary = ro.get("summary", {})
        stages = ro.get("stages", [])
        
        # -----------------------------------------------------
        # 1. Rejection (30 pts)
        # -----------------------------------------------------
        perm_tds = summary.get("perm_tds", 9999)
        if perm_tds <= target_tds:
            rej_score = self.W_REJECTION
            justification.append(f"Comfortably meets target TDS ({perm_tds:.1f} <= {target_tds} mg/L).")
        else:
            gap = perm_tds - target_tds
            penalty = min(self.W_REJECTION, gap * 0.5) # Deduct points if over target
            rej_score = max(0, self.W_REJECTION - penalty)
            justification.append(f"Exceeds target TDS ({perm_tds:.1f} > {target_tds} mg/L).")
            if gap > 50 or rej_score == 0:
                dq = True
                dq_reason = "Cannot meet permeate quality requirements."
        
        criteria["rejection"] = round(rej_score, 1)
        score += rej_score
        
        # -----------------------------------------------------
        # 2. Hydraulic Limits (20 pts)
        # -----------------------------------------------------
        hyd_score = self.W_HYDRAULIC
        max_feed_limit = mem.get("max_feed_flow_m3h", 15.9)
        min_conc_limit = mem.get("min_concentrate_flow_m3h", 2.0)
        
        for idx, stage in enumerate(stages):
            vessel_feed = stage.get("max_vessel_feed", 0)
            vessel_conc = stage.get("min_vessel_conc", 99)
            if vessel_feed > max_feed_limit:
                hyd_score -= 10
                justification.append(f"Stage {idx+1} vessel feed ({vessel_feed:.1f} m3/h) exceeds membrane max ({max_feed_limit}).")
                dq = True
                dq_reason = "Vessel feed flow exceeds maximum limit."
            if vessel_conc < min_conc_limit:
                hyd_score -= 5
                justification.append(f"Stage {idx+1} vessel concentrate ({vessel_conc:.1f} m3/h) below membrane min ({min_conc_limit}).")
        
        hyd_score = max(0, hyd_score)
        criteria["hydraulic"] = round(hyd_score, 1)
        score += hyd_score
        
        # -----------------------------------------------------
        # 3. Energy Efficiency (30 pts)
        # -----------------------------------------------------
        sec = summary.get("sec_kwh_m3", 5.0)
        # Give max points for < 1.0 kWh/m3, and deduct gradually as it goes up.
        energy_score = max(0, min(self.W_ENERGY, self.W_ENERGY - (sec - 1.0) * 8))
        criteria["energy"] = round(energy_score, 1)
        score += energy_score
        justification.append(f"Specific Energy Consumption is {sec:.2f} kWh/m3.")
        
        # -----------------------------------------------------
        # 4. Operating Envelope & Beta (20 pts)
        # -----------------------------------------------------
        env_score = self.W_ENVELOPE
        feed_press = summary.get("feed_pressure_bar", 0)
        max_press = mem.get("max_pressure_bar", 41)
        
        if feed_press > max_press:
            env_score = 0
            dq = True
            dq_reason = f"Feed pressure ({feed_press:.1f} bar) exceeds max limit ({max_press} bar)."
        elif feed_press > max_press * 0.9:
            env_score -= 5
            justification.append("Operating near maximum pressure limit.")
            
        elements = ro.get("elements", [])
        max_beta = max([e.get("beta", 1.0) for e in elements] + [1.0])
        if max_beta > 1.20:
            env_score -= min(10, (max_beta - 1.20) * 50)
            justification.append(f"High concentration polarization (\u03b2={max_beta:.2f}). Ensure sufficient cross-flow.")
        
        # Determine application type suitability if necessary (e.g. SWRO vs BWRO)
        mem_type = mem.get("type", "BWRO")
        feed_tds = summary.get("feed_tds", 0)
        
        if source_type in ["SEAWATER", "SEAWATER_BEACH"] and mem_type != "SWRO":
            dq = True
            dq_reason = "Membrane type is not suitable for Seawater application."
        elif feed_tds > 20000 and mem_type != "SWRO":
            dq = True
            dq_reason = f"High salinity ({feed_tds:.0f} mg/L). SWRO is strictly required for >20,000 mg/L TDS."
        elif 15000 <= feed_tds <= 20000 and mem_type == "BWRO":
            justification.append(f"WARNING: High salinity transition zone ({feed_tds:.0f} mg/L). BWRO used but SWRO recommended for safety margin.")
            env_score -= 5
            
        env_score = max(0, env_score)
        criteria["envelope"] = round(env_score, 1)
        score += env_score
            
        return {
            "total": score,
            "is_disqualified": dq,
            "dq_reason": dq_reason,
            "max_beta": round(max_beta, 3),
            "criteria": criteria,
            "justification": justification
        }
