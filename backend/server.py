from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import phreeqpython
from process_engine import ProcessInputData, ProcessRecommendationEngine
from process_engine import ProcessInputData, ProcessRecommendationEngine
from system_engine import SystemEngine
from membrane_database import MembraneDatabase
from report_generator import ReportGenerator
from membrane_recommender import MembraneRecommender
from aging_engine import AgingEngine
from typing import List, Optional, Dict
from fastapi.responses import FileResponse, RedirectResponse
import os

app = FastAPI(title="PHREEQC Scaling Engine API")

import base64

class BasicAuthASGIMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        method = scope.get("method")
        if method == "OPTIONS":
            await self.app(scope, receive, send)
            return

        headers = scope.get("headers", [])
        # Only apply authentication to API endpoints
        if not scope.get("path", "").startswith("/api/"):
            await self.app(scope, receive, send)
            return

        auth_header = None
        for name, value in headers:
            if name == b"authorization":
                auth_header = value.decode("utf-8")
                break

        authorized = False
        if auth_header:
            try:
                auth_type, encoded_creds = auth_header.split(" ", 1)
                if auth_type.lower() == "basic":
                    decoded_creds = base64.b64decode(encoded_creds).decode("utf-8")
                    username, password = decoded_creds.split(":", 1)
                    expected_user = os.environ.get("API_USERNAME", "pace_permionics")
                    expected_pass = os.environ.get("API_PASSWORD", "satyaraj_permionics@2026")
                    if username == expected_user and password == expected_pass:
                        authorized = True
            except Exception:
                pass

        if authorized:
            await self.app(scope, receive, send)
        else:
            await self.send_unauthorized(send)

    async def send_unauthorized(self, send):
        await send({
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"text/plain"),
            ]
        })
        await send({
            "type": "http.response.body",
            "body": b"Unauthorized",
        })

# Add Basic Auth Middleware first
app.add_middleware(BasicAuthASGIMiddleware)

# Allow CORS for the frontend to communicate with the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize PHREEQC engine
pp = phreeqpython.PhreeqPython(database='phreeqc.dat')

class FeedWaterData(BaseModel):
    temperature: float = 25.0
    ph: float = 7.0
    calcium: float = 0.0
    magnesium: float = 0.0
    sodium: float = 0.0
    chloride: float = 0.0
    sulfate: float = 0.0
    bicarbonate: float = 0.0
    strontium: float = 0.0
    fluoride: float = 0.0
    silica: float = 0.0
    barium: float = 0.0
    potassium: float = 0.0
    ammonium: float = 0.0
    carbonate: float = 0.0
    nitrate: float = 0.0
    aluminium: float = 0.0
    iron: float = 0.0
    manganese: float = 0.0
    phosphate: float = 0.0
    tss: Optional[float] = 0.0
    turbidity: Optional[float] = 0.0
    tds: Optional[float] = 0.0

class AutoBalanceInput(BaseModel):
    calcium: float = 0.0
    magnesium: float = 0.0
    sodium: float = 0.0
    potassium: float = 0.0
    ammonium: float = 0.0
    barium: float = 0.0
    strontium: float = 0.0
    chloride: float = 0.0
    sulfate: float = 0.0
    bicarbonate: float = 0.0
    carbonate: float = 0.0
    nitrate: float = 0.0
    fluoride: float = 0.0
    phosphate: float = 0.0
    silica: float = 0.0
    ph: float = 7.0
    temperature: float = 25.0

class BalanceResult(BaseModel):
    status: str
    cbe_meq: float
    cbe_pct: float
    sum_cations_meq: float
    sum_anions_meq: float
    injected_ion: Optional[str] = None
    injected_amount_mg_l: float = 0.0
    na_final: float
    cl_final: float
    message: str

class EconomicParams(BaseModel):
    electricity_tariff: float = 7.50
    membrane_cost: float = 26880.0
    vessel_cost: float = 48000.0
    pump_cost_kw: float = 96000.0
    ic_factor: float = 0.15
    contingency_factor: float = 0.10
    plant_availability: float = 0.90
    membrane_lifetime: float = 5.0
    discount_rate: float = 0.10
    project_life: float = 20.0
    uf_module_cost: Optional[float] = None        # ₹/module — user override; falls back to DB value if None
    uf_membrane_lifetime: float = 7.0             # UF module replacement interval in years

class PassConfig(BaseModel):
    membrane: str
    stages: int
    vessels_per_stage: List[int]
    elements_per_vessel: int
    target_recovery_pct: float

class ConditioningConfig(BaseModel):
    enabled: bool = False
    target_ph: Optional[float] = None
    chemical: Optional[str] = None
    co2_degassing: bool = False

class RecycleConfig(BaseModel):
    enabled: bool = False
    recycle_ratio: float = 0.0

class SystemCalcInput(BaseModel):
    technology_train: str
    feed_water: dict
    target_flow_m3h: float
    target_recovery_pct: float
    target_tds: Optional[float] = 50.0
    source_type: Optional[str] = "LOW_TDS"
    ro_membrane: str
    uf_module: Optional[str] = None
    stages: int
    vessels_per_stage: List[int]
    elements_per_vessel: int
    economic_params: Optional[EconomicParams] = None
    recycle_enabled: Optional[bool] = False
    recycle_ratio: Optional[float] = 0.0
    pass1: Optional[PassConfig] = None
    pass2: Optional[PassConfig] = None
    conditioning: Optional[ConditioningConfig] = None
    recycle: Optional[RecycleConfig] = None
    aging_results: Optional[dict] = None
    pfd_svg: Optional[str] = None
    pfd_png: Optional[str] = None
    project_details: Optional[dict] = None
    # Physics projection results (attached by JS from window.lastPhysicsResult)
    physics_results: Optional[dict] = None
    physics_selected_year: Optional[int] = 0
    units: Optional[dict] = None

@app.get("/")
def read_root():
    return RedirectResponse(url="/index.html")

@app.post("/api/verify-auth")
def verify_auth():
    return {"status": "success"}

