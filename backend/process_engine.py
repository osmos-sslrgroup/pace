from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import phreeqpython

class ProcessInputData(BaseModel):
    # Core
    feed_tds: float
    target_tds: float
    target_recovery: float
    feed_ph: Optional[float] = None
    feed_temp: Optional[float] = None
    source_type: Optional[str] = None
    
    # Fouling
    sdi_15: Optional[float] = None
    turbidity: Optional[float] = None
    toc: Optional[float] = None
    color_ptco: Optional[float] = None
    iron_total: Optional[float] = None
    manganese: Optional[float] = None
    free_cl2: Optional[float] = None
    oil_grease: Optional[float] = None
    cod: Optional[float] = None
    bod: Optional[float] = None
    
    # Ions
    ca: Optional[float] = 0.0
    mg_ion: Optional[float] = 0.0
    na: Optional[float] = 0.0
    cl: Optional[float] = 0.0
    so4: Optional[float] = 0.0
    hco3: Optional[float] = 0.0
    k: Optional[float] = 0.0
    ba: Optional[float] = 0.0
    sr: Optional[float] = 0.0
    f: Optional[float] = 0.0
    sio2: Optional[float] = 0.0
    boron: Optional[float] = 0.0
    no3: Optional[float] = 0.0
    po4: Optional[float] = 0.0
    nh4: Optional[float] = 0.0
    
    # Design Intent
    application: Optional[str] = None
    target_flow: Optional[float] = None

