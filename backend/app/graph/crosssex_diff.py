"""Compare active route unions, never full connectomes or proven cellular homologs."""
from collections import defaultdict


def scoped_diff(male, female):
    """Structural count differences; annotation groups do not establish biological identity."""
    if male['parameters']['species'] != 'male' or female['parameters']['species'] != 'female':
        raise ValueError('Provide male then female pathway results')
    for key in ['circuit', 'target_region', 'max_hops', 'top_k', 'min_weight', 'mode']:
        if male['parameters'].get(key) != female['parameters'].get(key):
            raise ValueError('Comparisons require identical trace parameters and data modes')
    synthetic = male['provenance']['mode'] == 'synthetic'
    sources = [next(n for n in r['nodes'] if n['id'] == r['parameters']['source_id']) for r in (male, female)]
    if synthetic:
        if sources[0]['label'] != sources[1]['label']:
            raise ValueError('Source fixtures must correspond')
    elif not sources[0].get('type') or sources[0]['type'] != sources[1].get('type'):
        raise ValueError('Select sources with the same annotated cell type; no correspondence was inferred.')

    groups = defaultdict(lambda: {'male': [], 'female': []})

    def scoped(result):
        species = result['parameters']['species']
        pairs = {(a, b) for p in result['paths'] for a, b in zip(p['nodes'], p['nodes'][1:])}
        active = {n for pair in pairs for n in pair}
        if len(active) > 80:
            raise ValueError('Cross-specimen comparison is limited to 80 active pathway neurons per specimen.')
        labels = {}
        for n in result['nodes']:
            if n['id'] not in active:
                continue
            # Unknown types and unknown sides stay specimen-specific; never guess.
            if synthetic:
                key = n['label']
            elif n.get('type') and n.get('side') in ('L', 'R'):
                key = f"{n['type']} · {n['side']}"
            else:
                key = f"unmatched {species}:{n['id']}"
            labels[n['id']] = key
            groups[key][species].append(n['id'])
        counts = defaultdict(int)
        for e in result['edges']:
            if (e['source'], e['target']) in pairs:
                counts[(labels[e['source']], labels[e['target']])] += e['weight']
        return counts

    a, b = scoped(male), scoped(female)
    rows = []
    for key in sorted(a.keys() | b.keys()):
        status = 'female_only' if key not in a else 'male_only' if key not in b else 'reweighted' if a[key] != b[key] else 'shared'
        rows.append({'source': key[0], 'target': key[1], 'male': a.get(key), 'female': b.get(key),
                     'delta': b.get(key, 0) - a.get(key, 0), 'status': status,
                     'confidence': 'synthetic correspondence' if synthetic else 'provisional type/side aggregation; identity unvalidated'})
    return {'edges': rows,
            'counts': {status: sum(r['status'] == status for r in rows)
                       for status in ['shared', 'reweighted', 'male_only', 'female_only']},
            'correspondences': [{'group': key, **members,
                                 'confidence': 'synthetic' if synthetic else 'unvalidated',
                                 'cardinality': f"{len(members['male'])}:{len(members['female'])}"}
                                for key, members in sorted(groups.items())],
            'source_selection': [{'species': r['parameters']['species'], 'id': n['id'], 'label': n['label']}
                                 for r, n in zip((male, female), sources)],
            'scope': 'Union of selected top-k pathways only. Counts are summed within annotated type/side groups. Only-in-path status does not establish absence from the other connectome.',
            'alignment': ('Fixture correspondence by construction; not biological homologs.' if synthetic else
                          'Provisional annotation-group comparison, not a neuron-level homology diff. Repeated types are aggregated, not paired. No navis registration or expert identity review; release filters differ.')}