@app.post("/api/calculate-scaling")
def calculate_scaling(data: FeedWaterData):
    try:
        # Create a new solution
        sol = pp.add_solution({
            'units': 'mg/L',
            'temp': data.temperature,
            'pH': data.ph,
            'Ca': data.calcium,
            'Mg': data.magnesium,
            'Na': data.sodium,
            'K': data.potassium,
            'N(-3)': f"{data.ammonium} as NH4",
            'Cl': data.chloride,
            'S(6)': f"{data.sulfate} as SO4",
            'Alkalinity': f"{data.bicarbonate} as HCO3",
            'N(5)': f"{data.nitrate} as NO3",
            'Sr': data.strontium,
            'F': data.fluoride,
            'Si': f"{data.silica} as SiO2",
            'Ba': data.barium,
            'Al': data.aluminium,
            'Fe': data.iron,
            'Mn': data.manganese,
            'P': f"{data.phosphate} as PO4"
        })
        
        # Retrieve saturation indices (SI)
        results = {
            "gypsum_si": sol.si("Gypsum"),
            "calcite_si": sol.si("Calcite"),
            "aragonite_si": sol.si("Aragonite"),
            "barite_si": sol.si("Barite"),
            "lsi": sol.si("Calcite"), # LSI is approximated by Calcite SI in pure systems
            "celestite_si": sol.si("Celestite"),
            "fluorite_si": sol.si("Fluorite"),
            "anhydrite_si": sol.si("Anhydrite"),
            "silica_si": sol.si("SiO2(a)"),
            "iron_si": sol.si("Fe(OH)3(a)"),
            "aluminium_si": sol.si("Al(OH)3(a)"),
            "manganese_si": sol.si("Pyrolusite"),
            "calcium_phosphate_si": sol.si("Hydroxyapatite")
        }
        
        # We can also calculate LSI more specifically if needed, but Calcite SI is the rigorous thermodynamic equivalent.
        
        # Clean up memory
        sol.forget()
        
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auto-balance", response_model=BalanceResult)
def auto_balance(data: AutoBalanceInput):
    """
    Computes the Charge Balance Error (CBE) of the feed water analysis.
    If the charge imbalance is greater than 2%, it automatically balances the water 
    by injecting either Sodium (Na+) or Chloride (Cl-) depending on whether the 
    imbalance is anion-heavy or cation-heavy.
    """
    try:
        mw_ca, z_ca = 40.08, 2
        mw_mg, z_mg = 24.31, 2
        mw_na, z_na = 22.99, 1
        mw_k, z_k = 39.10, 1
        mw_nh4, z_nh4 = 18.04, 1
        mw_ba, z_ba = 137.33, 2
        mw_sr, z_sr = 87.62, 2
        
        mw_cl, z_cl = 35.45, 1
        mw_so4, z_so4 = 96.06, 2
        mw_hco3, z_hco3 = 61.02, 1
        mw_co3, z_co3 = 60.01, 2
        mw_no3, z_no3 = 62.00, 1
        mw_f, z_f = 19.00, 1
        mw_po4, z_po4 = 94.97, 3
        
        # True HCO3- and CO3-- input
        hco3_meq = (data.bicarbonate / mw_hco3) * z_hco3
        co3_meq = (data.carbonate / mw_co3) * z_co3
            
        cat_meq = (
            (data.calcium / mw_ca) * z_ca +
            (data.magnesium / mw_mg) * z_mg +
            (data.sodium / mw_na) * z_na +
            (data.potassium / mw_k) * z_k +
            (data.ammonium / mw_nh4) * z_nh4 +
            (data.barium / mw_ba) * z_ba +
            (data.strontium / mw_sr) * z_sr
        )
        
        an_meq = (
            (data.chloride / mw_cl) * z_cl +
            (data.sulfate / mw_so4) * z_so4 +
            hco3_meq + co3_meq +
            (data.nitrate / mw_no3) * z_no3 +
            (data.fluoride / mw_f) * z_f +
            (data.phosphate / mw_po4) * z_po4
        )
        
        cbe_meq = cat_meq - an_meq
        denom = max(cat_meq + an_meq, 0.1)
        cbe_pct = (cbe_meq / denom) * 100
        
        abs_cbe_pct = abs(cbe_pct)
        status = "BALANCED"
        injected_ion = None
        injected_amount = 0.0
        na_final = data.sodium
        cl_final = data.chloride
        message = f"Feed water is balanced. CBE is {cbe_pct:.2f}%."
        
        if abs_cbe_pct <= 2.0:
            status = "BALANCED"
        else:
            status = "ADJUSTED"
            if cbe_meq > 0:
                injected_ion = "Cl"
                injected_amount = cbe_meq * (mw_cl / z_cl)
                cl_final += injected_amount
                message = f"Cl⁻ auto-added: {injected_amount:.2f} mg/L to balance charge."
            else:
                injected_ion = "Na"
                injected_amount = abs(cbe_meq) * (mw_na / z_na)
                na_final += injected_amount
                message = f"Na⁺ auto-added: {injected_amount:.2f} mg/L to balance charge."
            
        return BalanceResult(
            status=status,
            cbe_meq=cbe_meq,
            cbe_pct=cbe_pct,
            sum_cations_meq=cat_meq,
            sum_anions_meq=an_meq,
            injected_ion=injected_ion,
            injected_amount_mg_l=injected_amount,
            na_final=na_final,
            cl_final=cl_final,
            message=message
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/process-recommendation")
def process_recommendation(data: ProcessInputData):
    try:
        engine = ProcessRecommendationEngine(pp)
        result = engine.run(data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/calculate-system")
def calculate_system(data: SystemCalcInput):
    """
    Triggers the RO system simulation.
    Handles three configuration routes:
    1. Two-pass RO systems (2P-RO) by executing Pass 1 and Pass 2 sequentially.
    2. Recycle-loop systems where concentrate is partially recycled back to the feed.
    3. Standard Single-pass RO systems (1P-RO).
    """
    try:
        print("CALCULATE SYSTEM INPUT PAYLOAD:", data.dict())
        engine = SystemEngine()
        input_dict = data.dict()
        
        if "2P-RO" in data.technology_train:
            result = engine.simulate_two_pass_system(input_dict)
            if result and "pass1_results" in result and result["pass1_results"]:
                import copy
                ro_res = copy.deepcopy(result["pass1_results"])
                
                # Override summary with overall system metrics
                sys_sum = result.get("system_summary", {})
                if "summary" in ro_res:
                    ro_res["summary"]["total_recovery"] = sys_sum.get("overall_recovery", ro_res["summary"].get("total_recovery", 0.0))
                    ro_res["summary"]["perm_flow"] = sys_sum.get("final_permeate_flow_m3h", ro_res["summary"].get("perm_flow", 0.0))
                    ro_res["summary"]["perm_tds"] = sys_sum.get("final_permeate_tds", ro_res["summary"].get("perm_tds", 0.0))
                    ro_res["summary"]["sec_kwh_m3"] = sys_sum.get("sec_kwh_m3", ro_res["summary"].get("sec_kwh_m3", 0.0))
                    # Patch combined power so OPEX energy is correct for both passes
                    ro_res["summary"]["total_power_kw"] = sys_sum.get("total_power_kw", ro_res["summary"].get("total_power_kw", 0.0))
                
                # Combine warnings from both passes
                all_warnings = list(ro_res.get("warnings", []))
                if "pass2_results" in result and result["pass2_results"]:
                    for w in result["pass2_results"].get("warnings", []):
                        w_copy = dict(w)
                        w_copy["type"] = f"Pass 2: {w_copy.get('type')}"
                        all_warnings.append(w_copy)
                ro_res["warnings"] = all_warnings
                
                result["ro_results"] = ro_res
                
                # Use the two-pass economics (already covers both passes' membranes + pumps)
                # rather than letting the frontend recompute from Pass 1 only
                if result.get("economics"):
                    result["economics"] = result["economics"]

        elif data.recycle_enabled and data.recycle_ratio and data.recycle_ratio > 0:
            result = engine.calculate_system_with_recycle(input_dict)
        else:
            result = engine.calculate_system(input_dict)

        # ── Compute PHREEQC concentrate SI for all calculation paths ─────────
        # Dynamically compute the exact concentrate pH by solving the carbonate
        # equilibrium shift from the feed pH using the concentration factor of HCO3.
        try:
            ro_main = result.get("ro_results") or result.get("pass1_results") or result
            conc_ions = ro_main.get("summary", {}).get("conc_ions", {})
            fw = data.feed_water if isinstance(data.feed_water, dict) else (data.feed_water.dict() if hasattr(data.feed_water, "dict") else vars(data.feed_water))
            temp_c = float(fw.get("temperature", 25.0))
            feed_ph = float(fw.get("ph", 7.0))
            if conc_ions:
                import math
                feed_hco3 = float(fw.get("bicarbonate", 0.0))
                conc_hco3 = conc_ions.get("HCO3", 0)
                
                est_conc_ph = feed_ph
                if feed_hco3 and feed_hco3 > 0 and conc_hco3 > 0:
                    est_conc_ph += math.log10(conc_hco3 / feed_hco3)
                else:
                    target_rec = data.target_recovery_pct if hasattr(data, "target_recovery_pct") else data.get("target_recovery_pct", 75.0)
                    rec_frac = float(target_rec) / 100.0
                    cf = 1.0 / max(1.0 - rec_frac, 0.05)
                    est_conc_ph += math.log10(cf)
                    
                est_conc_ph = min(max(est_conc_ph, 0.0), 14.0)

                sol_input = {
                    'pH': est_conc_ph,
                    'units': 'mg/L',
                    'temp': temp_c,
                    'Ca':    conc_ions.get("Ca",   0),
                    'Mg':    conc_ions.get("Mg",   0),
                    'Na':    conc_ions.get("Na",   0),
                    'K':     conc_ions.get("K",    0),
                    'N(-3)': f"{conc_ions.get('NH4', 0)} as NH4",
                    'Cl':    conc_ions.get("Cl",   0),
                    'S(6)':  f"{conc_ions.get('SO4', 0)} as SO4",
                    'Alkalinity': f"{conc_ions.get('HCO3', 0)} as HCO3",
                    'N(5)':  f"{conc_ions.get('NO3', 0)} as NO3",
                    'Sr':    conc_ions.get("Sr",   0),
                    'F':     conc_ions.get("F",    0),
                    'Si':    f"{conc_ions.get('SiO2', 0)} as SiO2",
                    'Ba':    conc_ions.get("Ba",   0),
                    'Al':    conc_ions.get("Al",   0),
                    'Fe':    conc_ions.get("Fe",   0),
                    'Mn':    conc_ions.get("Mn",   0),
                    'P':     f"{conc_ions.get('PO4', 0)} as PO4",
                }
                sol = pp.add_solution(sol_input)
                result["concentrate_ph"] = round(sol.pH, 2)
                result["concentrate_si"] = {
                    "Calcite":   round(sol.si("Calcite"),   3),
                    "Aragonite": round(sol.si("Aragonite"), 3),
                    "Dolomite":  round(sol.si("Dolomite"),  3),
                    "Gypsum":    round(sol.si("Gypsum"),    3),
                    "Anhydrite": round(sol.si("Anhydrite"), 3),
                    "Barite":    round(sol.si("Barite"),    3),
                    "Celestite": round(sol.si("Celestite"), 3),
                    "Fluorite":  round(sol.si("Fluorite"),  3),
                    "SiO2(a)":   round(sol.si("SiO2(a)"),  3),
                }
                sol.forget()
                
            if fw:
                sol_feed_input = {
                    'units': 'mg/L',
                    'temp': temp_c,
                    'pH': feed_ph,
                    'Ca': float(fw.get("calcium", 0)),
                    'Mg': float(fw.get("magnesium", 0)),
                    'Na': float(fw.get("sodium", 0)),
                    'K': float(fw.get("potassium", 0)),
                    'N(-3)': f"{float(fw.get('ammonium', 0))} as NH4",
                    'Cl': float(fw.get("chloride", 0)),
                    'S(6)': f"{float(fw.get('sulfate', 0))} as SO4",
                    'Alkalinity': f"{float(fw.get('bicarbonate', 0))} as HCO3",
                    'N(5)': f"{float(fw.get('nitrate', 0))} as NO3",
                    'Sr': float(fw.get("strontium", 0)),
                    'F': float(fw.get("fluoride", 0)),
                    'Si': f"{float(fw.get('silica', 0))} as SiO2",
                    'Ba': float(fw.get("barium", 0)),
                    'Al': float(fw.get("aluminium", 0)),
                    'Fe': float(fw.get("iron", 0)),
                    'Mn': float(fw.get("manganese", 0)),
                    'P': f"{float(fw.get('phosphate', 0))} as PO4",
                }
                sol_feed = pp.add_solution(sol_feed_input)
                result["feed_si"] = {
                    "Calcite":   round(sol_feed.si("Calcite"),   3),
                    "Aragonite": round(sol_feed.si("Aragonite"), 3),
                    "Dolomite":  round(sol_feed.si("Dolomite"),  3),
                    "Gypsum":    round(sol_feed.si("Gypsum"),    3),
                    "Anhydrite": round(sol_feed.si("Anhydrite"), 3),
                    "Barite":    round(sol_feed.si("Barite"),    3),
                    "Celestite": round(sol_feed.si("Celestite"), 3),
                    "Fluorite":  round(sol_feed.si("Fluorite"),  3),
                    "SiO2(a)":   round(sol_feed.si("SiO2(a)"),  3),
                }
                sol_feed.forget()

        except Exception as e:
            print("PHREEQC concentrate SI error in calculate-system:", e)

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auto-select-membrane")
def auto_select_membrane(data: SystemCalcInput):
    try:
        from membrane_recommender import MembraneRecommender
        
        recommender = MembraneRecommender()
        rec_result = recommender.recommend(data.dict())
        
        best_membrane = rec_result.get("best_membrane")
        
        # We need to return max_recovery for the frontend.
        # Since SystemEngine is used under the hood, the target recovery is essentially achieved.
        best_recovery = data.target_recovery_pct / 100.0
        
        return {"best_membrane": best_membrane, "max_recovery": best_recovery}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/membranes")
def list_membranes():
    try:
        return {
            "ro_membranes": MembraneDatabase.list_ro_membranes(),
            "uf_modules": MembraneDatabase.list_uf_modules()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate-calculation-report")
def generate_calc_report(data: SystemCalcInput):
    try:
        import tempfile, os

        engine = SystemEngine()
        input_dict = data.dict()

        if "2P-RO" in data.technology_train:
            result = engine.simulate_two_pass_system(input_dict)
        elif data.recycle_enabled and data.recycle_ratio and data.recycle_ratio > 0:
            result = engine.calculate_system_with_recycle(input_dict)
        else:
            result = engine.calculate_system(input_dict)

        # Attach project metadata for the report header
        result["project_name"] = getattr(data, "project_name", "PACE Report")
        if getattr(data, "aging_results", None):
            result["aging_results"] = data.aging_results
        if getattr(data, "pfd_svg", None):
            result["pfd_svg"] = data.pfd_svg
        if getattr(data, "pfd_png", None):
            result["pfd_png"] = data.pfd_png
        # Physics-based multi-year projection results
        if getattr(data, "physics_results", None):
            result["physics_results"] = data.physics_results
        if getattr(data, "physics_selected_year", None) is not None:
            result["physics_selected_year"] = data.physics_selected_year
        if getattr(data, "project_details", None):
            result["project_details"] = data.project_details
        if getattr(data, "units", None):
            result["units"] = data.units

        # Generate .docx to a temp file
        tmp_docx = tempfile.NamedTemporaryFile(
            suffix=".docx", delete=False,
            dir=tempfile.gettempdir(), prefix="PACE_report_"
        )
        tmp_docx.close()
        tmp_pdf = tmp_docx.name.replace(".docx", ".pdf")

        reporter = ReportGenerator()
        reporter.generate_calculation_report(result, tmp_docx.name)

        # Convert docx → PDF using libreoffice (Linux/Docker compatible) or fallback to docx2pdf (Windows local)
        import subprocess
        import sys
        
        temp_dir = tempfile.gettempdir()
        if sys.platform == "win32":
            # Fallback for local Windows testing without Docker
            script = f"from docx2pdf import convert; convert(r'{tmp_docx.name}', r'{tmp_pdf}')"
            res = subprocess.run(["python", "-c", script], capture_output=True, text=True)
            if res.returncode != 0:
                raise Exception(f"Windows PDF conversion failed: {res.stderr}")
        else:
            # Production Linux Docker environment using LibreOffice
            res = subprocess.run(["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", temp_dir, tmp_docx.name], capture_output=True, text=True)
            if res.returncode != 0:
                raise Exception(f"Linux PDF conversion failed: {res.stderr}")

        # Add Watermark for copyright purposes
        try:
            import fitz
            
            # Step 1: Create an image of the watermark
            temp_doc = fitz.open()
            fontsize = 80
            text = "PERMIONICS"
            text_w = fitz.get_text_length(text, fontname="helv", fontsize=fontsize)
            padding = 30
            w = int(text_w + 2 * padding)
            h = int(fontsize * 1.5)
            
            w_page = temp_doc.new_page(width=w, height=h)
            w_page.insert_text(
                fitz.Point(padding, h * 0.70), 
                text, 
                fontname="helv",
                fontsize=fontsize, 
                color=(0.6, 0.6, 0.6), 
                fill_opacity=0.15
            )
            matrix = fitz.Matrix(45)
            pix = w_page.get_pixmap(alpha=True, matrix=matrix)
            w = pix.width
            h = pix.height
            temp_doc.close()

            # Step 2: Overlay image onto actual PDF
            doc_pdf = fitz.open(tmp_pdf)
            for page in doc_pdf:
                rect = page.rect
                x0 = (rect.width - w) / 2
                y0 = (rect.height - h) / 2
                image_rect = fitz.Rect(x0, y0, x0 + w, y0 + h)
                page.insert_image(image_rect, pixmap=pix)
                
            doc_pdf.saveIncr()
            doc_pdf.close()
        except Exception as e:
            print("Watermarking failed:", e)

        # Clean up docx temp file
        try:
            os.unlink(tmp_docx.name)
        except Exception:
            pass

        from starlette.background import BackgroundTask
        return FileResponse(
            path=tmp_pdf,
            filename="PACE_Calculation_Report.pdf",
            media_type="application/pdf",
            background=BackgroundTask(os.unlink, tmp_pdf)
        )
    except Exception as e:
        import traceback
        raise HTTPException(status_code=500, detail=traceback.format_exc())

@app.post("/api/recommend-membrane")
def recommend_membrane(data: SystemCalcInput):
    """Returns ranked Permionics membrane recommendations with scores and rationale."""
    try:
        recommender = MembraneRecommender()
        result = recommender.recommend(data.dict())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── Aging Simulation Models ──

class AgingSystemConfig(BaseModel):
    membrane: str
    stages: int
    vessels_per_stage: List[int]
    elements_per_vessel: int
    target_recovery_pct: float

class AgingConfig(BaseModel):
    design_life_months: int = 60
    time_step_months: int = 1
    simulation_mode: str = "constant_recovery"
    cip_trigger: str = "scheduled"
    cip_interval_days: int = 90
    cip_type: str = "acid_alkaline_sequential"
    antiscalant_dosed: bool = True

class FeedHistory(BaseModel):
    sdi15: float = 3.0
    toc_mg_l: float = 2.0
    temperature_c: float = 28.0
    cl2_residual_mg_l: float = 0.0

class AgingSimInput(BaseModel):
    technology_train: str = "RO"
    feed_water: dict
    system_config: AgingSystemConfig
    aging_config: AgingConfig
    feed_history: FeedHistory
    target_flow_m3h: float = 10.0
    model_params: Optional[Dict[str, float]] = None


# ── Physics-Based Multi-Year Projection Models ──────────────────────────────

class PhysicsFeedQuality(BaseModel):
    """Feed quality parameters for physics-based projection.
    These are sourced from the Feed Data tab (SDI, TOC, Cl2, temperature).
    """
    sdi15: float = 3.0           # SDI-15 index (dimensionless)
    toc_mg_l: float = 2.0        # Total organic carbon (mg/L)
    cl2_residual_mg_l: float = 0.0  # Free chlorine post-SBS (mg/L)

class PhysicsCIPConfig(BaseModel):
    """CIP protocol configuration.
    interval_months = 0 means condition-triggered only (dynamic, no fixed schedule).
    The engine fires CIP when NPF < 0.85, P_ratio > 1.35, or FRI > 0.60.
    """
    acid_ph: float = 2.5
    alk_ph: float = 11.5
    interval_months: int = 0     # 0 = dynamic condition-triggered (recommended)
    duration_h: float = 4.0      # duration per CIP step

class PhysicsCalcInput(BaseModel):
    """Input for physics-based multi-year membrane performance projection.
    Contains all the same fields as SystemCalcInput plus physics-specific fields.
    """
    # -- Standard system config (same as SystemCalcInput) --
    technology_train: str
    feed_water: dict
    target_flow_m3h: float
    target_recovery_pct: float
    target_tds: Optional[float] = 50.0
    source_type: Optional[str] = "LOW_TDS"
    ro_membrane: str
    uf_module: Optional[str] = None
    stages: int
    vessels_per_stage: List[int]
    elements_per_vessel: int
    economic_params: Optional[EconomicParams] = None
    recycle_enabled: Optional[bool] = False
    recycle_ratio: Optional[float] = 0.0
    pass1: Optional[PassConfig] = None
    pass2: Optional[PassConfig] = None
    conditioning: Optional[ConditioningConfig] = None
    recycle: Optional[RecycleConfig] = None
    aging_results: Optional[dict] = None
    pfd_svg: Optional[str] = None
    pfd_png: Optional[str] = None

    # -- Physics-specific fields --
    projection_year: int = 0          # Selected year to display (0–5)
    n_years: int = 5                  # Total years to project
    feed_quality: Optional[PhysicsFeedQuality] = None
    cip_config: Optional[PhysicsCIPConfig] = None
    antiscalant_dosed: bool = True


# ── Shared projection core ──────────────────────────────────────────────────
# Both /api/simulate-aging and /api/calculate-system-physics call this
# single function. By construction, the inputs to PhysicsAgingEngine are
# IDENTICAL for the same physical scenario, making divergence impossible.

def _run_projection_core(
    *,
    feed_water: dict,
    technology_train: str,
    target_flow_m3h: float,
    target_recovery_pct: float,
    membrane: str,
    stages: int,
    vessels_per_stage: list,
    elements_per_vessel: int,
    n_years: int,
    sdi15: float,
    toc_mg_l: float,
    cl2_residual_mg_l: float,
    cip_interval_months: int,
    antiscalant_dosed: bool,
    recycle_enabled: bool = False,
    recycle_ratio: float = 0.0,
    # Sub-configuration objects — forwarded verbatim to the simulation engine
    # so that 2P-RO, UF+RO, NF, and any future train uses the correct config.
    pass1:        Optional[dict] = None,
    pass2:        Optional[dict] = None,
    conditioning: Optional[dict] = None,
    recycle:      Optional[dict] = None,
    uf_module:    Optional[str]  = None,
    ro_membrane_override: Optional[str] = None,  # per-pass membrane override
) -> dict:
    """Run the physics-based membrane aging projection.

    Returns a dict with keys: baseline (full system result), physics_results
    (PhysicsAgingEngine output), baseline_ro (RO-only results).
    """
    import copy
    from physics_aging_engine import PhysicsAgingEngine

    feed = feed_water

    # ── Ion extraction ───────────────────────────────────────────────────
    ions = {
        "Ca":  feed.get("calcium", 0),
        "Mg":  feed.get("magnesium", 0),
        "Na":  feed.get("sodium", 0),
        "K":   feed.get("potassium", 0),
        "Cl":  feed.get("chloride", 0),
        "SO4": feed.get("sulfate", 0),
        "HCO3":feed.get("bicarbonate", 0),
        "Ba":  feed.get("barium", 0),
        "Sr":  feed.get("strontium", 0),
        "F":   feed.get("fluoride", 0),
        "SiO2":feed.get("silica", 0),
        "B":   feed.get("boron", 0),
        "NO3": feed.get("nitrate", 0),
        "PO4": feed.get("phosphate", 0),
        "NH4": feed.get("ammonium", 0),
        "Al":  feed.get("aluminium", 0),
        "Fe":  feed.get("iron", 0),
        "Mn":  feed.get("manganese", 0),
    }

    temp_c = feed.get("temperature", 25.0)
    ph     = feed.get("ph", 7.0)

    # ── Baseline Year 0 calculation ──────────────────────────────────────
    # Build a complete input_dict that mirrors what the frontend sends to
    # /api/calculate-system.  This guarantees that:
    #   - pass1 / pass2 configs are used for 2P-RO (not defaults)
    #   - conditioning is applied between passes
    #   - recycle loop runs correctly for all technology trains
    #   - UF pre-treatment stage is included when present in the train
    engine = SystemEngine()
    input_dict = {
        "technology_train":    technology_train,
        "feed_water":          feed,
        "target_flow_m3h":     target_flow_m3h,
        "target_recovery_pct": target_recovery_pct,
        "ro_membrane":         membrane,
        "stages":              stages,
        "vessels_per_stage":   vessels_per_stage,
        "elements_per_vessel": elements_per_vessel,
        # Recycle flags — required by calculate_system_with_recycle
        "recycle_enabled":     recycle_enabled,
        "recycle_ratio":       recycle_ratio,
    }
    if uf_module:    input_dict["uf_module"]    = uf_module
    if pass1:        input_dict["pass1"]        = pass1
    if pass2:        input_dict["pass2"]        = pass2
    if conditioning: input_dict["conditioning"] = conditioning
    if recycle:      input_dict["recycle"]      = recycle

    if "2P-RO" in technology_train:
        baseline = engine.simulate_two_pass_system(input_dict)
        if baseline and "pass1_results" in baseline and baseline["pass1_results"]:
            ro_res = copy.deepcopy(baseline["pass1_results"])
            sys_sum = baseline.get("system_summary", {})
            if "summary" in ro_res:
                ro_res["summary"]["total_recovery"] = sys_sum.get("overall_recovery", ro_res["summary"].get("total_recovery", 0.0))
                ro_res["summary"]["perm_flow"] = sys_sum.get("final_permeate_flow_m3h", ro_res["summary"].get("perm_flow", 0.0))
                ro_res["summary"]["perm_tds"] = sys_sum.get("final_permeate_tds", ro_res["summary"].get("perm_tds", 0.0))
                ro_res["summary"]["sec_kwh_m3"] = sys_sum.get("sec_kwh_m3", ro_res["summary"].get("sec_kwh_m3", 0.0))
            baseline["ro_results"] = ro_res
    elif recycle_enabled and recycle_ratio and recycle_ratio > 0:
        baseline = engine.calculate_system_with_recycle(input_dict)
    else:
        baseline = engine.calculate_system(input_dict)

    # For physics simulation, we MUST use the pure Pass 1 parameters (flow, recovery, TDS)
    # so that the simulated fouled permeate TDS matches the physics equations.
    physics_baseline_ro = baseline.get("pass1_results") or baseline.get("ro_results") or baseline

    # For the UI presentation baseline, we use the merged system properties.
    baseline_ro = baseline.get("ro_results") or baseline.get("pass1_results") or baseline

    # ── Recycle: blended feed ion concentrations for physics engine ──────
    # Industry-standard approach: use the ACTUAL converged blended feed ions
    # from the iterative steady-state solver as the basis for fouling/scaling
    # calculations.  This eliminates the Year 0 vs Year 1+ mismatch that
    # arises from the previous analytical TDS-scaling approximation.
    #
    # Extraction logic (covers all technology trains):
    #   2P-RO (any UF prefix):  baseline["recycle"]["blended_feed_ions"]
    #   RO / UF+RO / NF / UF+NF: baseline["recycle"]["blended_feed_ions"]
    #     (set by calculate_system_with_recycle from the converged c_blend)
    #   Fallback (solver data unavailable): analytical CF-scaling approximation
    recycle_feed_ions = None
    if recycle_enabled and recycle_ratio and recycle_ratio > 0:
        # Primary: extract from solver result (accurate, ion-specific)
        rec_info = baseline.get("recycle", {})
        blended_ions = rec_info.get("blended_feed_ions")
        if blended_ions:
            recycle_feed_ions = blended_ions
        else:
            # Secondary: reconstruct from blended feed_water_used (1P-RO path)
            bf = baseline.get("feed_water_used", {})
            if bf and bf.get("tds", 0) > feed.get("tds", 0):  # only if it was actually blended
                recycle_feed_ions = {
                    "Ca":  bf.get("calcium", 0),
                    "Mg":  bf.get("magnesium", 0),
                    "Na":  bf.get("sodium", 0),
                    "K":   bf.get("potassium", 0),
                    "Cl":  bf.get("chloride", 0),
                    "SO4": bf.get("sulfate", 0),
                    "HCO3":bf.get("bicarbonate", 0),
                    "Ba":  bf.get("barium", 0),
                    "Sr":  bf.get("strontium", 0),
                    "F":   bf.get("fluoride", 0),
                    "SiO2":bf.get("silica", 0),
                    "B":   bf.get("boron", 0),
                    "NO3": bf.get("nitrate", 0),
                    "PO4": bf.get("phosphate", 0),
                    "NH4": bf.get("ammonium", 0),
                    "Al":  bf.get("aluminium", 0),
                    "Fe":  bf.get("iron", 0),
                    "Mn":  bf.get("manganese", 0),
                }

        # Tertiary fallback: analytical concentration-factor scaling
        # Used only if both solver paths failed (e.g., legacy result dict)
        if not recycle_feed_ions:
            rr        = float(recycle_ratio)
            fresh_tds = feed.get("tds", sum(ions.values()))
            rec_frac  = target_recovery_pct / 100.0
            CF        = 1.0 / max(1.0 - rec_frac, 0.05)          # Concentration Factor
            conc_tds  = fresh_tds * CF
            q_fresh   = target_flow_m3h / max(1.0 - rec_frac, 0.05)
            q_recycle = q_fresh * rr * rec_frac
            q_blend   = q_fresh + q_recycle
            blend_w   = (q_fresh * fresh_tds + q_recycle * conc_tds) / (q_blend * max(fresh_tds, 1.0))
            recycle_feed_ions = {k: v * blend_w for k, v in ions.items()}
            print(f"[WARN] recycle_feed_ions: using analytical fallback (CF={CF:.2f})")

    # ── CIP config ───────────────────────────────────────────────────────
    cip_cfg = {
        "acid_ph":         2.5,
        "alk_ph":          11.5,
        "interval_months": cip_interval_months,
        "duration_h":      4.0,
    }

    # ── Run physics engine ───────────────────────────────────────────────
    phys_engine = PhysicsAgingEngine()

    # DEBUG: log exact inputs
    print(f"\n=== _run_projection_core ENGINE INPUTS ===")
    print(f"  temp_c       = {temp_c}")
    print(f"  ph           = {ph}")
    print(f"  membrane     = {membrane}")
    print(f"  stages       = {stages}")
    print(f"  vessels      = {vessels_per_stage}")
    print(f"  elems/vessel = {elements_per_vessel}")
    print(f"  recovery_pct = {target_recovery_pct}")
    print(f"  feed_flow    = {target_flow_m3h}")
    print(f"  n_years      = {n_years}")
    print(f"  sdi15        = {sdi15}")
    print(f"  toc_mg_l     = {toc_mg_l}")
    print(f"  cl2          = {cl2_residual_mg_l}")
    print(f"  cip_cfg      = {cip_cfg}")
    print(f"  antiscalant  = {antiscalant_dosed}")
    print(f"  recycle_ions = {recycle_feed_ions is not None}")
    print(f"  baseline P0  = {baseline_ro.get('summary', {}).get('feed_pressure_bar', '?')}")
    print(f"  baseline Q0  = {baseline_ro.get('summary', {}).get('perm_flow', '?')}")
    print(f"==========================================\n")

    # ── Concentrate SI ───
    # Dynamically compute the exact concentrate pH by solving the carbonate
    # equilibrium shift from the feed pH using the concentration factor of HCO3.
    bulk_si = None
    concentrate_si = None
    concentrate_ph = None
    try:
        conc_ions = baseline_ro.get("summary", {}).get("conc_ions", {})
        if conc_ions:
            import math
            feed_hco3 = data.feed_water.bicarbonate
            conc_hco3 = conc_ions.get("HCO3", 0)
            
            est_conc_ph = ph
            if feed_hco3 and feed_hco3 > 0 and conc_hco3 > 0:
                est_conc_ph += math.log10(conc_hco3 / feed_hco3)
            else:
                rec_frac = target_recovery_pct / 100.0
                cf = 1.0 / max(1.0 - rec_frac, 0.05)
                est_conc_ph += math.log10(cf)
                
            est_conc_ph = min(max(est_conc_ph, 0.0), 14.0)

            sol_input = {
                'pH': est_conc_ph,
                'units': 'mg/L',
                'temp': temp_c,
                'Ca': conc_ions.get("Ca", 0),
                'Mg': conc_ions.get("Mg", 0),
                'Na': conc_ions.get("Na", 0),
                'K': conc_ions.get("K", 0),
                'N(-3)': f"{conc_ions.get('NH4', 0)} as NH4",
                'Cl': conc_ions.get("Cl", 0),
                'S(6)': f"{conc_ions.get('SO4', 0)} as SO4",
                # Use alkalinity expressed as HCO3 mg/L for correct carbonate equilibrium
                'Alkalinity': f"{conc_ions.get('HCO3', 0)} as HCO3",
                'N(5)': f"{conc_ions.get('NO3', 0)} as NO3",
                'Sr': conc_ions.get("Sr", 0),
                'F': conc_ions.get("F", 0),
                'Si': f"{conc_ions.get('SiO2', 0)} as SiO2",
                'Ba': conc_ions.get("Ba", 0),
                'Al': conc_ions.get("Al", 0),
                'Fe': conc_ions.get("Fe", 0),
                'Mn': conc_ions.get("Mn", 0),
                'P': f"{conc_ions.get('PO4', 0)} as PO4"
            }
            sol = pp.add_solution(sol_input)
            # Read back the equilibrated pH — PHREEQC solved this from the carbonate system
            concentrate_ph = round(sol.pH, 2)
            concentrate_si = {
                "Calcite":   round(sol.si("Calcite"),   3),
                "Aragonite": round(sol.si("Aragonite"), 3),
                "Dolomite":  round(sol.si("Dolomite"),  3),
                "Gypsum":    round(sol.si("Gypsum"),    3),
                "Anhydrite": round(sol.si("Anhydrite"), 3),
                "Barite":    round(sol.si("Barite"),    3),
                "Celestite": round(sol.si("Celestite"), 3),
                "Fluorite":  round(sol.si("Fluorite"),  3),
                "SiO2(a)":   round(sol.si("SiO2(a)"),   3),
            }
            # Legacy compact SI for physics engine scaling model
            bulk_si = {
                "calcite": concentrate_si["Calcite"],
                "gypsum":  concentrate_si["Gypsum"],
                "barite":  concentrate_si["Barite"],
                "silica":  concentrate_si["SiO2(a)"],
            }
            sol.forget()
    except Exception as e:
        print("Error calculating concentrate SI in server.py:", e)

    physics_results = phys_engine.run_physics_projection(
        baseline_ro_result  = physics_baseline_ro,
        feed_ions           = ions,
        temp_c              = temp_c,
        ph                  = ph,
        membrane_model      = membrane,
        stages              = stages,
        vessels_per_stage   = vessels_per_stage,
        elements_per_vessel = elements_per_vessel,
        target_recovery_pct = target_recovery_pct,
        feed_flow_m3h       = target_flow_m3h,
        n_years             = n_years,
        feed_quality        = {
            "sdi15":             sdi15,
            "toc_mg_l":          toc_mg_l,
            "cl2_residual_mg_l": cl2_residual_mg_l,
        },
        cip_config          = cip_cfg,
        antiscalant_dosed   = antiscalant_dosed,
        recycle_feed_ions   = recycle_feed_ions,
        bulk_si             = bulk_si,
    )

    # Ensure physics engine snapshots reflect the TRUE system recovery/flow (vital for 2P-RO)
    if "annual_snapshots" in physics_results:
        # Extract baseline metrics, supporting both 1-Pass (summary) and 2-Pass (system_summary)
        base_summ = baseline_ro.get("summary", {})
        sys_summ  = baseline.get("system_summary", {})
        # Recycle data is stored at the root of the baseline object
        recycle_data = baseline.get("recycle", {})

        if sys_summ:  # 2-Pass RO
            true_recovery = sys_summ.get("overall_recovery", target_recovery_pct / 100.0)
            true_perm     = sys_summ.get("final_permeate_flow_m3h", None)
        else:         # 1-Pass RO
            true_recovery = base_summ.get("total_recovery", target_recovery_pct / 100.0)
            true_perm     = base_summ.get("perm_flow", None)
            
        true_base_pressure = base_summ.get("feed_pressure_bar", None)  # P1 pressure
        true_base_tds      = base_summ.get("perm_tds", None)
        if "pass2_results" in baseline:  # For 2-Pass RO, TDS comes from Pass 2
            true_base_tds = baseline["pass2_results"]["summary"].get("perm_tds", true_base_tds)

        true_base_sec = sys_summ.get("sec_kwh_m3") if sys_summ else base_summ.get("sec_kwh_m3", None)

        # OVERRIDE: If recycle is enabled, use the effective system recovery
        if recycle_data and recycle_data.get("enabled"):
            true_recovery = recycle_data.get("effective_system_recovery", true_recovery)
            # Explicitly force the permeate flow to match the effective recovery of the fresh feed
            true_perm = true_recovery * target_flow_m3h
            
        print("DEBUG RECOVERY: true_recovery =", true_recovery)
        print("DEBUG RECOVERY: sys_summ =", sys_summ)
        print("DEBUG RECOVERY: recycle_data =", recycle_data)

        snaps = physics_results["annual_snapshots"]

        # ── Correct Year 0 snapshot to the true combined baseline ──────────
        if len(snaps) > 0:
            raw_year0_sec = snaps[0].get("sec_kwh_m3", 0.0)
            snaps[0]["recovery"] = true_recovery
            snaps[0]["npf"]      = 1.0   # ASTM baseline — always 1.0
            snaps[0]["nsp"]      = 1.0   # ASTM baseline — always 1.0
            if true_perm          is not None: snaps[0]["perm_flow"]         = true_perm
            if true_base_pressure is not None: snaps[0]["feed_pressure_bar"] = true_base_pressure
            if true_base_tds      is not None: snaps[0]["perm_tds"]          = true_base_tds
            if true_base_sec      is not None: snaps[0]["sec_kwh_m3"]        = true_base_sec

        # The physics engine has been updated to calibrate A0 to match the exact P0_bar
        # at Year 0, so no delta-correction is needed anymore. The raw physics output
        # is correctly anchored to the baseline.
        
        # We only need to overwrite the recovery and perm_flow to match the true system
        if len(snaps) > 1:
            for snap in snaps[1:]:
                snap["recovery"] = true_recovery
                if true_perm is not None:
                    snap["perm_flow"] = true_perm
                
                # Apply 2-Pass normalization for TDS and SEC
                if true_base_tds is not None:
                    # In a 2-Pass system, if Pass 1 NSP increases (e.g. 1.10), 
                    # Pass 2 feed TDS increases by 10%, causing its permeate TDS to rise proportionately.
                    snap["perm_tds"] = true_base_tds * snap["nsp"]
                
                if true_base_sec is not None:
                    # SEC penalty is driven by physical fouling delta 
                    delta_sec = snap["sec_kwh_m3"] - raw_year0_sec
                    snap["sec_kwh_m3"] = true_base_sec + delta_sec
                
                # NPF and NSP: the physics engine now uses the correct ASTM D4516-19a
                # constant-flow formula (NDP_0 / NDP_y). Values are already physically
                # correct and monotonically declining — no normalization needed.
                # Year 0 = 1.0 (forced by the engine), Year N < 1.0 (as fouling grows).

    # Expose antiscalant state to frontend for SI risk threshold selection
    physics_results["antiscalant_dosed"] = antiscalant_dosed

    return {
        "baseline":        baseline,
        "baseline_ro":     baseline_ro,
        "physics_results": physics_results,
        "concentrate_si":  concentrate_si,
        "concentrate_ph":  concentrate_ph,
    }


# ── Aging endpoint ──────────────────────────────────────────────────────────

@app.post("/api/simulate-aging")
def simulate_aging(data: AgingSimInput):
    """Run the physics-based membrane aging simulation.
    Internally delegates to the same _run_projection_core() as the Year-wise tab.
    """
    try:
        feed = data.feed_water
        sc   = data.system_config
        aging_cfg = data.aging_config.dict()
        feed_hist = data.feed_history.dict()

        # CIP interval: 0 days → 0 months (dynamic). Non-zero: round to nearest month.
        cip_interval_days   = aging_cfg.get("cip_interval_days", 0)
        cip_interval_months = 0 if cip_interval_days == 0 else max(1, round(cip_interval_days / 30))

        n_years = max(1, aging_cfg.get("design_life_months", 60) // 12)

        core = _run_projection_core(
            feed_water          = feed,
            technology_train    = data.technology_train,
            target_flow_m3h     = data.target_flow_m3h,
            target_recovery_pct = sc.target_recovery_pct,
            membrane            = sc.membrane,
            stages              = sc.stages,
            vessels_per_stage   = sc.vessels_per_stage,
            elements_per_vessel = sc.elements_per_vessel,
            n_years             = n_years,
            sdi15               = feed_hist.get("sdi15", 3.0),
            toc_mg_l            = feed_hist.get("toc_mg_l", 2.0),
            cl2_residual_mg_l   = feed_hist.get("cl2_residual_mg_l", 0.0),
            cip_interval_months = cip_interval_months,
            antiscalant_dosed   = aging_cfg.get("antiscalant_dosed", True),
        )

        result = core["physics_results"]
        return {
            "aging_profile":         result.get("monthly_profile", []),
            "cip_events":            result.get("cip_events", []),
            "end_of_life_month":     result.get("end_of_life_month", None),
            "dominant_mechanism":    result.get("dominant_mechanism", "N/A"),
            "mechanism_totals":      result.get("mechanism_totals", {}),
            "element_autopsy":       result.get("element_autopsy", {}),
            "baseline_pressure_bar": result.get("baseline_pressure_bar", 0),
            "baseline_npf":          1.0,
            "annual_snapshots":      result.get("annual_snapshots", []),
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ── Physics Year-wise Projection endpoint ────────────────────────────────────

@app.post("/api/calculate-system-physics")
def calculate_system_physics(data: PhysicsCalcInput):
    """Physics-based multi-year membrane performance projection.
    Internally delegates to the same _run_projection_core() as the Aging tab.
    """
    try:
        import copy

        feed = data.feed_water
        fq   = data.feed_quality or PhysicsFeedQuality()

        # Allow feed_water tss/turbidity to inform SDI if not explicitly set
        if fq.sdi15 == 3.0 and feed.get("tss", 0) > 0:
            fq.sdi15 = min(feed["tss"] * 0.5, 6.0)
        if fq.toc_mg_l == 2.0 and feed.get("toc", 0) > 0:
            fq.toc_mg_l = feed["toc"]

        cip_interval_months = 0
        if data.cip_config:
            cip_interval_months = data.cip_config.interval_months

        core = _run_projection_core(
            feed_water          = feed,
            technology_train    = data.technology_train,
            target_flow_m3h     = data.target_flow_m3h,
            target_recovery_pct = data.target_recovery_pct,
            membrane            = data.ro_membrane,
            stages              = data.stages,
            vessels_per_stage   = data.vessels_per_stage,
            elements_per_vessel = data.elements_per_vessel,
            n_years             = data.n_years,
            sdi15               = fq.sdi15,
            toc_mg_l            = fq.toc_mg_l,
            cl2_residual_mg_l   = fq.cl2_residual_mg_l,
            cip_interval_months = cip_interval_months,
            antiscalant_dosed   = data.antiscalant_dosed,
            recycle_enabled     = data.recycle_enabled or False,
            recycle_ratio       = data.recycle_ratio or 0.0,
            # Sub-configs forwarded verbatim — guarantees all technology trains
            # (RO, UF+RO, NF, UF+NF, 2P-RO, UF+2P-RO) use the user's config
            pass1        = data.pass1.model_dump()        if data.pass1        else None,
            pass2        = data.pass2.model_dump()        if data.pass2        else None,
            conditioning = data.conditioning.model_dump() if data.conditioning else None,
            recycle      = data.recycle.model_dump()      if data.recycle      else None,
            uf_module    = data.uf_module,
        )

        baseline        = core["baseline"]
        physics_results = core["physics_results"]

        # ── Merge selected year into standard result ─────────────────────
        selected_year = data.projection_year
        snapshots = physics_results.get("annual_snapshots", [])
        sel = next((s for s in snapshots if s["year"] == selected_year), None)

        result = copy.deepcopy(baseline)

        if sel and selected_year > 0:
            ro_res = result.get("ro_results") or result.get("pass1_results") or {}
            if "summary" in ro_res:
                base_summ = baseline.get("ro_results", {}).get("summary", {}) or baseline.get("pass1_results", {}).get("summary", {})
                
                base_pressure = base_summ.get("feed_pressure_bar", 1.0) or 1.0
                pressure_ratio = sel["feed_pressure_bar"] / base_pressure
                
                base_tds = base_summ.get("perm_tds", 1.0) or 1.0
                tds_ratio = sel["perm_tds"] / base_tds
                
                base_kwh = base_summ.get("sec_kwh_m3", 1.0) or 1.0
                kwh_ratio = sel["sec_kwh_m3"] / base_kwh

                summ = ro_res["summary"]
                summ["feed_pressure_bar"] = sel["feed_pressure_bar"]
                summ["perm_tds"]          = sel["perm_tds"]
                summ["sec_kwh_m3"]        = sel["sec_kwh_m3"]
                summ["npf"]               = sel["npf"]
                summ["nsp"]               = sel["nsp"]
                summ["fri"]               = sel["fri"]
                summ["b_irr"]        = sel["b_irr"]
                summ["physics_year"]      = selected_year

                pass2_res = result.get("pass2_results")
                if pass2_res and "summary" in pass2_res:
                    p2_summ = pass2_res["summary"]
                    p2_summ["feed_pressure_bar"] *= pressure_ratio
                    p2_summ["perm_tds"] *= tds_ratio
                    p2_summ["sec_kwh_m3"] *= kwh_ratio
                    p2_summ["npf"] = sel["npf"]
                    p2_summ["nsp"] = sel["nsp"]
                    p2_summ["fri"] = sel["fri"]
                    p2_summ["b_irr"] = sel["b_irr"]
                    p2_summ["physics_year"] = selected_year

        result["physics_results"] = physics_results
        result["physics_selected_year"] = selected_year
        result["concentrate_si"] = core.get("concentrate_si")
        result["concentrate_ph"] = core.get("concentrate_ph")

        return result

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

