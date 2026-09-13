import { useId, useRef, useState } from 'react';
import { linkHorizontal, scaleSqrt } from 'd3';
import { Maximize2, Minus, Plus, RotateCcw, MousePointer2 } from 'lucide-react';
import type { Neuron, Trace, Route } from '../api/client';

const stages = ['SENSORY', 'CENTRAL BRAIN', 'DESCENDING', 'VNC PREMOTOR', 'MOTOR'];
const colors = ['#5a8f7e','#7da493','#bc995c','#8e91b4','#ae8972'];
interface Props { trace: Trace; selected?: string; onSelect: (n: Neuron) => void; route?: Route; removed?: string[]; surviving?: Route[]; knockout?: boolean; compact?: boolean; }
export function SubwayMap({trace,selected,onSelect,route,removed=[],surviving,knockout,compact}: Props) {
  const [zoom,setZoom] = useState(1); const frame = useRef<HTMLDivElement>(null); const id = useId().replace(/:/g,'');
  const [hover,setHover] = useState<string|null>(null);
  const real=trace.parameters.mode==='release';
  const height=Math.max(420,180+Math.max(...trace.nodes.map(n=>n.slot),0)*105);
  const pos = (n: Neuron): [number,number] => [80+n.stage*175,100+n.slot*105+(n.stage===2||n.stage===4?50:0)];
  const points = new Map(trace.nodes.map(n => [n.id,pos(n)]));
  const active = route ? new Set(route.nodes.slice(1).map((n,i)=>`${route.nodes[i]}:${n}`)) : null;
  const remaining = surviving ? new Set(surviving.flatMap(p=>p.nodes.slice(1).map((n,i)=>`${p.nodes[i]}:${n}`))) : null;
  const thickness = scaleSqrt().domain([1,Math.max(...trace.edges.map(e=>e.weight),300)]).range([1,5]);
  const curve = linkHorizontal<unknown,[number,number]>();
  return <div className={`map-frame ${compact?'compact':''}`} ref={frame}>
    <div className="map-tools"><span className="micro map-label"><span className="live-dot"/> {knockout?'VIRTUAL LESION':'PATHWAY VIEW'} <span className="muted">/ 2D</span></span><div>
      <button title="Zoom out" aria-label="Zoom out" onClick={()=>setZoom(z=>Math.max(.7,z-.15))}><Minus size={15}/></button><span className="zoom-label">{Math.round(zoom*100)}%</span><button title="Zoom in" aria-label="Zoom in" onClick={()=>setZoom(z=>Math.min(1.8,z+.15))}><Plus size={15}/></button><button title="Reset view" aria-label="Reset view" onClick={()=>setZoom(1)}><RotateCcw size={14}/></button><button title="Fullscreen graph" aria-label="Fullscreen graph" onClick={()=>{if(document.fullscreenElement)void document.exitFullscreen();else void frame.current?.requestFullscreen().catch(()=>{});}}><Maximize2 size={14}/></button></div></div>
    <div className="map-scroll"><svg className="subway" viewBox={`0 0 860 ${height}`} style={{width:`${zoom*100}%`,minWidth:compact?580:650}} aria-label={`Interactive ${real?'release':'synthetic'} sensorimotor pathway map`}>
      <defs><pattern id={`dots-${id}`} width="18" height="18" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r=".65" fill="#d9ded6"/></pattern></defs><rect width="860" height={height} fill={`url(#dots-${id})`}/>
      {stages.map((s,i)=><g key={s}><rect x={i*175+7} y="20" width="145" height="24" rx="4" fill="#f5f6f1"/><text x={80+i*175} y="36" textAnchor="middle" className="stage-label">{s}</text><line x1={80+i*175} x2={80+i*175} y1="57" y2={height-60} stroke="#e1e5dc" strokeDasharray="3 6"/></g>)}
      {trace.edges.map(e=>{ const key=`${e.source}:${e.target}`; const dead=removed.includes(e.source)||removed.includes(e.target); const alive=remaining?.has(key); const highlight=active?.has(key); const hot=hover===key; const color=dead?'#d18b80':alive?'#4f9974':e.sign==='inhibitory'?'#c99563':e.sign==='unknown'?'#a7afbc':'#70a591'; return <g key={key} onMouseEnter={()=>setHover(key)} onMouseLeave={()=>setHover(null)}>
        <path d={curve({source:points.get(e.source)!,target:points.get(e.target)!})||''} fill="none" stroke={color} strokeWidth={thickness(e.weight)+(highlight||hot?1.4:0)} strokeOpacity={dead?.32:active&&!highlight?.2:remaining&&!alive?.15:.65} strokeDasharray={dead?'6 5':e.sign==='unknown'?'4 5':undefined}/>
        <path d={curve({source:points.get(e.source)!,target:points.get(e.target)!})||''} fill="none" stroke="transparent" strokeWidth="15"><title>{e.source.split('-').at(-1)} → {e.target.split('-').at(-1)}: {e.weight} {real?'synapse':'synthetic'} count; {e.sign}</title></path>
        {(highlight||hot)&&<g transform={`translate(${(points.get(e.source)![0]+points.get(e.target)![0])/2},${(points.get(e.source)![1]+points.get(e.target)![1])/2})`}><rect x="-17" y="-11" width="34" height="21" rx="5" fill="#f9faf6" stroke="#dce5db"/><text textAnchor="middle" y="4" className="edge-number">{e.weight}</text></g>}
      </g>;})}
      {trace.nodes.map(n=>{ const [x,y]=pos(n); const isSelected=selected===n.id; const dead=removed.includes(n.id); const onPath=route?.nodes.includes(n.id); return <g className="graph-node" key={n.id} transform={`translate(${x},${y})`} tabIndex={0} role="button" aria-label={`${knockout?'Toggle lesion':'Inspect'} ${n.label}, ${n.role}`} aria-pressed={dead||isSelected} onClick={()=>onSelect(n)} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();onSelect(n);}}}>
        {(isSelected||onPath||dead)&&<circle r="24" fill="none" stroke={dead?'#bc6255':isSelected?'#c67751':colors[n.stage]} strokeWidth="1" strokeDasharray={dead?'3 3':undefined} opacity=".5"/>}<circle r="16" fill={dead?'#f1e2dd':'#fafcf8'} stroke={dead?'#bd7567':colors[n.stage]} strokeWidth={isSelected?3:2.5}/><circle r="6" fill={dead?'#bd7567':colors[n.stage]}/>{dead&&<path d="M-6 -6 L6 6 M6 -6 L-6 6" stroke="white" strokeWidth="1.5"/>}
        <rect x="-27" y="25" width="54" height="22" rx="5" fill={isSelected?'#e5ece2':'#f9faf6'}/><text textAnchor="middle" y="41" className="node-label">{n.label}</text><text textAnchor="middle" y="58" className="node-meta">{real?n.id:n.stage===4?n.region.replace(' motor pool','').toLowerCase()+' · fixture':'synthetic cell'}</text>
      </g>;})}
      <text x="430" y={height-13} textAnchor="middle" className="map-footnote">SCHEMATIC STAGES · {real?'RELEASE IDS & SYNAPSE COUNTS':'SYNTHETIC IDENTIFIERS & WEIGHTS'} · NOT AN ANATOMICAL RECONSTRUCTION</text>
    </svg></div>
    <div className="map-legend"><div><span><i className="line green"/>Excitatory*</span><span><i className="line amber"/>Inhibitory*</span><span><i className="line unknown"/>Unknown</span></div><span className="map-hint"><MousePointer2 size={12}/>{knockout?'Click a cell to select a lesion':'Click a cell to inspect'}</span></div>
  </div>;
}
