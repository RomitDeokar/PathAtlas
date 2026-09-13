"""Bounded, positive-cost path search on a prefiltered subgraph only."""
import heapq
import networkx as nx
from ..config import MAX_NODES, MAX_EDGES


def graph_from(nodes, edges):
    if len(nodes) > MAX_NODES or len(edges) > MAX_EDGES:
        raise ValueError('Graph exceeds safe subgraph budget')
    graph = nx.DiGraph()
    graph.add_nodes_from((n['id'], n) for n in nodes)
    for e in edges:
        if e['weight'] <= 0 or e['source'] not in graph or e['target'] not in graph:
            raise ValueError('Edges must have positive weights and known endpoints')
        graph.add_edge(e['source'], e['target'], **e, cost=1.0/e['weight'])
    return graph


def top_paths(graph, source, targets, max_hops=5, top_k=5):
    """Rank structural routes by sum(1/count); the inverse cost is not signal strength."""
    if source not in graph:
        return [], False
    frontier = [(0.0, (source,))]
    paths, expanded = [], 0
    while frontier and len(paths) < top_k:
        cost, route = heapq.heappop(frontier)
        expanded += 1
        if expanded > 50000:
            return paths, True
        if route[-1] in targets and len(route) > 1:
            weights = [graph[a][b]['weight'] for a,b in zip(route,route[1:])]
            paths.append({'rank':len(paths)+1, 'nodes':list(route), 'cost':round(cost,8),
                          'strength':round(1/cost,3), 'bottleneck':min(weights), 'hops':len(route)-1})
            continue
        if len(route)-1 >= max_hops:
            continue
        for neighbor in sorted(graph.successors(route[-1])):
            if neighbor not in route:
                heapq.heappush(frontier,(cost+graph[route[-1]][neighbor]['cost'], (*route,neighbor)))
    return paths, False
