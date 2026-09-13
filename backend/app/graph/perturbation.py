import random
import statistics
from .pathfinding import top_paths


def knockout(graph, source, targets, selected, max_hops, top_k, seed=42, controls=100):
    """A virtual structural lesion and approximate degree-matched controls, not observed behavior."""
    selected = sorted(set(selected))
    baseline, truncated = top_paths(graph,source,targets,max_hops,top_k)
    perturbed = graph.copy()
    perturbed.remove_nodes_from(selected)
    after, cut = top_paths(perturbed,source,targets,max_hops,top_k)
    base_strength = sum(p['strength'] for p in baseline)
    after_strength = sum(p['strength'] for p in after)
    loss = lambda value: round(100*(1-value/base_strength),2) if base_strength else 0.0
    rng, random_losses, distances = random.Random(seed), [], []
    # Match endpoint eligibility to the selected lesion; do not compare a source to an interneuron.
    endpoints = {source, *targets}
    candidate_sets = {node: [n for n in graph if (n in endpoints) == (node in endpoints)] for node in selected}
    for _ in range(controls):
        chosen = []
        for node in selected:
            candidates = [n for n in candidate_sets[node] if n not in chosen]
            delta = min(abs(graph.degree[n]-graph.degree[node]) for n in candidates)
            nearest = sorted(n for n in candidates if abs(graph.degree[n]-graph.degree[node]) == delta)
            chosen.append(rng.choice(nearest))
            distances.append(delta)
        control = graph.copy()
        control.remove_nodes_from(chosen)
        paths, control_cut = top_paths(control,source,targets,max_hops,top_k)
        cut = cut or control_cut
        random_losses.append(loss(sum(p['strength'] for p in paths)))
    baseline_routes = {tuple(p['nodes']) for p in baseline}
    after_routes = {tuple(p['nodes']) for p in after}
    ordered = sorted(random_losses)
    return {'selected': selected, 'baseline_paths':baseline, 'paths':after,
            'surviving':len(after_routes & baseline_routes), 'rerouted':len(after_routes-baseline_routes),
            'lost':len(baseline_routes-after_routes), 'redundancy':max(0,len(after)-1),
            'strength_loss_pct':loss(after_strength), 'target_reachable':bool(after),
            'search_truncated':truncated or cut, 'controls':{'seed':seed,'n':controls,
            'mean_loss_pct':round(statistics.mean(random_losses),2),
            'interval_95':[ordered[int(.025*(controls-1))],ordered[int(.975*(controls-1))]],
            'losses':random_losses,'mean_degree_mismatch':round(statistics.mean(distances),3),
            'method':'Uniform sampling among nearest-degree eligible nodes, without replacement per trial; includes selected nodes in null population.'},
            'limitation':'Counts and inverse-cost sums are top-k bounded route metrics, not whole-graph resilience or behavioral effects.'}
