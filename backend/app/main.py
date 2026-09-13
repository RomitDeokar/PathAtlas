import csv
import io
import json
from contextlib import asynccontextmanager
from typing import Literal
from pathlib import Path
from urllib.parse import quote
import numpy as np
from scipy.io import wavfile
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response, FileResponse
from fastapi.staticfiles import StaticFiles
from .config import CAVEAT, SOURCES, provenance
from .schemas import Species, Scheme, KnockoutRequest
from .data.cache_build import ensure_cache, load_subgraph, save_query, read_query
from .data.releases import release, catalog, circuit_contracts
from .graph.pathfinding import graph_from, top_paths
from .graph.perturbation import knockout
from .graph.crosssex_diff import scoped_diff
from .graph.motif_stats import motif_stats
from .sim.lif_model import simulate
from .sim.sensitivity import sensitivity


@asynccontextmanager
async def lifespan(app):
    ensure_cache()
    yield


app = FastAPI(title='PathAtlas',version='0.3.0',description=CAVEAT,lifespan=lifespan)


def stored(query_id, expected=None):
    try:
        result = read_query(query_id)
    except KeyError:
        raise HTTPException(404,'Query not found; trace a pathway first.')
    if expected and result.get('kind') != expected:
        raise HTTPException(422,f'Expected a {expected} query')
    return result


Mode = Literal['synthetic', 'release', 'live']


def dataset(species, circuit, mode, min_weight=1):
    """Never silently substitute synthetic data for an unavailable release."""
    if mode == 'live':
        raise HTTPException(503, 'Live authenticated queries are not configured. Select an attributed release snapshot explicitly.')
    if mode == 'synthetic':
        nodes, edges = load_subgraph(species, circuit, min_weight)
        return nodes, edges, provenance()
    try:
        result = release(species, circuit)
    except ValueError as exc:
        raise HTTPException(503, str(exc)) from exc
    return result['nodes'], [e for e in result['edges'] if e['weight'] >= min_weight], result['provenance']


@app.get('/api/health')
def health():
    return {'status': 'ok', 'mode': 'release+synthetic', 'version': '0.3.0',
            'release_available': {r['species']: r['available'] for r in catalog()}}


@app.get('/api/datasets')
def datasets():
    return {'datasets': catalog(), 'caveat': CAVEAT}


@app.get('/api/sources')
def sources():
    checks = circuit_contracts()
    return {'sources': SOURCES, 'provenance': provenance(), 'gates': [
        {'name': c['name'], 'status': c['status'],
         'detail': c.get('detail', f"Observed: {c.get('observed', 'see contract')}. Expected: {c.get('expected', '')}")}
        for c in checks]}


@app.get('/api/validation/contracts')
def contracts():
    return save_query({'kind': 'contracts', 'parameters': {'scope': 'bundled escape snapshots'},
                       'checks': circuit_contracts(), 'datasets': catalog(),
                       'provenance': {'mode': 'release', 'dataset': 'MaleCNS + BANC',
                                      'version': 'v1.0 / v888', 'caveat': CAVEAT,
                                      'limitations': ['Structural contracts are not behavioral validation.']}})


@app.get('/api/neurons/search')
def search(query: str = Query('', max_length=100), species: Species = 'male',
           circuit: Literal['escape', 'courtship'] = 'escape', mode: Mode = 'release'):
    nodes, _, evidence = dataset(species, circuit, mode)
    return {'neurons': [n for n in nodes if query.lower() in
                       f"{n['id']} {n['label']} {n['role']} {n.get('type', '')}".lower()],
            'provenance': evidence, 'scope': 'Bounded snapshot only, not a full-dataset search.'}


@app.get('/api/pathway')
def pathway(source_id: str = Query('', max_length=100),
            target_region: Literal['Leg motor pool', 'Wing motor pool'] = 'Leg motor pool',
            species: Species = 'male', max_hops: int = Query(5, ge=1, le=8),
            top_k: int = Query(5, ge=1, le=20), min_weight: int = Query(1, ge=1, le=1000),
            circuit: Literal['escape', 'courtship'] = 'escape', mode: Mode = 'release'):
    nodes, edges, evidence = dataset(species, circuit, mode, min_weight)
    if not source_id:
        source_id = release(species, circuit)['default_source'] if mode == 'release' else f'demo-{species}-S01'
    graph = graph_from(nodes, edges)
    if source_id not in graph:
        raise HTTPException(404, 'Source is not present in this snapshot. No match was inferred.')
    targets = [n['id'] for n in nodes if n['stage'] == 4 and n['region'] == target_region]
    paths, truncated = top_paths(graph, source_id, targets, max_hops, top_k)
    parameters = dict(source_id=source_id, target_region=target_region, species=species,
                      max_hops=max_hops, top_k=top_k, min_weight=min_weight, circuit=circuit, mode=mode)
    return save_query({'kind': 'pathway', 'parameters': parameters, 'nodes': nodes, 'edges': edges,
                       'paths': paths, 'targets': targets, 'search_truncated': truncated,
                       'ranking': 'Ascending sum(1 / count). Strength proxy = 1 / cost; not physiological strength. Sign is not used to infer functional transmission.',
                       'provenance': evidence})


