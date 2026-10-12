"""Cold offline original-grid physical/official KPI and input checks."""
import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from official_kpi import KPI_Calculator

ROOT=Path(__file__).resolve().parent


def physical(d,kpi):
    t=d['time'];assert t[0]==float(d['initial_time'])-7*86400
    assert t[-1]==float(d['end_time']);assert np.all(np.diff(t)==30)
    assert float(d['end_time']-d['initial_time'])==14*86400
    mask=t>=d['initial_time'];tt=t[mask]
    def integral(v):return float(np.trapezoid(v,tt))
    T=d['zon_reaTRooAir_y'][mask];C=d['zon_reaCO2RooAir_y'][mask]
    result={'tdis_tot':integral(np.maximum(d['LowerSetp[1]'][mask]-T,0)+np.maximum(T-d['UpperSetp[1]'][mask],0))/3600,
            'idis_tot':integral(np.maximum(C-d['UpperCO2[1]'][mask],0))/3600}
    energy=cost=emissions=0
    for kind in ['ElectricPower','GasPower']:
        power=sum(d[p][mask] for p in kpi[kind]);assert np.all(power>=-1e-5)
        price='Price'+kind+('HighlyDynamic' if kind=='ElectricPower' else '')
        energy+=integral(power)/3600000/float(d['area'])
        cost+=integral(power*d[price][mask])/3600000/float(d['area'])
        emissions+=integral(power*d['Emissions'+kind][mask])/3600000/float(d['area'])
        bins=(tt//900).astype(int);bins-=bins.min()
        result['pele_tot' if kind=='ElectricPower' else 'pgas_tot']=float((np.bincount(bins,weights=power)/np.bincount(bins)).max()/1000/float(d['area']))
    result.update(ener_tot=energy,cost_tot=cost,emis_tot=emissions)
    return result


def check():
    events=json.loads((ROOT/'commands.json').read_text());rows=[]
    assert len(events)==14*86400//300
    for label in ['default','tight']:
        row=json.loads((ROOT/(label+'-row.json')).read_text())
        with np.load(ROOT/(label+'.npz')) as z:d={k:z[k].copy() for k in z.files}
        with np.load(ROOT/(label+'-hidden.npz')) as z:h=dict(zip(z['names'],z['values'].T))
        assert all(np.all(np.isfinite(v)) for v in d.values())
        case=SimpleNamespace(y_store={k:v for k,v in d.items() if v.ndim},initial_time=float(d['initial_time']),kpi_json=row['kpi_json'])
        case._get_area=lambda:float(d['area']);case._get_elapsed_control_time_ratio=lambda:[]
        case.data_manager=SimpleNamespace(get_data=lambda index,variables:{k:np.interp(index,d['time'],d[k]) for k in variables})
        official=KPI_Calculator(case).get_core_kpis(price_scenario='HighlyDynamic');calc=physical(d,row['kpi_json'])
        for k,v in calc.items():
            assert np.isclose(v,row['kpis'][k],rtol=2e-6,atol=1e-9)
            assert np.isclose(official[k],row['kpis'][k],rtol=1e-12,atol=1e-12)
        for e in events:
            i=np.searchsorted(d['time'],e['time'],side='right');j=np.searchsorted(d['time'],e['time']+300,side='left')
            for p,value in e['u'].items():
                if p.endswith('_u'):
                    assert row['inputs'][p]['Minimum']<=value<=row['inputs'][p]['Maximum']
                    assert e['u'][p[:-2]+'_activate']==1
                    assert np.allclose(d[p][i:j],value,atol=1e-8)
        bad=dict(d);bad['fcu_reaPHea_y']=d['fcu_reaPHea_y']*2
        assert not np.isclose(physical(bad,row['kpi_json'])['cost_tot'],row['kpis']['cost_tot'],rtol=2e-6)
        bad=dict(d);bad['zon_reaCO2RooAir_y']=d['zon_reaCO2RooAir_y']+100
        assert physical(bad,row['kpi_json'])['idis_tot']>row['kpis']['idis_tot']+100
        pressure=h['mod.zon.roo.air.vol.dynBal.medium.p'];mass=h['mod.fcu.fan.vol.m']
        assert np.allclose(h['mod.zon.density.d'],1.2*pressure/101325,rtol=1e-12)
        assert np.allclose(-h['mod.zon.sinInf.m_flow_in'],.018*h['mod.zon.density.d'],atol=1e-12)
        rows.append({'label':label,'idis':calc['idis_tot'],'pressure_drop_Pa':float(pressure[0]-pressure[-1]),'fan_mass_loss_kg':float(mass[0]-mass[-1])})
    assert rows[0]['idis']-rows[1]['idis']>50
    assert rows[0]['pressure_drop_Pa']>100 and abs(rows[1]['pressure_drop_Pa'])<.01
    print(json.dumps({'original_grid_physical_official_inputs_and_negative_controls':'pass','rows':rows},indent=2))


if __name__=='__main__':check()
