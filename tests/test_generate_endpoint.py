from server import SystemCalcInput, generate_calc_report

data = {
    "technology_train": "1P-RO",
    "feed_water": {"sodium": 50, "temperature": 25, "ph": 7, "calcium": 0, "magnesium": 0, "potassium": 0, "chloride": 0, "sulfate": 0, "bicarbonate": 0, "strontium": 0, "barium": 0, "fluoride": 0, "silica": 0, "boron": 0, "nitrate": 0, "phosphate": 0, "ammonium": 0, "turbidity": 0, "tss": 0, "tds": 50},
    "target_flow_m3h": 50.0,
    "target_recovery_pct": 75.0,
    "ro_membrane": "HPA-RO-8040-LF-WW",
    "stages": 2,
    "vessels_per_stage": [3, 2],
    "elements_per_vessel": 6,
    "aging_results": {
        "status": "success",
        "eol_month": 48,
        "mechanism": "Fouling",
        "final_npf": 1.2,
        "final_feed_pressure": 15.0
    }
}

try:
    inp = SystemCalcInput(**data)
    resp = generate_calc_report(inp)
    print("Success:", resp)
except Exception as e:
    import traceback
    traceback.print_exc()
