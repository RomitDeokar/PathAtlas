
def scoped_diff(male, female):
    """Compare only top-k route unions. Fixture pairs are NOT biological homologs."""
    if male['parameters']['species'] != 'male' or female['parameters']['species'] != 'female':
        raise ValueError('Provide male then female pathway results')
    for key in ['circuit','target_region','max_hops','top_k','min_weight']:
        if male['parameters'][key] != female['parameters'][key]:
            raise ValueError('Comparisons require identical trace parameters')
    if male['parameters']['source_id'].split('-')[-1] != female['parameters']['source_id'].split('-')[-1]:
        raise ValueError('Source fixtures must correspond')
    def scoped(result):
        pairs = {(a,b) for p in result['paths'] for a,b in zip(p['nodes'],p['nodes'][1:])}
        return {(e['source'].split('-')[-1],e['target'].split('-')[-1]):e['weight'] for e in result['edges'] if (e['source'],e['target']) in pairs}
    a,b = scoped(male),scoped(female)
    rows = []
    for key in sorted(a.keys() | b.keys()):
        status = 'female_only' if key not in a else 'male_only' if key not in b else 'reweighted' if a[key] != b[key] else 'shared'
        rows.append({'source':key[0], 'target':key[1], 'male':a.get(key), 'female':b.get(key),
                     'delta':b.get(key,0)-a.get(key,0),'status':status,'confidence':'synthetic correspondence only'})
    return {'edges':rows, 'counts':{s:sum(r['status']==s for r in rows) for s in ['shared','reweighted','male_only','female_only']},
            'scope':'Union of selected top-k pathways only; absence here does not establish dataset-wide absence.',
            'alignment':'Fixture correspondence by construction; real navis registration and curated identity review are not completed.'}
