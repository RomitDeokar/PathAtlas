"""Immutable fixture Parquet tables and bounded DuckDB queries; never a whole Python graph."""
import hashlib
import json
import threading
from pathlib import Path
import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
from ..config import CACHE, MAX_NODES, MAX_EDGES
from .fixtures import fixture

_LOCK = threading.Lock()


def ensure_cache():
    with _LOCK:
        CACHE.mkdir(parents=True, exist_ok=True)
        (CACHE / 'queries').mkdir(exist_ok=True)
        for species in ['male', 'female']:
            for circuit in ['escape', 'courtship']:
                nodes, edges = fixture(species, circuit)
                for name, rows in [('nodes', nodes), ('edges', edges)]:
                    path = CACHE / f'{species}-{circuit}-{name}.parquet'
                    if not path.exists():
                        pq.write_table(pa.Table.from_pylist(rows), path)


def load_subgraph(species, circuit, min_weight=1):
    ensure_cache()
    with duckdb.connect() as db:
        db.execute("SET memory_limit='256MB'")
        npath = str(CACHE / f'{species}-{circuit}-nodes.parquet')
        epath = str(CACHE / f'{species}-{circuit}-edges.parquet')
        if db.execute('SELECT count(*) FROM read_parquet(?)', [npath]).fetchone()[0] > MAX_NODES:
            raise ValueError('Subgraph exceeds the 4,999-node limit; narrow the cache query.')
        count = db.execute('SELECT count(*) FROM read_parquet(?) WHERE weight >= ?', [epath,min_weight]).fetchone()[0]
        if count > MAX_EDGES:
            raise ValueError('Subgraph exceeds the edge budget; narrow the cache query.')
        nodes = db.execute('SELECT * FROM read_parquet(?)', [npath]).to_arrow_table().to_pylist()
        edges = db.execute('SELECT * FROM read_parquet(?) WHERE weight >= ?', [epath,min_weight]).to_arrow_table().to_pylist()
    return nodes, edges


def save_query(result):
    """Persist exact structural/modeled output, not a behavioral observation."""
    ensure_cache()
    payload = json.dumps(result, sort_keys=True, separators=(',', ':'), allow_nan=False)
    query_id = hashlib.sha256(payload.encode()).hexdigest()[:24]
    path = CACHE / 'queries' / f'{query_id}.json'
    with _LOCK:
        if not path.exists():
            tmp = path.with_suffix('.tmp')
            tmp.write_text(payload)
            tmp.replace(path)
    return {**result, 'query_id': query_id}


def read_query(query_id):
    if not query_id or any(c not in 'abcdef0123456789' for c in query_id) or len(query_id) != 24:
        raise KeyError('Unknown query ID')
    path = CACHE / 'queries' / f'{query_id}.json'
    if not path.is_file():
        raise KeyError('Unknown query ID')
    return {**json.loads(path.read_text()), 'query_id': query_id}
