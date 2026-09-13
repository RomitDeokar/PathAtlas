"""An explicitly synthetic Brian2 LIF sandbox, not a validated courtship model."""
from functools import lru_cache
from threading import Lock
import numpy as np
from ..data.fixtures import fixture

_LOCK = Lock()


@lru_cache(maxsize=24)
def simulate(scheme='synapse_count', tau_ms=20, min_weight=0):
    """Model synthetic spikes. Sonification does not represent recorded fly song."""
    import brian2 as b
    with _LOCK:
        b.prefs.codegen.target = 'numpy'
        clock = b.Clock(dt=.2*b.ms)
        nodes,edges = fixture('male','courtship')
        ids = {n['id']:i for i,n in enumerate(nodes)}
        tau = tau_ms*b.ms
        cells = b.NeuronGroup(len(nodes), 'dv/dt = (-v + drive * int(t >= 50*ms) * int(t < 350*ms))/tau : 1 (unless refractory)\ndrive : 1',
                              threshold='v > 1',reset='v = 0',refractory=3*b.ms,method='euler',clock=clock,namespace={'tau':tau})
        cells.drive[0] = 2.4
        links = b.Synapses(cells,cells,'w : 1',on_pre='v_post += w',delay=2*b.ms,clock=clock)
        usable = [e for e in edges if e['weight'] >= min_weight]
        links.connect(i=[ids[e['source']] for e in usable],j=[ids[e['target']] for e in usable])
        weights = np.array([e['weight'] for e in usable],dtype=float)
        if scheme == 'synapse_count':
            weights = weights / max(e['weight'] for e in edges) * 1.5
        elif scheme == 'log':
            weights = np.log1p(weights)/np.log1p(max(e['weight'] for e in edges))*1.5
        else:
            weights = np.ones_like(weights)*1.5
        # Unknown signs are excluded rather than silently asserted to be excitatory.
        weights *= np.array([-1 if e['sign']=='inhibitory' else 0 if e['sign']=='unknown' else 1 for e in usable])
        links.w = weights
        spikes = b.SpikeMonitor(cells)
        network = b.Network(cells,links,spikes)
        network.run(500*b.ms)
        motor_index = next(i for i,n in enumerate(nodes) if n['label']=='M02')
        output = np.array(spikes.spike_trains()[motor_index]/b.ms)
        raster = [{'neuron':int(i),'time':round(float(t/b.ms),2)} for i,t in zip(spikes.i,spikes.t)]
        intervals = np.diff(output)
        return {'engine':'Brian2 · LIF · synthetic circuit', 'parameters':{'weight_scheme':scheme,'tau_ms':tau_ms,'min_weight':min_weight,'dt_ms':.2,'duration_ms':500,'stimulus_ms':[50,350],'refractory_ms':3,'delay_ms':2,'gain':1.5},
                'spikes':raster,'motor_spikes_ms':[round(float(t),2) for t in output],
                'labels':[n['label'] for n in nodes], 'spike_count':len(output),
                'mean_ipi_ms':round(float(np.mean(intervals)),2) if len(intervals) else None,
                'reference':{'literature_ipi_ms':35,'recording_loaded':False,'validated':False,
                'note':'35 ms is a literature guide only. No empirical recording or curated courtship circuit has been loaded.'},
                'assumptions':['Weights are dimensionless synthetic count proxies, not conductances.',
                'Unknown transmitter signs excluded. Inhibitory sign is a modeling assumption.',
                'No muscle, wing mechanics, gap-junction, or acoustic model. Audio is spike sonification.']}
