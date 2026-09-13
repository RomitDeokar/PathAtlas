from functools import lru_cache
from .lif_model import simulate


@lru_cache(maxsize=1)
def sensitivity():
    """Test robustness of modeled outputs, never evidence of observed behavior."""
    rows = []
    for scheme in ['synapse_count','log','uniform']:
        for tau in [10,20,30]:
            for threshold in [0,100]:
                result = simulate(scheme,tau,threshold)
                rows.append({'scheme':scheme,'tau_ms':tau,'threshold':threshold,
                             'spike_count':result['spike_count'],'mean_ipi_ms':result['mean_ipi_ms']})
    positive = sum(r['spike_count']>0 for r in rows)
    return {'runs':rows,'total_runs':len(rows),'active_runs':positive,
            'conclusions':[{'label':'Motor output occurs in every run','robust':positive==len(rows)},
                           {'label':'Output is absent in every run','robust':positive==0}],
            'validation':'Not empirically validated. Sensitivity across these 18 assumptions does not establish biological accuracy.'}
