from server import _run_projection_core, PhysicsCalcInput, PhysicsFeedQuality, PhysicsCIPConfig
import json

payload = {'technology_train': '2P-RO', 'feed_water': {'calcium': 85, 'magnesium': 28, 'sodium': 130, 'potassium': 4.5, 'barium': 0.05, 'strontium': 1.2, 'chloride': 180, 'sulfate': 110, 'bicarbonate': 180, 'nitrate': 15, 'fluoride': 0.6, 'silica': 18, 'boron': 0, 'phosphate': 0.1, 'aluminium': 0.03, 'iron': 0.05, 'manganese': 0.02, 'temperature': 25, 'ph': 7.2, 'tds': 753.6, 'tss': 0, 'turbidity': 0.2}, 'target_flow_m3h': 50.0, 'target_recovery_pct': 75.0, 'target_tds': 50.0, 'source_type': 'LOW_TDS', 'ro_membrane': 'HPA-4040', 'uf_module': None, 'stages': 2, 'vessels_per_stage': [4, 2], 'elements_per_vessel': 6, 'economic_params': {'electricity_tariff': 7.5, 'membrane_cost': 26880.0, 'vessel_cost': 48000.0, 'pump_cost_kw': 96000.0, 'ic_factor': 0.15, 'contingency_factor': 0.1, 'plant_availability': 0.9, 'membrane_lifetime': 5.0, 'discount_rate': 0.1, 'project_life': 20.0}, 'recycle_enabled': False, 'recycle_ratio': 0.0, 'pass1': {'membrane': 'HPA-4040', 'stages': 2, 'vessels_per_stage': [4, 2], 'elements_per_vessel': 6, 'target_recovery_pct': 75.0}, 'pass2': {'membrane': 'HPA-4040', 'stages': 1, 'vessels_per_stage': [2], 'elements_per_vessel': 6, 'target_recovery_pct': 85.0}, 'conditioning': {'enabled': False, 'target_ph': 9.8, 'chemical': 'NaOH', 'co2_degassing': False}, 'recycle': {'enabled': False, 'recycle_ratio': 0.0}, 'aging_results': None, 'pfd_svg': None, 'pfd_png': None, 'project_details': None, 'physics_results': None, 'physics_selected_year': 0}

from system_engine import SystemEngine
engine = SystemEngine()
res = engine.calculate_system(payload)

sys_input = PhysicsCalcInput(**payload)
sys_input.feed_quality = PhysicsFeedQuality()
sys_input.cip_config = PhysicsCIPConfig()

physics = _run_projection_core(
    feed_water=sys_input.feed_water,
    technology_train=sys_input.technology_train,
    target_flow_m3h=sys_input.target_flow_m3h,
    target_recovery_pct=sys_input.target_recovery_pct,
    membrane=sys_input.ro_membrane,
    stages=sys_input.stages,
    vessels_per_stage=sys_input.vessels_per_stage,
    elements_per_vessel=sys_input.elements_per_vessel,
    n_years=sys_input.n_years,
    sdi15=sys_input.feed_quality.sdi15,
    toc_mg_l=sys_input.feed_quality.toc_mg_l,
    cl2_residual_mg_l=sys_input.feed_quality.cl2_residual_mg_l,
    cip_interval_months=0,
    antiscalant_dosed=True,
    recycle_enabled=sys_input.recycle_enabled,
    recycle_ratio=sys_input.recycle_ratio,
    pass1=sys_input.pass1,
    pass2=sys_input.pass2
)

snaps = physics['physics_results']['annual_snapshots']
for s in snaps:
    print(f"Year {s['year']}: NPF={s['npf']:.3f} SEC={s['sec_kwh_m3']:.3f} TDS={s['perm_tds']:.1f} Rep={s['replacement_triggered']} NSP={s.get('nsp', 1.0)}")
