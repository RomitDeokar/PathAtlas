"""Rebuild small, attributed escape snapshots from official public release tables.

Run from the repository root: python -m backend.app.data.ingest --species both
Full tables are streamed Arrow -> Parquet; DuckDB filters before Python graphs.
This is an anatomical subset, not a validated escape-behavior model.
"""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

import duckdb
import pyarrow as pa
import pyarrow.ipc as ipc
import pyarrow.parquet as pq

from ..config import CACHE, CAVEAT

RELEASES = Path(__file__).parent / 'releases'
MALE_BASE = 'https://storage.googleapis.com/flyem-male-cns/v1.0/connectome-data/flat-connectome/'
BANC_BASE = 'https://storage.googleapis.com/lee-lab_brain-and-nerve-cord-fly-connectome/compiled_data/banc_888/'
URLS = {
    'male': {
        'nodes': MALE_BASE + 'body-annotations-male-cns-v1.0-minconf-0.5.feather',
        'edges': MALE_BASE + 'connectome-weights-male-cns-v1.0-minconf-0.5.feather',
    },
    'female': {
        'nodes': 'https://raw.githubusercontent.com/htem/BANC-project/main/data/meta/banc_888_meta_20260521.parquet',
        'edges': BANC_BASE + 'banc_888_edgelist_simple_v3.feather',
    },
}


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def download(url, path):
    """Retrieve an official static release; never fall back to synthetic data."""
    if path.exists():
        return
    tmp = path.with_suffix('.download')
    with urlopen(url, timeout=90) as response, tmp.open('wb') as out:
        while chunk := response.read(1024 * 1024):
            out.write(chunk)
    tmp.replace(path)


def parquet_from_arrow(path, output):
    """Stream record batches, never materialize a full connectome table in RAM."""
    if output.exists():
        return
    tmp = output.with_suffix('.partial')
    with pa.memory_map(str(path), 'r') as source:
        reader = ipc.open_file(source)
        with pq.ParquetWriter(tmp, reader.schema, compression='zstd') as writer:
            for i in range(reader.num_record_batches):
                writer.write_batch(reader.get_batch(i))
    tmp.replace(output)


