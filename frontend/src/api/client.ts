export type Species = 'male' | 'female';
export type Circuit = 'escape' | 'courtship';
export type Tab = 'explorer' | 'compare' | 'knockout' | 'simulation' | 'evidence';
export interface Neuron { id: string; label: string; role: string; stage: number; slot: number; region: string; nt: string; body_id: string | null; }
export interface Edge { source: string; target: string; weight: number; sign: string; }
export interface Route { rank: number; nodes: string[]; strength: number; cost: number; bottleneck: number; hops: number; }
export interface Params { source_id: string; target_region: string; species: Species; max_hops: number; top_k: number; min_weight: number; circuit: Circuit; }
export interface Provenance { mode: string; version: string; dataset: string; caveat: string; limitations: string[]; }
export interface Trace { kind: string; query_id: string; parameters: Params; nodes: Neuron[]; edges: Edge[]; paths: Route[]; targets: string[]; search_truncated: boolean; provenance: Provenance; ranking: string; }
export interface Lesion { query_id: string; selected: string[]; paths: Route[]; surviving: number; rerouted: number; lost: number; redundancy: number; strength_loss_pct: number; target_reachable: boolean; controls: {n: number; seed: number; mean_loss_pct: number; interval_95: number[]; losses: number[]; mean_degree_mismatch: number; method: string;}; limitation: string; }
export interface Difference { query_id: string; edges: {source: string; target: string; male: number | null; female: number | null; delta: number; status: string; confidence: string}[]; counts: Record<string,number>; scope: string; alignment: string; }
export interface Simulation { query_id: string; engine: string; parameters: {weight_scheme: string; tau_ms: number; min_weight: number;}; spikes: {neuron: number; time: number}[]; motor_spikes_ms: number[]; labels: string[]; spike_count: number; mean_ipi_ms: number | null; reference: {note: string}; assumptions: string[]; }
export interface Sweep {query_id: string; runs: {scheme: string; tau_ms: number; threshold: number; spike_count: number; mean_ipi_ms: number | null}[]; total_runs: number; active_runs: number; conclusions: {label: string; robust: boolean}[]; validation: string; }
export interface Source {title: string; publisher: string; url: string; kind: string; note: string; }
export interface Sources {sources: Source[]; gates: {name: string; status: string; detail: string}[]; }
export interface Stats {query_id: string; nodes: number; edges: number; reciprocal_pairs: number; feedforward_loops: number; density: number; bottlenecks: {id: string; score: number; degree: number}[]; }
export async function api<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`/api${path}`, {signal, ...(body ? {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)} : {})});
  if (!response.ok) { const error = await response.json().catch(() => ({})); throw new Error(typeof error.detail === 'string' ? error.detail : `Request failed (${response.status}). Please check your parameters.`); }
  return response.json();
}
export const traceQuery = (p: Params) => '/pathway?' + new URLSearchParams(Object.entries(p).map(([k,v]) => [k,String(v)])).toString();
export const short = (id: string) => id.split('-').at(-1) || id;
export function download(queryId: string, format = 'json') { const a = document.createElement('a'); a.href = `/api/export?query_id=${queryId}&format=${format}`; a.download = ''; a.click(); }
