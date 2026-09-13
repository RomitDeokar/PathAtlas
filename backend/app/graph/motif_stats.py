import networkx as nx


def motif_stats(graph):
    reciprocal = sum(graph.has_edge(b,a) for a,b in graph.edges)//2
    loops = sum(1 for a,b in graph.edges for c in graph.successors(b) if c != a and graph.has_edge(a,c))
    scores = nx.betweenness_centrality(graph,weight='cost')
    return {'nodes':len(graph),'edges':len(graph.edges),'reciprocal_pairs':reciprocal,
            'feedforward_loops':loops,'density':round(nx.density(graph),4),
            'bottlenecks':[{'id':n,'score':round(v,4),'degree':graph.degree[n]} for n,v in sorted(scores.items(),key=lambda x:-x[1])[:8]],
            'degree_distribution':[{'id':n,'degree':graph.degree[n]} for n in graph]}
