import os
import sys
import math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from calc_engine import ROEngine
from membrane_database import MembraneDatabase
from physics_aging_engine import PhysicsAgingEngine, _mu_water, MU_25
from uf_engine import UFEngine
from conditioning import compute_chemical_dose, apply_conditioning
from system_engine import SystemEngine
from process_engine import ProcessInputData, ProcessRecommendationEngine
import phreeqpython

def test_15_changes():
    print("=== BEGIN TEST: ALL 15 CALIBRATION CHANGES ===")
    
    # CHANGE 1: Boron in ions & solute sum
    engine = ROEngine()
    mem = MembraneDatabase.get_ro_membrane('HPA-RO-8040')
    res_b = engine.simulate_element(
        feed_flow_m3h=10.0, feed_pressure_bar=15.0,
        feed_ions={'Na': 500.0, 'Cl': 770.0, 'B': 5.0},
        temp_c=25.0, membrane=mem, element_idx=1
    )
    assert 'B' in res_b['perm_ions']
    b_perm = res_b['perm_ions']['B']
    assert 0.0 < b_perm < 5.0
    print(f"[PASS] CHANGE 1: Boron transported: perm B = {b_perm:.2f} mg/L (feed 5.0 mg/L)")

    # CHANGE 2: Dynamic recovery evaluation in process engine
    pp = phreeqpython.PhreeqPython(database='phreeqc.dat')
    pe_safe = ProcessRecommendationEngine(pp)
    safe_data = ProcessInputData(
        feed_tds=500.0, target_tds=50.0, target_recovery=75.0,
        feed_ph=7.0, feed_temp=25.0,
        ca=10.0, so4=20.0, hco3=50.0, na=100.0, cl=150.0
    )
    res_safe = pe_safe.run(safe_data)
    assert res_safe.get('recommended_recovery') == 75.0
    assert not any(v.get('risk') == 'CRITICAL' for v in res_safe.get('scaling_risks', {}).values())

    pe_crit = ProcessRecommendationEngine(pp)
    crit_data = ProcessInputData(
        feed_tds=8000.0, target_tds=50.0, target_recovery=85.0,
        feed_ph=8.2, feed_temp=25.0,
        ca=2500.0, so4=5000.0, sio2=150.0, na=1000.0, cl=2000.0
    )
    res_crit = pe_crit.run(crit_data)
    assert res_crit.get('recommended_recovery') is None
    assert any(v.get('risk') == 'CRITICAL' for v in res_crit.get('scaling_risks', {}).values())
    print(f"[PASS] CHANGE 2: Recovery sweep: safe rec = {res_safe['recommended_recovery']}%, crit scaling rec = {res_crit['recommended_recovery']}")

    # CHANGE 3: Alkalinity-based dosing
    dose_acid = compute_chemical_dose({'pH': 7.8, 'HCO3': 200.0}, target_ph=6.5, chemical='H2SO4')
    dose_caustic = compute_chemical_dose({'pH': 6.0, 'CO2': 25.0}, target_ph=8.0, chemical='NaOH')
    print(f"[PASS] CHANGE 3: Alkalinity-based dosing: H2SO4={dose_acid:.2f} mg/L, NaOH={dose_caustic:.2f} mg/L")
    assert dose_acid > 0.0
    assert dose_caustic > 0.0

    # CHANGE 4: Partial degasser stripping model
    ions_degas, _, _ = apply_conditioning({'CO2': 50.0, 'pH': 6.5}, cond_cfg={'enabled': True}, degasser_cfg={'enabled': True, 'efficiency': 0.90, 'residual_co2_mg_l': 5.0})
    print(f"[PASS] CHANGE 4: Partial degasser: CO2 stripped from 50 to {ions_degas['CO2']:.1f} mg/L")
    assert ions_degas['CO2'] == 5.0

    # CHANGE 5: Interstage booster pump controls
    res_boost_off = engine.simulate_system(
        feed_flow_m3h=100.0, feed_pressure_bar=15.0,
        feed_ions={'Na': 500.0, 'Cl': 770.0}, temp_c=25.0,
        membrane_model='HPA-RO-8040', stages=2, vessels_per_stage=[4, 2], elements_per_vessel=6,
        enable_booster=False
    )
    assert res_boost_off['booster_pumps'][0]['status'] == 'BYPASSED'
    res_boost_manual = engine.simulate_system(
        feed_flow_m3h=100.0, feed_pressure_bar=15.0,
        feed_ions={'Na': 500.0, 'Cl': 770.0}, temp_c=25.0,
        membrane_model='HPA-RO-8040', stages=2, vessels_per_stage=[4, 2], elements_per_vessel=6,
        enable_booster=True, interboost_dp_bar=2.5
    )
    assert res_boost_manual['booster_pumps'][0]['boost_dp_bar'] == 2.5
    print(f"[PASS] CHANGE 5: Booster bypassed by default; manual boost dp = 2.5 bar verified")

    # CHANGE 6: Membrane datasheet rating block
    mem_norm = MembraneDatabase.get_ro_membrane('HPA-RO-8040')
    assert 'datasheet' in mem_norm
    assert mem_norm['datasheet']['test_pressure_psi'] == 225.0
    ro_list = MembraneDatabase.list_ro_membranes()
    assert any('datasheet' in m for m in ro_list)
    print(f"[PASS] CHANGE 6: Membrane datasheet block verified: {mem_norm['datasheet']['test_solution']}, {mem_norm['datasheet']['test_pressure_psi']} psi")

    # CHANGE 7: Concentrate recycle loop
    sys_engine = SystemEngine()
    recycle_input = {
        'technology_train': 'RO',
        'feed_water': {'calcium': 100, 'chloride': 300, 'sodium': 200, 'temperature': 25.0, 'ph': 7.5},
        'target_flow_m3h': 50.0,
        'target_recovery_pct': 75.0,
        'ro_membrane': 'HPA-RO-8040',
        'stages': 2,
        'vessels_per_stage': [4, 2],
        'elements_per_vessel': 6,
        'recycle_enabled': True,
        'recycle_ratio': 0.20
    }
    rec_res = sys_engine.calculate_system_with_recycle(recycle_input)
    assert 'recycle' in rec_res
    assert rec_res['recycle']['converged'] is True
    assert rec_res['recycle']['recycle_flow_m3h'] > 0.0
    assert abs(rec_res['recycle']['blended_feed_flow_m3h'] - (50.0 + rec_res['recycle']['recycle_flow_m3h'])) < 1e-3
    print(f"[PASS] CHANGE 7: Recycle steady state: converged={rec_res['recycle']['converged']}, flow={rec_res['recycle']['recycle_flow_m3h']} m3/h, effective rec = {rec_res['recycle']['effective_system_recovery_pct']}%")

    # CHANGE 8: Antiscalant by chemistry type
    scaling_ions = {'Na': 1000.0, 'Cl': 1500.0, 'Ca': 800.0, 'SO4': 2000.0, 'HCO3': 300.0}
    res_base_scaling = engine.simulate_system(
        feed_flow_m3h=100.0, feed_pressure_bar=18.0,
        feed_ions=scaling_ions, temp_c=25.0,
        membrane_model='HPA-RO-8040', stages=2, vessels_per_stage=[4, 2], elements_per_vessel=6
    )
    bulk_si_test = {'calcite': 1.8, 'gypsum': 0.8, 'barite': 0.0, 'silica': -0.2}
    phys_engine = PhysicsAgingEngine()
    aging_res_dendrimer = phys_engine.run_physics_projection(
        baseline_ro_result=res_base_scaling, feed_ions=scaling_ions,
        temp_c=25.0, ph=8.0, membrane_model='HPA-RO-8040',
        stages=2, vessels_per_stage=[4, 2], elements_per_vessel=6,
        target_recovery_pct=75.0, feed_flow_m3h=100.0, n_years=1,
        bulk_si=bulk_si_test,
        antiscalant_type='Dendrimer'
    )
    aging_res_phosphonate = phys_engine.run_physics_projection(
        baseline_ro_result=res_base_scaling, feed_ions=scaling_ions,
        temp_c=25.0, ph=8.0, membrane_model='HPA-RO-8040',
        stages=2, vessels_per_stage=[4, 2], elements_per_vessel=6,
        target_recovery_pct=75.0, feed_flow_m3h=100.0, n_years=1,
        bulk_si=bulk_si_test,
        antiscalant_type='Phosphonate'
    )
    assert len(aging_res_dendrimer['annual_snapshots']) == 2
    assert len(aging_res_phosphonate['annual_snapshots']) == 2
    # Dendrimer provides stronger crystal growth suppression than standard Phosphonate
    rs_dend = aging_res_dendrimer['annual_snapshots'][1]['rs_avg']
    rs_phos = aging_res_phosphonate['annual_snapshots'][1]['rs_avg']
    assert rs_dend < rs_phos
    print(f"[PASS] CHANGE 8: Antiscalant kinetics differed: Dendrimer Rs={rs_dend:.2e} < Phosphonate Rs={rs_phos:.2e}")

    # CHANGE 9: Standalone UF train
    uf_res = sys_engine.calculate_system({
        'technology_train': 'UF',
        'feed_water': {'temperature': 25.0, 'ph': 7.3, 'turbidity': 15.0, 'tss': 25.0, 'tds': 150.0},
        'target_flow_m3h': 100.0,
        'target_recovery_pct': 90.0,
        'uf_module': 'PERMA-UF-i0875s40'
    })
    assert uf_res['uf_results'] is not None
    assert uf_res['ro_results'] is None
    assert 'economics' in uf_res
    print(f"[PASS] CHANGE 9: Standalone UF train simulated: Capex={uf_res['economics']['capex']['total_capex_inr']} INR, Cost/kL={uf_res['economics']['metrics']['cost_per_kl_inr']} INR")

    # CHANGE 10: sigma = 0.9995 and refitted B
    assert mem['sigma']['Na'] == 0.9995
    assert mem['sigma']['Cl'] == 0.9995
    assert mem['permeability_B'] == 2.30e-08
    print(f"[PASS] CHANGE 10: sigma=0.9995, refitted B={mem['permeability_B']} m/s")

    # CHANGE 11: Sherwood constants (0.050, 0.875, 0.25)
    # Independently compute and compare _calculate_cp_beta for fixed inputs
    beta_calc = engine._calculate_cp_beta(
        flux_lmh=20.0, feed_flow_m3h=10.0, conc_flow_m3h=8.5,
        temp_c=25.0, membrane=mem
    )
    assert round(beta_calc, 4) == 1.1349
    print(f"[PASS] CHANGE 11: Sherwood CP Beta = {beta_calc:.4f} (calibrated Sh = 0.050 * Re^0.875 * Sc^0.25)")

    # CHANGE 12: Viscosity via Vogel equation
    uf_eng = UFEngine()
    vcf = uf_eng._viscosity_correction(25.0)
    mu_calc = engine._water_viscosity(25.0)
    print(f"[PASS] CHANGE 12: Vogel Viscosity at 25 C: calc_engine={mu_calc*1000:.3f} mPa*s, UF VCF={vcf:.4f}")
    assert round(mu_calc * 1000, 3) == 0.890

    # CHANGE 13: Permeate backpressure defaulting to 0.0 bar
    res_omitted = engine.simulate_system(
        feed_flow_m3h=100.0, feed_pressure_bar=15.0,
        feed_ions={'Na': 500.0, 'Cl': 770.0}, temp_c=25.0,
        membrane_model='HPA-RO-8040', stages=2, vessels_per_stage=[4, 2], elements_per_vessel=6
    )
    res_zero = engine.simulate_system(
        feed_flow_m3h=100.0, feed_pressure_bar=15.0,
        feed_ions={'Na': 500.0, 'Cl': 770.0}, temp_c=25.0,
        membrane_model='HPA-RO-8040', stages=2, vessels_per_stage=[4, 2], elements_per_vessel=6,
        permeate_pressure_bar=0.0
    )
    res_positive = engine.simulate_system(
        feed_flow_m3h=100.0, feed_pressure_bar=15.0,
        feed_ions={'Na': 500.0, 'Cl': 770.0}, temp_c=25.0,
        membrane_model='HPA-RO-8040', stages=2, vessels_per_stage=[4, 2], elements_per_vessel=6,
        permeate_pressure_bar=2.0
    )
    ndp_omitted = res_omitted['elements'][0]['ndp']
    ndp_zero = res_zero['elements'][0]['ndp']
    ndp_pos = res_positive['elements'][0]['ndp']
    assert abs(ndp_omitted - ndp_zero) < 1e-6
    assert ndp_pos < ndp_zero
    assert abs((ndp_zero - ndp_pos) - 2.0) < 0.1
    print(f"[PASS] CHANGE 13: Permeate backpressure defaults to 0.0 bar (NDP omitted={ndp_omitted:.2f} bar == 0.0 bar; +2 bar backpressure lowers NDP to {ndp_pos:.2f} bar)")

    # CHANGE 14: TDS includes SiO2
    tds_test = engine.simulate_system(
        feed_flow_m3h=50.0, feed_pressure_bar=15.0,
        feed_ions={'Na': 400.0, 'Cl': 600.0, 'SiO2': 30.0}, temp_c=25.0,
        membrane_model='HPA-RO-8040', stages=1, vessels_per_stage=[2], elements_per_vessel=6
    )
    assert tds_test['summary']['feed_tds'] == 1030.0
    print(f"[PASS] CHANGE 14: Feed TDS includes SiO2: {tds_test['summary']['feed_tds']} mg/L (expected: 1030.0)")

    # CHANGE 15: Feed spacer 31 mil & hydraulic diameter 1.01 mm
    assert mem_norm['feed_spacer_mil'] == 31
    assert round(mem_norm['hydraulic_diameter_m'] * 1000, 2) == 1.01
    print(f"[PASS] CHANGE 15: Spacer=31 mil, d_h={mem_norm['hydraulic_diameter_m']*1000:.2f} mm")

    print("\nALL 15 CHANGES VERIFIED AND PASSED!")

if __name__ == '__main__':
    test_15_changes()

if __name__ == '__main__':
    test_15_changes()

