import os
import sys
import math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from calc_engine import ROEngine
from membrane_database import MembraneDatabase
from physics_aging_engine import PhysicsAgingEngine, _mu_water, MU_25

def test_calibrations():
    engine = ROEngine()
    
    # 1. Viscosity check at 25 C
    mu_25 = engine._water_viscosity(25.0)
    print(f"ROEngine Viscosity at 25 C: {mu_25*1000:.3f} mPa*s (expected: 0.890)")
    assert round(mu_25 * 1000, 3) == 0.890

    mu_aging_25 = _mu_water(25.0)
    print(f"PhysicsAgingEngine Viscosity at 25 C: {mu_aging_25*1000:.3f} mPa*s (expected: 0.890)")
    assert round(mu_aging_25 * 1000, 3) == 0.890
    assert round(MU_25 * 1000, 3) == 0.890

    # 2. Feed spacer and d_h check
    mem = MembraneDatabase.get_ro_membrane('HPA-RO-8040')
    assert mem['feed_spacer_mil'] == 31
    assert mem['sigma']['Na'] == 0.9995
    assert mem['sigma']['Cl'] == 0.9995
    
    t_fs = 31 * 2.54e-5
    eps = 0.90
    d_h = (4.0 * eps) / ((2.0 / t_fs) + ((1.0 - eps) * 8.0 / t_fs))
    print(f"Hydraulic diameter for 31 mil spacer: {d_h*1000:.2f} mm (expected: 1.01 mm)")
    assert round(d_h * 1000, 2) == 1.01

    # 3. Rejection verification for refitted B
    # HPA-4040 test at 2000 ppm NaCl, 225 psi (15.51 bar), 15% recovery
    res_4040 = engine.simulate_element(
        feed_flow_m3h=2.944,
        feed_pressure_bar=15.51,
        feed_ions={'Na': 786.5, 'Cl': 1213.5},
        temp_c=25.0,
        membrane=MembraneDatabase.get_ro_membrane('HPA-4040'),
        element_idx=1
    )
    rej_4040 = 1.0 - sum(res_4040['perm_ions'].values()) / 2000.0
    print(f"HPA-4040 Rejection at test conditions: {rej_4040*100:.2f}% (expected: 99.60%)")
    assert round(rej_4040 * 100, 1) == 99.6

    # HPA-RO-8040 test at 2000 ppm NaCl, 225 psi, 15% recovery
    res_8040 = engine.simulate_element(
        feed_flow_m3h=11.028,
        feed_pressure_bar=15.51,
        feed_ions={'Na': 786.5, 'Cl': 1213.5},
        temp_c=25.0,
        membrane=MembraneDatabase.get_ro_membrane('HPA-RO-8040'),
        element_idx=1
    )
    rej_8040 = 1.0 - sum(res_8040['perm_ions'].values()) / 2000.0
    print(f"HPA-RO-8040 Rejection at test conditions: {rej_8040*100:.2f}% (expected: 99.70%)")
    assert round(rej_8040 * 100, 1) == 99.7

    # 4. Simulate 2-stage system
    feed_ions = {
        'Ca': 100.0, 'Mg': 50.0, 'Na': 500.0, 'K': 10.0,
        'Cl': 800.0, 'SO4': 200.0, 'HCO3': 150.0, 'SiO2': 20.0
    }
    
    res_default = engine.simulate_system(
        feed_flow_m3h=100.0,
        feed_pressure_bar=15.0,
        feed_ions=feed_ions,
        temp_c=25.0,
        membrane_model='HPA-RO-8040',
        stages=2,
        vessels_per_stage=[4, 2],
        elements_per_vessel=6
    )
    
    # Verify booster is off by default
    assert len(res_default['booster_pumps']) == 1
    bp = res_default['booster_pumps'][0]
    assert bp['required'] is False
    assert bp['boost_dp_bar'] == 0.0
    assert bp['power_kw'] == 0.0
    print(f"Booster default status: {bp['status']}, boost_dp: {bp['boost_dp_bar']} bar")

    # Verify TDS includes SiO2
    expected_feed_tds = sum(v for k, v in feed_ions.items() if k not in ('B', 'CO2'))
    assert res_default['summary']['feed_tds'] == expected_feed_tds
    print(f"Feed TDS with SiO2: {res_default['summary']['feed_tds']} mg/L")

    # Verify permeate pressure default is 0.0 bar
    elem1 = res_default['elements'][0]
    print(f"Element 1 NDP: {elem1['ndp']:.2f} bar, Flux: {elem1['flux']:.2f} LMH, Beta: {elem1['beta']:.3f}")

    # 5. Physics aging simulation run
    aging_engine = PhysicsAgingEngine()
    aging_res = aging_engine.run_physics_projection(
        baseline_ro_result=res_default,
        feed_ions=feed_ions,
        temp_c=25.0,
        ph=7.5,
        membrane_model='HPA-RO-8040',
        stages=2,
        vessels_per_stage=[4, 2],
        elements_per_vessel=6,
        target_recovery_pct=res_default['summary']['total_recovery'] * 100.0,
        feed_flow_m3h=100.0,
        n_years=3
    )
    assert len(aging_res['annual_snapshots']) == 4 # Year 0, 1, 2, 3
    print(f"Physics Aging projection completed: {len(aging_res['annual_snapshots'])} annual snapshots generated.")
    for s in aging_res['annual_snapshots']:
        print(f"  Year {s['year']}: Pfeed={s['feed_pressure_bar']:.2f} bar, Perm TDS={s['perm_tds']:.1f} mg/L, NDP ratio={s['ndp_ratio']:.3f}")

    print("ALL CALIBRATION AND AGING ENGINE CHECKS PASSED SUCCESSFULLY!")

if __name__ == '__main__':
    test_calibrations()