def build(species):
    raw = CACHE / 'raw'
    raw.mkdir(parents=True, exist_ok=True)
    RELEASES.mkdir(exist_ok=True)
    source_files = {}
    for name, url in URLS[species].items():
        path = raw / f'{species}_{name}{Path(url).suffix}'
        download(url, path)
        source_files[name] = {'url': url, 'sha256': digest(path), 'bytes': path.stat().st_size}
        if path.suffix == '.feather':
            parquet_from_arrow(path, raw / f'{species}_{name}.parquet')
    with duckdb.connect(config={'memory_limit': '180MB', 'threads': 1}) as db:
        db.execute('SET temp_directory=?', [str(raw / 'duckdb_tmp')])
        db.read_parquet(str(raw / f'{species}_nodes.parquet')).create_view('annotations')
        db.read_parquet(str(raw / f'{species}_edges.parquet')).create_view('raw_edges')
        if species == 'male':
            db.execute('''CREATE VIEW neurons AS SELECT CAST(bodyId AS VARCHAR) AS id,
                type, instance, superclass AS category, somaSide AS side,
                CAST(mancBodyid AS BIGINT) AS manc_id, mancType AS manc_type,
                NULL::VARCHAR AS transmitter, NULL::VARCHAR AS candidate_male_id,
                status FROM annotations''')
            db.execute('''CREATE VIEW edges AS SELECT CAST(body_pre AS VARCHAR) AS source,
                CAST(body_post AS VARCHAR) AS target, weight FROM raw_edges''')
        else:
            db.execute('''CREATE VIEW neurons AS SELECT CAST(root_id AS VARCHAR) AS id, cell_type AS type,
                cell_type AS instance, super_class AS category,
                CASE side WHEN 'left' THEN 'L' WHEN 'right' THEN 'R' ELSE side END AS side,
                NULL::BIGINT AS manc_id, manc_cell_type AS manc_type,
                neurotransmitter_predicted_v3 AS transmitter, malecns_match AS candidate_male_id,
                status FROM annotations''')
            db.execute('''CREATE VIEW edges AS SELECT CAST(pre AS VARCHAR) AS source, CAST(post AS VARCHAR) AS target,
                count AS weight FROM raw_edges''')
        gf = db.execute("SELECT id FROM neurons WHERE type='DNp01' ORDER BY id").fetchnumpy()['id'].tolist()
        if len(gf) != 2:
            raise ValueError('Expected exactly two annotated DNp01 cells; review release before continuing.')
        # Materialize the tiny GF neighborhood once instead of rescanning gigabytes per cell.
        db.execute('''CREATE TEMP TABLE gf_edges AS SELECT * FROM edges
            WHERE source IN (SELECT unnest(?)) OR target IN (SELECT unnest(?))''', [gf, gf])
        checks = db.execute('''SELECT target AS body_id, SUM(weight)::BIGINT AS incoming_synapses,
            COUNT(DISTINCT source) AS presynaptic_bodies FROM gf_edges
            WHERE target IN (SELECT unnest(?)) GROUP BY target ORDER BY target''', [gf]).to_arrow_table().to_pylist()
        selected = set(gf)
        # The selection contract is explicit: four strongest LPLC2 and four LC4
        # inputs per GF, six strongest annotated VNC intrinsic outputs per GF,
        # and all annotated TTMn motor cells. It is not a complete circuit.
        for g in gf:
            for typ in ['LPLC2', 'LC4']:
                rows = db.execute('''SELECT e.source FROM gf_edges e JOIN neurons n ON n.id=e.source
                    WHERE e.target=? AND n.type=? ORDER BY e.weight DESC,e.source LIMIT 4''', [g, typ]).fetchall()
                selected.update(r[0] for r in rows)
            rows = db.execute('''SELECT e.target FROM gf_edges e JOIN neurons n ON n.id=e.target
                WHERE e.source=? AND n.category IN ('vnc_intrinsic','ventral_nerve_cord_intrinsic')
                ORDER BY e.weight DESC,e.target LIMIT 6''', [g]).fetchall()
            selected.update(r[0] for r in rows)
        selected.update(r[0] for r in db.execute("SELECT id FROM neurons WHERE type='TTMn' OR manc_type='TTMn'").fetchall())
        if not 1 < len(selected) <= 80:
            raise ValueError('Selection exceeds the 80-neuron release contract.')
        selected = sorted(selected)
        nodes = db.execute('SELECT * FROM neurons WHERE id IN (SELECT unnest(?)) ORDER BY id', [selected]).to_arrow_table().to_pylist()
        edges = db.execute('''SELECT source,target,SUM(weight)::BIGINT AS weight FROM edges
            WHERE source IN (SELECT unnest(?)) AND target IN (SELECT unnest(?)) AND weight>0
            GROUP BY source,target ORDER BY source,target''', [selected, selected]).to_arrow_table().to_pylist()
    for n in nodes:
        stage = 0 if n['type'] in ['LC4', 'LPLC2'] else 2 if n['type'] == 'DNp01' else 4 if n['type'] == 'TTMn' or n['manc_type'] == 'TTMn' else 3
        n.update(body_id=n['id'], synthetic=False, stage=stage, nt='unknown',
                 label=f"{n['type'] or 'Unannotated'} · {n['side'] or '?'}",
                 role=['Visual projection', 'Central brain', 'Descending', 'VNC intrinsic', 'Motor'][stage],
                 region='Leg motor pool' if stage == 4 else n['category'],
                 muscle_mapping='MANC type annotation: TTMn; not independently reviewed' if stage == 4 else 'Not applicable')
    for stage in range(5):
        for slot, n in enumerate(n for n in nodes if n['stage'] == stage):
            n['slot'] = slot
    for e in edges:
        # A transmitter prediction alone does not establish receptor-dependent sign.
        e.update(sign='unknown', synthetic=False)
    right_gf = next(n['id'] for n in nodes if n['type'] == 'DNp01' and n['side'] == 'R')
    possible_sources = {n['id'] for n in nodes if n['type'] == 'LPLC2'}
    source = sorted((e for e in edges if e['source'] in possible_sources and e['target'] == right_gf), key=lambda e: (-e['weight'], e['source']))[0]['source']
    p = {
        'mode': 'release', 'dataset': 'MaleCNS' if species == 'male' else 'BANC',
        'version': 'male-cns:v1.0 · minconf 0.5' if species == 'male' else 'v888 · synapses v3 · size ≥10',
        'biological_validation': 'structural-only', 'caveat': CAVEAT,
        'sources': source_files, 'license': 'CC BY 4.0; attribute the dataset authors',
        'limitations': [
            'Selection-biased bounded snapshot, not a complete escape circuit.',
            'Four strongest LC4 and LPLC2 inputs per GF, six strongest VNC intrinsic outputs per GF, plus TTMn.',
            'Only chemical connectivity is included; gap junctions, receptor physiology and dynamics are omitted.',
            'Transmitter sign is unknown, not inferred from a predicted transmitter label.',
            'MaleCNS confidence filtering and BANC synapse-size filtering are not equivalent.',
            'BANC match annotations may refer to MaleCNS v0.9; no v1.0 identity validation or navis registration was performed.',
            'One specimen per sex cannot establish population-level sex effects.',
        ],
    }
    result = {'species': species, 'circuit': 'escape', 'default_source': source,
              'nodes': nodes, 'edges': edges, 'provenance': p, 'validation': checks}
    payload = json.dumps(result, sort_keys=True, indent=2, allow_nan=False)
    out = RELEASES / f'{species}_escape.json'
    out.write_text(payload + '\n')
    print(f'{species}: {len(nodes)} nodes, {len(edges)} edges; default source {source}')
    print(json.dumps(checks, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--species', choices=['male', 'female', 'both'], default='both')
    args = parser.parse_args()
    for species in ['male', 'female'] if args.species == 'both' else [args.species]:
        build(species)


if __name__ == '__main__':
    main()