@app.get('/api/pathway/candidates')
def candidates(path_id: str):
    """Return same-annotation candidates for manual choice, never assert cell identity."""
    trace = stored(path_id, 'pathway')
    p = trace['parameters']
    other = 'female' if p['species'] == 'male' else 'male'
    nodes, _, evidence = dataset(other, p['circuit'], p['mode'])
    source = next(n for n in trace['nodes'] if n['id'] == p['source_id'])
    if p['mode'] == 'synthetic':
        matches = [n for n in nodes if n['label'] == source['label']]
    else:
        matches = [n for n in nodes if n.get('type') and n['type'] == source.get('type')]
    return {'species': other, 'candidates': matches, 'provenance': evidence,
            'confidence': 'unvalidated',
            'note': 'Same-type candidates only. Select a source explicitly; no anatomical registration or cell identity is implied.'}


@app.post('/api/knockout')
def lesion(request: KnockoutRequest):
    """Return structural virtual-lesion output, not observed behavioral consequences."""
    trace = stored(request.path_id,'pathway')
    graph = graph_from(trace['nodes'],trace['edges'])
    if any(n not in graph for n in request.neuron_ids):
        raise HTTPException(422,'Selected neuron is outside this subgraph.')
    p = trace['parameters']
    result = knockout(graph,p['source_id'],trace['targets'],request.neuron_ids,p['max_hops'],p['top_k'],request.seed,request.controls)
    return save_query({'kind':'knockout','path_id':request.path_id,'parameters':request.model_dump(),**result,'provenance':trace['provenance']})


@app.get('/api/pathway/diff')
def difference(male_path_id: str, female_path_id: str):
    a,b = stored(male_path_id,'pathway'),stored(female_path_id,'pathway')
    try:
        result = scoped_diff(a,b)
    except ValueError as e:
        raise HTTPException(422,str(e))
    return save_query({'kind':'diff','parameters':{'male_path_id':male_path_id,'female_path_id':female_path_id},**result,'provenance':{'mode':a['provenance']['mode'],'dataset':'Pathway-scoped specimen comparison','version':a['provenance']['version']+' / '+b['provenance']['version'],'caveat':CAVEAT,'limitations':list(dict.fromkeys(a['provenance']['limitations']+b['provenance']['limitations'])),'inputs':[a['provenance'],b['provenance']]}})


@app.get('/api/stats/motif')
def stats(subgraph_id: str):
    trace = stored(subgraph_id,'pathway')
    return save_query({'kind':'stats','parameters':{'subgraph_id':subgraph_id},**motif_stats(graph_from(trace['nodes'],trace['edges'])),'provenance':trace['provenance']})


@app.get('/api/circuit/courtship/simulate')
def simulation(weight_scheme: Scheme='synapse_count',tau_ms: Literal[10,20,30]=20,min_weight: Literal[0,100]=0):
    """Return synthetic modeled spikes, explicitly unvalidated against behavior."""
    return save_query({'kind':'simulation',**simulate(weight_scheme,tau_ms,min_weight),'provenance':provenance()})


@app.get('/api/circuit/courtship/sensitivity')
def sweep():
    """Return model-assumption sensitivity, not biological validation."""
    return save_query({'kind':'sensitivity','parameters':{'schemes':['synapse_count','log','uniform'],'tau_ms':[10,20,30],'thresholds':[0,100]},**sensitivity(),'provenance':provenance()})


@app.get('/api/audio/{query_id}.wav')
def audio(query_id: str):
    """Sonify modeled spikes. This is not a fly recording or an acoustic model."""
    result = stored(query_id,'simulation')
    rate = 22050
    samples = np.zeros(rate//2,dtype=float)
    t = np.arange(int(.008*rate))/rate
    pulse = np.sin(2*np.pi*220*t)*np.hanning(len(t))*.25
    for spike in result['motor_spikes_ms']:
        start = int(spike/1000*rate)
        end = min(start+len(pulse),len(samples))
        samples[start:end] += pulse[:end-start]
    buf = io.BytesIO()
    wavfile.write(buf,rate,(np.clip(samples,-1,1)*32767).astype(np.int16))
    return Response(buf.getvalue(),media_type='audio/wav',headers={'Content-Disposition':'attachment; filename="pathatlas-synthetic-sonification.wav"'})


@app.get('/api/neuroglancer_state')
def neuroglancer(neuron_ids: str = Query('',max_length=2000), species: Species='male'):
    # Reject unverified identifiers; never send synthetic fixture IDs to an anatomical viewer.
    return {'available':False,'state':None,'url':'https://male-cns.janelia.org/' if species=='male' else 'https://ng.banc.community/view',
            'reason':'Synthetic IDs have no EM geometry. A verified segmentation source and real IDs are required to generate a neuron state.',
            'provenance':provenance()}


@app.get('/api/export')
def export(query_id: str, format: Literal['json','csv']='json'):
    result = stored(query_id)
    headers = {'Content-Disposition':f'attachment; filename="pathatlas-{query_id}.{format}"'}
    if format == 'json':
        return Response(json.dumps(result,indent=2),media_type='application/json',headers=headers)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['query_id','kind','field','json_value','caveat'])
    for key,value in result.items():
        writer.writerow([query_id,result['kind'],key,json.dumps(value,ensure_ascii=False),CAVEAT])
    return Response(output.getvalue(),media_type='text/csv',headers=headers)


DIST = Path(__file__).resolve().parents[2] / 'frontend' / 'dist'
if DIST.exists():
    app.mount('/assets',StaticFiles(directory=DIST/'assets'),name='assets')
    @app.get('/')
    def frontend():
        return FileResponse(DIST/'index.html')
