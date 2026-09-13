from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / 'data_cache'
CAVEAT = 'This shows structural connectivity, not proven behavioral function.'
FIXTURE_VERSION = 'synthetic-v1.0'
MAX_NODES = 4999
MAX_EDGES = 30000
SOURCES = [
    {'title': 'MaleCNS v1.0', 'publisher': 'HHMI Janelia · Google Research', 'url': 'https://male-cns.janelia.org/', 'kind': 'Primary dataset', 'note': '166,000+ neurons; 125 million synapses in the full dataset. PathAtlas bundles only an attributed escape-pathway subset.'},
    {'title': 'BANC · v888', 'publisher': 'Bates, Phelps, Kim, Yang et al. · Nature, 2026', 'url': 'https://doi.org/10.1038/s41586-026-10735-w', 'kind': 'Primary dataset', 'note': 'Female brain and nerve cord. Bounded release subset; annotation-group comparisons are provisional, not validated cell matches.'},
    {'title': 'A connectomics milestone', 'publisher': 'Google Research', 'url': 'https://research.google/blog/a-connectomics-milestone-mapping-the-complete-male-fruit-fly-brain/', 'kind': 'Research context', 'note': 'Confirms dataset scope, acquisition process, and links to the primary papers.'},
    {'title': 'Google announcement', 'publisher': 'News from Google · X', 'url': 'https://x.com/NewsFromGoogle/status/2095553014715093022', 'kind': 'Announcement', 'note': 'Context, not independent experimental validation.'},
    {'title': 'The male fly connectome, explained', 'publisher': 'User-supplied video · YouTube', 'url': 'https://www.youtube.com/watch?v=KOwsVDogscY', 'kind': 'Video context', 'note': 'Reviewed for architecture and limitations. Game-controller demos excluded.'},
    {'title': 'Courtship song perception', 'publisher': 'Zhou et al. · eLife, 2015', 'url': 'https://elifesciences.org/articles/08477', 'kind': 'Literature reference', 'note': 'Approximately 35 ms pulse-song interval is context, not an imported validation recording.'},
    {'title': 'MaleCNS data access', 'publisher': 'HHMI Janelia', 'url': 'https://male-cns.janelia.org/download/', 'kind': 'Integration guide', 'note': 'Official neuprint-python access requires an account and API token.'},
    {'title': 'BANC reproducible data products', 'publisher': 'BANC-FlyWire Consortium', 'url': 'https://github.com/htem/BANC-project', 'kind': 'Data and code', 'note': 'Versioned metadata, edge lists, and curated cross-dataset matching resources.'},
]


def provenance():
    return {'mode': 'synthetic', 'version': FIXTURE_VERSION, 'dataset': 'PathAtlas test fixtures',
            'biological_validation': 'blocked', 'caveat': CAVEAT,
            'limitations': ['All displayed node identifiers and weights are synthetic test data.',
                           'No real MaleCNS/BANC neurons have been aligned.',
                           'Chemical connectivity alone omits electrical coupling and dynamics.',
                           'A single specimen per sex cannot isolate sex from individual variation.']}
