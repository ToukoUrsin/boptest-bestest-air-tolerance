"""Run the exact frozen command sequence with the upstream TestCase/FMU.

Requires an upstream checkout and Python environment with pyfmi/numpy/pandas/
requests/pytz. No optimizer and no controller tuning are involved.
"""
import argparse
from contextlib import redirect_stdout
import hashlib
import json
import logging
import os
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parent


def checked(response):
    assert response[0]==200,response[1]
    return response[2]


def main():
    p=argparse.ArgumentParser();p.add_argument('--boptest',required=True)
    p.add_argument('--fmu');p.add_argument('--rtol',type=float,required=True)
    p.add_argument('--out',required=True);p.add_argument('--smoke',action='store_true');a=p.parse_args()
    upstream=Path(a.boptest).resolve();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
    fmu=Path(a.fmu).resolve() if a.fmu else upstream/'testcases/bestest_air/models/wrapped.fmu'
    b=fmu.read_bytes();blob=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
    assert blob=='84db75c5026b6744fedf457b333be5354b145f1f', 'Different FMU: scope must be checked again'
    events=json.loads((ROOT/'commands.json').read_text());sys.path.insert(0,str(upstream))
    os.chdir(out);(out/'version.txt').write_text((upstream/'version.txt').read_text())
    from testcase import TestCase
    case=TestCase(fmupath=str(fmu),forecast_uncertainty_params_path=str(upstream/'forecast/forecast_uncertainty_params.json'))
    logging.getLogger().handlers.clear();logging.getLogger().addHandler(logging.NullHandler())
    case.store_results=lambda:None
    simulate=case._TestCase__simulation
    def with_tolerance(*args,**kwargs):
        if case.initialize_fmu:case.fmu.set('_cs_rel_tol',a.rtol)
        return simulate(*args,**kwargs)
    case._TestCase__simulation=with_tolerance
    with open(os.devnull,'w') as quiet,redirect_stdout(quiet):
        checked(case.set_scenario({'electricity_price':'highly_dynamic','time_period':'peak_heat_day',
                                   'temperature_uncertainty':None,'solar_uncertainty':None,'seed':None}))
    assert case.fmu.get('_cs_rel_tol')[0]==a.rtol
    checked(case.set_step(300));pressure=[];mass=[];times=[]
    for event in events[:12] if a.smoke else events:
        assert case.start_time==event['time']
        times.append(case.start_time)
        pressure.append(float(case.fmu.get('mod.zon.roo.air.vol.dynBal.medium.p')[0]))
        mass.append(float(case.fmu.get('mod.fcu.fan.vol.m')[0]))
        with open(os.devnull,'w') as quiet,redirect_stdout(quiet):checked(case.advance(event['u']))
    pressure.append(float(case.fmu.get('mod.zon.roo.air.vol.dynBal.medium.p')[0]))
    mass.append(float(case.fmu.get('mod.fcu.fan.vol.m')[0]));times.append(case.start_time)
    if not a.smoke:assert case.start_time==case.end_time
    arrays={k:np.asarray(v) for k,v in case.y_store.items()}
    arrays.update({k:np.asarray(v) for k,v in case.u_store.items() if k!='time'})
    for k in ['area','initial_time','end_time']:arrays[k]=np.array(getattr(case,k))
    np.savez_compressed(out/'trajectory.npz',**arrays)
    np.savez_compressed(out/'pressure-mass.npz',time=times,pressure=pressure,mass=mass)
    report={'scope':'one-hour smoke only' if a.smoke else 'full seven-day native warmup + fourteen-day frozen command replay',
            'rtol':a.rtol,'actual_rtol':float(case.fmu.get('_cs_rel_tol')[0]),'commands':len(times)-1,
            'kpis':checked(case.get_kpis()),'pressure_drop_Pa':pressure[0]-pressure[-1],
            'fan_mass_loss_kg':mass[0]-mass[-1]}
    (out/'reproduced.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
