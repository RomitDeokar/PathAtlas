"""Deterministic abstract test networks. None of these identifiers are biological IDs."""
from ..config import FIXTURE_VERSION


def fixture(species='male', circuit='escape'):
    stages = [('Sensory', 'S', 3), ('Central brain', 'C', 3), ('Descending', 'D', 2),
              ('VNC premotor', 'V', 3), ('Motor', 'M', 2)]
    nodes = []
    for stage, (role, prefix, count) in enumerate(stages):
        for i in range(1, count + 1):
            key = f'{prefix}{i:02}'
            nodes.append({'id': f'demo-{species}-{key}', 'label': key, 'role': role,
                          'stage': stage, 'slot': i - 1, 'type': None, 'body_id': None,
                          'region': ('Leg motor pool' if i == 1 else 'Wing motor pool') if prefix == 'M' else role,
                          'nt': 'inhibitory' if key == 'C03' else 'unknown' if key == 'V03' else 'excitatory',
                          'synthetic': True, 'version': FIXTURE_VERSION})
    edges = [('S01','C01',180),('S01','C02',105),('S01','C03',48),
             ('S02','C01',125),('S02','C02',84),('S03','C03',95),
             ('C01','D01',230),('C01','D02',76),('C02','D01',130),
             ('C02','D02',95),('C03','D02',55),('D01','V01',280),
             ('D01','V02',122),('D02','V02',160),('D02','V03',62),
             ('V01','M01',210),('V01','M02',80),('V02','M01',132),
             ('V02','M02',175),('V03','M01',42),('V03','M02',72)]
    if species == 'female':
        edges = [(a,b,round(w * (0.74 if a == 'D01' else 1.18))) for a,b,w in edges if (a,b) != ('C01','D02')]
        edges.append(('C03','D01',65))
    if circuit == 'courtship':
        edges = [(a,b,round(w * (1.3 if b.endswith('02') else .8))) for a,b,w in edges]
    lookup = {n['label']: n for n in nodes}
    return nodes, [{'source':lookup[a]['id'], 'target':lookup[b]['id'], 'weight':w,
                    'sign':lookup[a]['nt'], 'synthetic': True} for a,b,w in edges]
