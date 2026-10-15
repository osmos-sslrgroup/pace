import urllib.request
import json

payload = {
    "technology_train": "UF_RO",
    "feed_water": {
        "calcium": 400, "magnesium": 1300, "sodium": 10500, "potassium": 380,
        "ammonium": 0, "barium": 0.05, "strontium": 8, "iron": 0, "manganese": 0,
        "bicarbonate": 140, "sulfate": 2700, "chloride": 19000, "fluoride": 1,
        "nitrate": 0, "phosphate": 0, "silica": 1, "boron": 4.5, "toc": 2, "tss": 0,
        "temperature": 25, "ph": 8.0, "turbidity": 0, "tds": 35000
    },
    "target_flow_m3h": 100,
    "target_recovery_pct": 45,
    "ro_membrane": "FilmTec SW30HRLE-400",
    "stages": 1,
    "vessels_per_stage": [20],
    "elements_per_vessel": 6,
    "n_years": 5,
    "projection_year": 2,
    "feed_quality": {
        "sdi15": 3.0,
        "toc_mg_l": 2.0,
        "cl2_residual_mg_l": 0.0
    },
    "cip_config": {
        "interval_months": 0,
        "duration_h": 4.0
    },
    "antiscalant_dosed": True
}

req = urllib.request.Request("http://localhost:8000/api/calculate-system-physics", 
                             data=json.dumps(payload).encode("utf-8"),
                             headers={
                                 "Content-Type": "application/json",
                                 "Authorization": "Basic dXNlcjpwYXNzd29yZDEyMw=="
                             })
try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode("utf-8"))
        if "physics_results" in data:
            snaps = data["physics_results"].get("annual_snapshots", [])
            for s in snaps:
                print(f"Year {s['year']}: Bulk Calcite={s.get('si_calcite_bulk')}, Wall Calcite={s.get('si_calcite_wall')}, Recovery={s.get('recovery')}, Qp={s.get('perm_flow')}")
except Exception as e:
    print("Error:", e)