class ProcessRecommendationEngine:
    def __init__(self, pp_instance: phreeqpython.PhreeqPython):
        self.pp = pp_instance
        self.state = {
            "primary_config": None,
            "ro_variant": None,
            "second_pass_required": False,
            "second_pass_high_ph": False,
            "alternate_config": None,

            "scaling_risks": {},
            "flags": [],
            "pretreatment_flags": [],
            "confidence": {
                "score": 100,
                "level": "HIGH",
                "missing_inputs": []
            },
            "halt": False
        }

    def run(self, data: ProcessInputData) -> Dict[str, Any]:
        self.data = data

        self._phase_0_confidence()
        if self.state["halt"]: return self.state

        self._phase_1_source_type()
        if self.state["halt"]: return self.state

        self._phase_2_fouling()
        self._phase_3_primary_process()
        
        # Phase 4 only runs if we have ionic data to compute CF
        has_ions = sum([data.ca, data.mg_ion, data.na, data.so4, data.hco3, data.cl]) > 0
        if has_ions:
            self._phase_4_scaling()
        else:
            self.state["confidence"]["score"] -= 20
            self.state["confidence"]["missing_inputs"].append("ionic_data")
            self._update_confidence_level()
            self.state["flags"].append("RECOVERY UNVERIFIED: Missing ionic data. Phase 4 skipped.")


        self._phase_5_permeate_quality()
        self._phase_6_nf_refinement()
        self._phase_7_final_assembly()

        return self.state

    def _add_flag(self, text: str):
        self.state["flags"].append(text)

    def _add_pre_flag(self, text: str):
        self.state["pretreatment_flags"].append(text)

    def _update_confidence_level(self):
        s = self.state["confidence"]["score"]
        if s >= 80: self.state["confidence"]["level"] = "HIGH"
        elif s >= 55: self.state["confidence"]["level"] = "MEDIUM"
        else: self.state["confidence"]["level"] = "LOW"

    def _phase_0_confidence(self):
        d = self.data
        c = self.state["confidence"]
        if d.feed_ph is None:
            d.feed_ph = 7.5
            c["score"] -= 10
            c["missing_inputs"].append("feed_ph")
            self._add_flag("Default pH 7.5 applied. Carbonate scaling risk may be underestimated.")
        
        if d.sdi_15 is None and d.turbidity is None:
            c["score"] -= 12
            c["missing_inputs"].extend(["sdi_15", "turbidity"])
            
        if d.feed_temp is None:
            d.feed_temp = 25.0
            c["score"] -= 5
            c["missing_inputs"].append("feed_temp")
            
        if d.application is None:
            c["score"] -= 5
            c["missing_inputs"].append("application")
            
        self._update_confidence_level()

    def _phase_1_source_type(self):
        d = self.data
        if d.source_type is None:
            if d.feed_tds > 20000: d.source_type = "SEAWATER"
            elif d.feed_tds > 3000: d.source_type = "BRACKISH_GW"
            elif d.feed_tds <= 3000 and ((d.turbidity or 0) > 2 or (d.toc or 0) > 5): d.source_type = "SURFACE"
            else: d.source_type = "LOW_TDS"
            self.state["confidence"]["score"] -= 10
            self.state["confidence"]["missing_inputs"].append("source_type")
            self._update_confidence_level()
        
        st = d.source_type.upper()
        if "WW" in st or "WASTEWATER" in st:
            if (d.cod and d.cod > 150) or (d.bod and d.bod > 20):
                self._add_pre_flag("HALT: High biological loading (BOD > 20 or COD > 150). Biological pretreatment required.")
                self.state["halt"] = True
                return
        
        if d.oil_grease and d.oil_grease > 5:
            self._add_pre_flag("HALT: Oil and grease > 5 mg/L. DAF or separator pretreatment required.")
            self.state["halt"] = True
            return

    def _phase_2_fouling(self):
        d = self.data
        uf_mandatory = False
        uf_recommended = False
        
        # SDI checks
        if d.sdi_15 is not None:
            if d.sdi_15 > 5: uf_mandatory = True
            elif d.sdi_15 > 3: uf_mandatory = True
            elif d.sdi_15 > 1 and ("SURFACE" in (d.source_type or "").upper() or "WW" in (d.source_type or "").upper()):
                uf_mandatory = True
        else:
            if d.turbidity is not None:
                if d.turbidity > 1.0: uf_mandatory = True
                elif d.turbidity > 0.5: uf_recommended = True
            elif "SURFACE" in (d.source_type or "").upper():
                uf_mandatory = True
                self._add_flag("UF mandated due to surface water source type with missing SDI/Turbidity.")

        # Organics & Metals
        if d.toc and d.toc > 10:
            uf_mandatory = True
            self._add_pre_flag("TOC > 10 mg/L. Biofouling control required.")
        elif d.toc and d.toc > 5:
            uf_recommended = True
            
        if d.color_ptco and d.color_ptco > 50:
            uf_mandatory = True
            self._add_flag("High colour indicates potential humic substances. NF may be suitable.")
            
        if d.iron_total and d.iron_total > 0.3:
            uf_mandatory = True
            self._add_pre_flag("Iron > 0.3 mg/L. Oxidation and filtration required upstream.")
            
        if d.manganese and d.manganese > 0.05:
            self._add_pre_flag("Manganese > 0.05 mg/L. Oxidation pretreatment required.")
            
        if d.free_cl2 and d.free_cl2 > 0.1:
            self._add_pre_flag("Free Chlorine > 0.1 mg/L. Dechlorination required (SMBS or Carbon).")
            
        if d.oil_grease and d.oil_grease >= 1 and d.oil_grease <= 5:
            uf_mandatory = True
            
        if "WW" in (d.source_type or "").upper():
            uf_mandatory = True

        self.state["uf_integration"] = uf_mandatory or uf_recommended

    def _phase_3_primary_process(self):
        tds = self.data.feed_tds
        if tds < 200:
            config = "NF"
            pclass = None
        elif tds <= 500:
            config = "NF"
            pclass = "BWRO-LP"
        elif tds <= 2000:
            # Draft NF for brackish water up to 2000 ppm. 
            # Phase 6 will automatically upgrade to RO if the target TDS requires higher rejection.
            config = "NF"
            pclass = "BWRO-LP"
        elif tds <= 5000:
            config = "RO"
            pclass = "BWRO-MP"
        elif tds <= 10000:
            config = "RO"
            pclass = "BWRO-HP"
        elif tds <= 35000:
            config = "RO"
            pclass = "HP-BWRO"
        else:
            config = "RO"
            pclass = "SWRO"
            self._add_flag("ERD strongly recommended for SWRO systems > 500 m3/day.")
            
        self.state["primary_config_draft"] = config
        self.state["ro_variant"] = pclass

    def _run_phreeqc_cf(self, cf: float) -> dict:
        d = self.data
        sol = self.pp.add_solution({
            'units': 'mg/L',
            'temp': d.feed_temp,
            'pH': d.feed_ph,
            'Ca': (d.ca or 0) * cf,
            'Mg': (d.mg_ion or 0) * cf,
            'Na': (d.na or 0) * cf,
            'K': (d.k or 0) * cf,
            'Cl': (d.cl or 0) * cf,
            'S(6)': f"{(d.so4 or 0) * cf} as SO4",
            'Alkalinity': f"{(d.hco3 or 0) * cf} as CaCO3",
            'Ba': (d.ba or 0) * cf,
            'Sr': (d.sr or 0) * cf,
            'F': (d.f or 0) * cf,
            'Si': f"{(d.sio2 or 0) * cf} as SiO2",
            'N(-3)': f"{(d.nh4 or 0) * cf} as NH4",
            'N(5)': f"{(d.no3 or 0) * cf} as NO3",
            'P': f"{(d.po4 or 0) * cf} as PO4"
        })
        
        res = {
            "Calcite": sol.si("Calcite"),
            "Gypsum": sol.si("Gypsum"),
            "Anhydrite": sol.si("Anhydrite"),
            "Barite": sol.si("Barite"),
            "Celestite": sol.si("Celestite"),
            "Fluorite": sol.si("Fluorite"),
            "SiO2(a)": sol.si("SiO2(a)"),
            "Aragonite": sol.si("Aragonite"),
            "Dolomite": sol.si("Dolomite")
        }
        sol.forget()
        return res

    def _eval_scaling(self, sis: dict) -> dict:
        limits = {
            "Calcite": {"mod": 0.0, "high": 0.5, "crit": 1.0},
            "Gypsum": {"mod": 0.0, "high": 0.3, "crit": 0.5},
            "Anhydrite": {"mod": 0.0, "high": 0.3, "crit": 0.5},
            "Barite": {"mod": -0.2, "high": 0.0, "crit": 0.3},
            "Celestite": {"mod": 0.0, "high": 0.2, "crit": 0.4},
            "Fluorite": {"mod": 0.0, "high": 0.5, "crit": 0.5},
            "SiO2(a)": {"mod": -0.1, "high": 0.0, "crit": 0.2}
        }
        
        risks = {}
        has_crit = False
        limiting = None
        
        for minr, sival in sis.items():
            if sival <= -99.0: continue
            risk = "NONE"
            if minr in limits:
                if sival > limits[minr]["crit"]:
                    risk = "CRITICAL"
                    has_crit = True
                    limiting = minr
                elif sival > limits[minr]["high"]: risk = "HIGH"
                elif sival > limits[minr]["mod"]: risk = "MODERATE"
                elif sival > limits[minr]["mod"] - 0.2: risk = "LOW"
            else:
                if sival > -0.3: risk = "INFORMATIONAL"
            
            if risk != "NONE":
                risks[minr] = {"si": round(sival, 3), "risk": risk}
                
        return risks, has_crit, limiting

    def _phase_4_scaling(self):
        target = self.data.target_recovery
        
        cf = 1 / (1 - target / 100)
        sis = self._run_phreeqc_cf(cf)
        risks, has_crit, limiting = self._eval_scaling(sis)
            
        self.state["scaling_risks"] = risks
        
        if has_crit:
            self._add_flag(f"CRITICAL {limiting} scaling detected at {target}% target recovery. Recovery may not be feasible.")
            
            if limiting == "SiO2(a)":
                self.state["high_ph_ro_hint"] = True
                self._add_flag("High pH RO configuration hinted: critical silica scaling detected.")

    def _phase_5_permeate_quality(self):
        tds = self.data.feed_tds
        pclass = self.state["ro_variant"]
        
        if pclass == "SWRO": rej = 0.995
        elif pclass == "HP-BWRO": rej = 0.985
        else: rej = 0.980
        
        est_ro_tds = tds * (1 - rej)
        
        two_pass = False
        
        if est_ro_tds > self.data.target_tds * 1.1:
            two_pass = True
            self._add_flag(f"Estimated single-pass TDS ({est_ro_tds:.0f}) exceeds target ({self.data.target_tds}).")
            
        app = (self.data.application or "").upper()
        if app in ["UPW", "PHARMA", "BOILER_FEED"]:
            if app == "BOILER_FEED" and self.data.target_tds > 10:
                pass # High pressure boiler
            else:
                two_pass = True
                self._add_flag(f"Application '{app}' mandates Two-Pass RO.")
                
        if self.data.boron and self.data.boron > 1.0: # simplistic check, spec says below 0.5 needs high pH
            if app == "DRINKING" or True: # if target < 0.5
                two_pass = True
                self.state["second_pass_high_ph"] = True
                self._add_flag("Boron removal requires 2P-RO with caustic dosing (pH 9.5-10.5).")
                
        self.state["second_pass_required"] = two_pass

    def _phase_6_nf_refinement(self):
        if self.state["primary_config_draft"] == "NF":
            est_nf_tds = self.data.feed_tds * (1 - 0.6)
            
            override = False
            override_reason = ""
            
            # Hard-override NF to RO for two-pass or strict applications
            if self.state["second_pass_required"]:
                override = True
                override_reason = "Two-pass requirement overrides NF. Upgrading to RO."
                
            app = (self.data.application or "").upper()
            if app in ["UPW", "PHARMA", "BOILER_FEED"]:
                if self.data.target_tds < 50:
                    override = True
                    override_reason = f"Application '{app}' with tight TDS overrides NF. Upgrading to RO."
            
            # Upgrade to RO if NF estimated permeate TDS exceeds target TDS
            if not override and est_nf_tds > self.data.target_tds * 1.1:
                override = True
                override_reason = f"NF estimated permeate TDS ({est_nf_tds:.0f} mg/L) exceeds target ({self.data.target_tds} mg/L). Upgrading to RO for strict permeate quality."
                
            if override:
                self.state["primary_config_draft"] = "RO"
                if override_reason:
                    self._add_flag(override_reason)
            else:
                self._add_flag(f"NF confirmed suitable. Estimated permeate TDS: {est_nf_tds:.0f} mg/L. "
                               f"NF offers higher recovery at lower operating pressure for this feed.")

    def _phase_7_final_assembly(self):
        draft = self.state["primary_config_draft"]
        uf = self.state.get("uf_integration", False)
        tp = self.state["second_pass_required"]
        
        if draft == "NF":
            self.state["primary_config"] = "NF"
            self.state["alternate_config"] = "RO"
            if uf: self._add_pre_flag("UF recommended upstream of NF.")
        elif draft == "RO":
            if not tp and not uf:
                self.state["primary_config"] = "RO"
                self.state["alternate_config"] = "UF+RO"
            elif not tp and uf:
                self.state["primary_config"] = "UF+RO"
                self.state["alternate_config"] = "RO with enhanced cartridge filtration"
            elif tp and not uf:
                self.state["primary_config"] = "2P-RO"
                self.state["alternate_config"] = "RO + EDI/MB"
            elif tp and uf:
                self.state["primary_config"] = "UF+RO"
                self.state["alternate_config"] = "2P-RO with enhanced cartridge filtration"
                
        app = (self.data.application or "").upper()
        if app == "ZLD":
            self._add_flag("ZLD Application: RO max recovery 85%. Downstream brine concentrator/crystalliser required.")
            
        if self.state.get("high_ph_ro_hint"):
            self.state["primary_config"] = "High pH RO"
            self.state["alternate_config"] = "UF+RO (at reduced recovery)"
