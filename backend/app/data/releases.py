"""Read immutable, attributed, bounded release extracts; never query full data in the API."""
import hashlib
import json
from functools import lru_cache
from pathlib import Path

from ..config import MAX_NODES, MAX_EDGES

ROOT = Path(__file__).parent / 'releases'


@lru_cache(maxsize=4)
def release(species, circuit='escape'):
    if species not in ('male', 'female') or circuit != 'escape':
        raise ValueError('No real courtship snapshot is available. Select escape, or explicitly use synthetic mode.')
    path = ROOT / f'{species}_{circuit}.json'
    if not path.exists():
        raise ValueError('Release snapshot missing. Run python -m backend.app.data.ingest.')
    payload = path.read_bytes()
    result = json.loads(payload)
    if len(result['nodes']) > MAX_NODES or len(result['edges']) > MAX_EDGES:
        raise ValueError('Release exceeds the bounded subgraph budget.')
    result['provenance']['snapshot_sha256'] = hashlib.sha256(payload).hexdigest()
    return result


def catalog():
    datasets = []
    for species in ['male', 'female']:
        try:
            r = release(species)
            datasets.append({'species': species, 'circuit': 'escape', 'available': True,
                             'default_source': r['default_source'], 'nodes': len(r['nodes']),
                             'edges': len(r['edges']), 'provenance': r['provenance'],
                             'validation': r['validation']})
        except ValueError as exc:
            datasets.append({'species': species, 'available': False, 'reason': str(exc)})
    return datasets


def circuit_contracts():
    """Executable structural contracts, not empirical behavioral validation."""
    from ..graph.pathfinding import graph_from, top_paths
    checks = []
    for species in ['male', 'female']:
        try:
            r = release(species)
            graph = graph_from(r['nodes'], r['edges'])
            targets = [n['id'] for n in r['nodes'] if n['stage'] == 4]
            paths, truncated = top_paths(graph, r['default_source'], targets, 5, 5)
            checks.extend([
                {'name': f'{species}: bounded release', 'status': 'pass' if len(graph) <= 80 else 'fail', 'observed': len(graph), 'expected': '≤80 neurons'},
                {'name': f'{species}: motor-reaching structural route', 'status': 'pass' if paths and not truncated else 'fail', 'observed': len(paths), 'expected': '≥1 complete top-k route'},
                {'name': f'{species}: identifiers are release IDs', 'status': 'pass' if all(n.isdigit() for n in graph) else 'fail', 'expected': 'numeric strings; no synthetic identifiers'},
            ])
            if species == 'male':
                for v in r['validation']:
                    expected = 25000
                    near = abs(v['incoming_synapses'] - expected) / expected <= .1
                    checks.append({'name': f"Giant fiber {v['body_id']}: supplied ≈25k input check", 'status': 'pass' if near else 'differs',
                                   'observed': v, 'expected': '25,000 ±10%; context from supplied brief/video, not an independent replication study'})
        except ValueError as exc:
            checks.append({'name': f'{species}: release available', 'status': 'blocked', 'detail': str(exc)})
    checks.extend([
        {'name': 'Cross-sex neuron identity validation', 'status': 'blocked', 'detail': 'Type/side correspondences are provisional; no morphology registration or expert review.'},
        {'name': 'Courtship recording agreement', 'status': 'blocked', 'detail': 'No extracted courtship model and no empirical recording have been validated.'},
    ])
    return checks
