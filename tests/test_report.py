"""
Full test of ReportGenerator using real SystemEngine output.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from system_engine import SystemEngine
from report_generator import ReportGenerator

engine = SystemEngine()

inp = {
    'technology_train': '1P-RO',
    'feed_water': {
        'sodium': 48.4,        'calcium': 29.04,    'magnesium': 7.26,
        'potassium': 4.5,      'chloride': 130.0,   'sulfate': 110.0,
        'bicarbonate': 180.0,  'strontium': 1.2,    'barium': 0.05,
        'fluoride': 0.6,       'silica': 18.0,      'boron': 0.0,
        'nitrate': 15.0,       'phosphate': 0.1,    'ammonium': 0.2,
        'temperature': 25.0,   'ph': 7.2,           'turbidity': 0.2,
        'tss': 2.0,            'tds': 753.6,
    },
    'target_flow_m3h': 50.0,
    'target_recovery_pct': 75.0,
    'ro_membrane': 'HPA-RO-8040-LF-WW',
    'stages': 2,
    'vessels_per_stage': [3, 2],
    'elements_per_vessel': 6,
    'recycle_enabled': False,
    'recycle_ratio': 0.0,
    'economic_params': {
        'electricity_tariff': 7.5,
        'membrane_cost': 26880.0,
        'vessel_cost': 48000.0,
        'pump_cost_kw': 96000.0,
        'ic_factor': 0.15,
        'contingency_factor': 0.10,
        'plant_availability': 0.90,
        'membrane_lifetime': 5.0,
        'discount_rate': 0.10,
        'project_life': 20.0,
    }
}

print("Running system calculation...")
result = engine.calculate_system(inp)
result['project_name'] = 'PACE Test Project – Well Water 50 CMH'
result['project_details'] = {
    'name': 'PACE Test Project',
    'client': 'Mock Client',
    'engineer': 'Test Engineer',
    'date': '2026-06-29',
    'revision': 'Rev-A',
    'revDesc': 'Initial Release',
    'caseNo': 'Case-1',
    'caseDesc': 'Well Water Feed',
    'notes': 'This is a mock note test.'
}
result['aging_results'] = {
    'status': 'success',
    'end_of_life_month': 48,
    'dominant_mechanism': 'fouling_organic',
    'aging_profile': [
        {'npf': 1.0, 'p_feed_bar': 10.0},
        {'npf': 0.8, 'p_feed_bar': 12.0},
        {'npf': 0.5, 'p_feed_bar': 14.5}
    ]
}
print(f"Recovery: {result['ro_results']['summary']['total_recovery']*100:.1f}%")
print(f"Perm TDS: {result['ro_results']['summary']['perm_tds']:.2f} mg/L")
print(f"Elements: {len(result['ro_results']['elements'])}")

rg   = ReportGenerator()
path = rg.generate_calculation_report(result, "WAVE_Style_Report.docx")
print(f"\nReport saved to: {path}")
