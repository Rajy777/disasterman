import React, { useState, useMemo } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import { simulate } from '../api/client';
import type { SimResult, TaskInfo } from '../types';
import { Zap } from 'lucide-react';
import { CommsInterceptTerminal } from './CommsInterceptTerminal';

interface Props {
  tasks: TaskInfo[];
}

const ACTION_LABELS: Record<string, string> = {
    'deploy_team': 'Dispatch Rescue (Ground)',
    'send_supplies': 'Route Supply Convoy',
    'airlift': 'Call Emergency Airlift',
    'wait': 'Wait Penalty Applied'
};
const ACTION_COLORS: Record<string, string> = {
    'deploy_team': 'bg-blue-600/90 text-blue-100',
    'send_supplies': 'bg-orange-500/90 text-orange-100',
    'airlift': 'bg-cyan-600/90 text-cyan-100',
    'wait': 'bg-red-800/90 text-red-100'
};

const SectionHeader = ({ title, subtitle }: { title: string, subtitle?: string }) => (
    <div className="mb-4 flex flex-col">
        <h3 className="text-lg font-bold text-cyan-50 tracking-wider uppercase text-shadow-sm shadow-blue-500/20">{title}</h3>
        {subtitle && <p className="text-[10px] sm:text-xs text-zinc-400 font-mono tracking-tight">{subtitle}</p>}
    </div>
);

function ZoneContentionMatrix({ data }: { data: { zones: string[], matrix: (number | null)[][] } }) {
  const { zones, matrix } = data;
  if (!zones.length) return <div className="text-zinc-600 text-sm italic flex h-full items-center justify-center">Run simulation to process matrix.</div>;

  return (
    <div className="bg-[#0b0c10] border border-zinc-800/80 rounded-xl p-4 md:p-6 w-full h-full flex flex-col relative overflow-hidden">
      <div className="absolute top-0 right-0 p-4 opacity-10 blur-xl pointer-events-none">
         <div className="w-32 h-32 bg-red-500 rounded-full"></div>
      </div>
      <SectionHeader title="Inter-Zone Escalation Likelihood" subtitle="Predictive conflict over shared strategic resources computed from live step history" />
      <div className="flex-1 flex flex-col overflow-auto min-w-max">
        {/* Header Row */}
        <div className="grid mb-2" style={{ gridTemplateColumns: `40px repeat(${zones.length}, minmax(30px, 1fr))` }}>
            <div className="text-center"></div>
            {zones.map(z => <div key={z} className="text-center text-[10px] font-bold text-zinc-500">{z}</div>)}
        </div>
        {/* Body Rows */}
        {zones.map((z1, rIdx) => (
          <div key={z1} className="grid relative group" style={{ gridTemplateColumns: `40px repeat(${zones.length}, minmax(30px, 1fr))` }}>
            <div className="flex items-center justify-end pr-3 text-[10px] font-bold text-zinc-500">{z1}</div>
            {zones.map((z2, cIdx) => {
              const val = matrix[rIdx][cIdx];
              let bg = "bg-[#111318]";
              let text = "";
              let shadow = "";
              
              if (val === null) text = "•";
              else if (val >= 50) { bg = "bg-red-600"; text = `${val}%`; shadow = "shadow-[0_0_15px_rgba(220,38,38,0.7)] z-10 scale-105"; }
              else if (val >= 25) { bg = "bg-orange-600"; text = `${val}%`; shadow = "shadow-[0_0_10px_rgba(234,88,12,0.4)] z-10 scale-105"; }
              else if (val >= 10) { bg = "bg-yellow-600/80"; text = `${val}%`; }
              else if (val > 0) { text = `${val}%`; }
              else { text = "0%"; }

              return (
                <div key={z2} className={`relative flex items-center justify-center p-1.5 sm:p-2 text-[10px] font-bold border border-[#0b0c10] transition-colors duration-300 ${bg} ${shadow}`}>
                   <span className={val === null || val === 0 ? "text-zinc-600" : "text-white"}>{text}</span>
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

function SmallChart({ data, dataKey, color, title, criticalAt }: any) {
    if (!data.length) return <div className="h-[200px] bg-[#12141a] rounded flex items-center justify-center text-zinc-600 text-xs italic border border-zinc-800">Awaiting data</div>;
    return (
        <div className="bg-[#12141a] rounded-lg p-3 border border-zinc-800/50 flex flex-col h-[200px]">
           <div className="text-sm font-semibold text-zinc-300 mb-1">{title}</div>
           <ResponsiveContainer width="100%" height="100%">
               <LineChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                   <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                   <XAxis dataKey="step" tick={{ fill: '#71717a', fontSize: 10 }} tickLine={false} axisLine={false} tickMargin={5} />
                   <YAxis tick={{ fill: '#71717a', fontSize: 10 }} tickLine={false} axisLine={false} />
                   <Tooltip contentStyle={{ backgroundColor: '#18181b', border: '1px solid #3f3f46', borderRadius: '8px' }} itemStyle={{ color: '#06b6d4', fontWeight: 'bold' }} />
                   <ReferenceLine y={criticalAt} stroke="#ef4444" strokeDasharray="3 3" label={{ position: 'insideBottomRight', value: 'Critical', fill: '#ef4444', fontSize: 10 }} />
                   <Line type="monotone" dataKey={dataKey} stroke={color} strokeWidth={2} dot={false} activeDot={{ r: 4, fill: color }} />
               </LineChart>
           </ResponsiveContainer>
        </div>
    );
}

function ResourceHistory({ data }: { data: any[] }) {
  return (
    <div className="bg-[#0b0c10] border border-zinc-800/80 rounded-xl p-4 md:p-6 w-full h-full flex flex-col">
       <div className="flex justify-between items-start mb-4">
          <SectionHeader title="Resource History" subtitle="Global Live Trend Analytics" />
       </div>
       <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 flex-1">
           <SmallChart data={data} dataKey="unattended" color="#0ea5e9" title="Total Unattended Casualties" criticalAt={30} />
           <SmallChart data={data} dataKey="supply_gap" color="#10b981" title="Aggregate Supply Deficit" criticalAt={60} />
           <SmallChart data={data} dataKey="severity" color="#f59e0b" title="Max Severity Spike %" criticalAt={80} />
           <SmallChart data={data} dataKey="logistics" color="#f97316" title="Logistics Criticality %" criticalAt={40} />
       </div>
    </div>
  );
}

function AgentNetworkRadar({ result }: { result: SimResult | null }) {
  // Try to find PyTorch scores from the most critical step
  const lastStep = result?.steps[result.steps.length - 1];
  const scores = lastStep?.reasoning?.pytorch_scores || [];
  const topScores = [...scores].sort((a, b) => b.score - a.score).slice(0, 4);

  if (!result || !topScores.length) {
     return <div className="bg-[#0b0c10] border border-zinc-800/80 rounded-xl p-6 w-full h-full flex items-center justify-center text-zinc-600 text-sm italic">Run simulation with PyTorch AI agent for radar telemetry.</div>
  }

  const sortedZones = topScores.map(t => ({ zone: t.zone_id, score: Math.round(t.score * 100) }));
  const positions = [
    { top: '12%', left: '50%', transform: '-translate-x-1/2', bg: 'bg-red-600', shadow: 'shadow-[0_0_20px_rgba(220,38,38,0.6)]' },
    { top: '50%', right: '12%', transform: '-translate-y-1/2', bg: 'bg-orange-500', shadow: 'shadow-[0_0_15px_rgba(249,115,22,0.5)]' },
    { bottom: '12%', left: '50%', transform: '-translate-x-1/2', bg: 'bg-indigo-600', shadow: 'shadow-[0_0_15px_rgba(79,70,229,0.5)]' },
    { top: '50%', left: '16%', transform: '-translate-y-1/2', bg: 'bg-emerald-600', shadow: '' },
  ];

  return (
    <div className="bg-[#0b0c10] border border-zinc-800/80 rounded-xl p-4 md:p-6 w-full h-full flex overflow-hidden relative">
      {/* Background circles */}
       <div className="absolute inset-0 flex items-center justify-center opacity-10 pointer-events-none">
           <div className="w-32 h-32 md:w-48 md:h-48 rounded-full border border-zinc-400 absolute"></div>
           <div className="w-64 h-64 md:w-80 md:h-80 rounded-full border border-dashed border-zinc-400 absolute"></div>
       </div>

       <div className="flex-1 relative flex items-center justify-center">
            <svg className="w-full h-full absolute inset-0 text-zinc-600 pointer-events-none">
                {sortedZones[0] && <line x1="50%" y1="50%" x2="50%" y2="20%" stroke="url(#redGlow)" strokeWidth="3" />}
                {sortedZones[1] && <line x1="50%" y1="50%" x2="80%" y2="50%" stroke="url(#redGlow)" strokeWidth="2" />}
                {sortedZones[2] && <line x1="50%" y1="50%" x2="50%" y2="80%" stroke="#1e3a8a" strokeWidth="2" />}
                {sortedZones[3] && <line x1="50%" y1="50%" x2="25%" y2="50%" stroke="#1e3a8a" strokeWidth="1" />}
                <defs>
                   <linearGradient id="redGlow" x1="0%" y1="0%" x2="100%" y2="100%">
                      <stop offset="0%" stopColor="#ef4444" />
                      <stop offset="100%" stopColor="#f97316" />
                   </linearGradient>
                </defs>
            </svg>

            {/* Nodes */}
            {sortedZones.map((z, i) => (
                <div key={z.zone} className="absolute flex flex-col items-center z-10" style={{ top: positions[i].top, left: positions[i].left, right: positions[i].right, bottom: positions[i].bottom, transform: positions[i].transform }}>
                    <div className={`w-8 h-8 md:w-10 md:h-10 rounded-full flex items-center justify-center font-bold text-white ${positions[i].bg} ${positions[i].shadow}`}>{z.zone}</div>
                    <div className="text-[10px] text-zinc-400 mt-1 font-bold">Node {z.zone}</div>
                    <div className="text-white bg-black/50 px-1 rounded text-[10px] mt-0.5 font-bold border border-zinc-700">{z.score}%</div>
                </div>
            ))}

            <div className="absolute w-12 h-12 md:w-16 md:h-16 rounded-full bg-cyan-500 flex items-center justify-center font-bold text-white shadow-[0_0_30px_rgba(6,182,212,0.8)] z-10 text-lg border-2 border-white">
                HQ
            </div>
       </div>

       <div className="w-1/3 md:w-64 border-l border-zinc-800/50 pl-4 md:pl-6 py-2 flex flex-col h-full bg-gradient-to-r from-transparent to-[#050608]">
           <div className="mb-6">
               <h4 className="text-[10px] md:text-xs font-bold text-cyan-600 uppercase tracking-widest mb-3">Attention Rank</h4>
               <div className="space-y-3">
                   {sortedZones.map((z, i) => (
                       <React.Fragment key={z.zone}>
                          <div className={`flex justify-between text-xs md:text-sm font-black ${i===0?'text-red-500':i===1?'text-orange-500':i===2?'text-indigo-400':'text-zinc-500'}`}>
                             <span>{i+1}. Zone {z.zone}</span><span>{z.score}%</span>
                          </div>
                          <div className={`h-px ${i===0?'bg-red-900/30':i===1?'bg-orange-900/30':i===2?'bg-indigo-900/30':'bg-zinc-800'}`}></div>
                       </React.Fragment>
                   ))}
               </div>
           </div>
           
           <div className="flex-1 overflow-auto">
               <h4 className="text-[10px] md:text-xs font-bold text-cyan-500 uppercase tracking-widest mb-2">Network Rationale</h4>
               <p className="text-[10px] text-zinc-400 leading-relaxed font-mono">
                   Live API data extraction successful. Neural ranking algorithm evaluates {sortedZones[0]?.zone} as critical failure vector. Deep routing protocols initiated. 
               </p>
               <div className="mt-3 text-[9px] text-zinc-600 flex items-center gap-1">
                   Engine: <span className="text-cyan-600 border-b border-cyan-900 border-dashed">{result.agent} pipeline</span>
               </div>
           </div>
       </div>
    </div>
  );
}

function StrategyHeatmap({ displayData, mode, setMode }: any) {
  const { actions, zones, matrix } = displayData;

  if (!zones?.length) return <div className="bg-[#0b0c10] border border-zinc-800/80 rounded-xl p-6 w-full h-full flex items-center justify-center text-zinc-600 text-sm italic">Run simulation to populate heatmap.</div>;

  return (
    <div className="bg-[#0b0c10] border border-zinc-800/80 rounded-xl p-4 md:p-6 w-full h-full flex flex-col">
       <div className="flex justify-between items-center mb-4">
          <SectionHeader title="Strategy Heatmap" subtitle="Actual API action frequencies by zone" />
          <div className="flex gap-2 text-[10px] font-bold uppercase tracking-wider">
              <button onClick={() => setMode('type')} className={`px-3 py-1 rounded transition-colors ${mode === 'type' ? 'bg-cyan-900/40 text-cyan-400 border border-cyan-800/50' : 'text-zinc-500 hover:text-zinc-300'}`}>By type</button>
              <button onClick={() => setMode('spread')} className={`px-3 py-1 rounded transition-colors ${mode === 'spread' ? 'bg-cyan-900/40 text-cyan-400 border border-cyan-800/50' : 'text-zinc-500 hover:text-zinc-300'}`}>By spread</button>
          </div>
       </div>

       <div className="flex-1 w-full overflow-x-auto">
           {mode === 'type' ? (
               <table className="w-full text-left border-collapse min-w-max">
                   <thead>
                       <tr>
                           <th className="p-2 text-xs text-zinc-600 font-semibold uppercase tracking-widest min-w-[200px]">Enacted Strategy</th>
                           {zones.map((z: string) => <th key={z} className="p-2 text-center text-xs text-cyan-100 font-semibold"><div className="flex flex-col items-center"><div className="w-1.5 h-1.5 rounded-full bg-cyan-700 mb-1"></div>{z}</div></th>)}
                       </tr>
                   </thead>
                   <tbody>
                       {actions.map((actionKey: string, rIdx: number) => {
                           const rowTotal = matrix[rIdx].reduce((a:number,b:number)=>a+b, 0);
                           if (rowTotal === 0) return null; // hide unused actions
                           
                           return (
                           <tr key={actionKey} className="border-b border-[#18181b] hover:bg-zinc-900/20">
                               <td className="p-2 text-[10px] text-zinc-300 font-bold tracking-wide uppercase border-l-2 border-zinc-700 pl-3">
                                   {ACTION_LABELS[actionKey] || actionKey}
                               </td>
                               {zones.map((z: string, cIdx: number) => {
                                   const val = matrix[rIdx][cIdx];
                                   const colorClass = val > 0 ? (ACTION_COLORS[actionKey] || 'bg-zinc-700 text-white') : 'bg-[#18181b] text-transparent';

                                   return (
                                       <td key={z} className="p-1">
                                          <div className={`w-8 h-6 flex items-center justify-center text-[11px] font-black rounded mx-auto transition-all ${colorClass} ${val > 0 ? 'shadow-sm' : ''}`}>
                                              {val > 0 ? val : ''}
                                          </div>
                                       </td>
                                   )
                               })}
                           </tr>
                       )})}
                   </tbody>
               </table>
           ) : (
               <table className="w-full text-left border-collapse min-w-max">
                   <thead>
                       <tr>
                           <th className="p-2 text-xs text-zinc-600 font-semibold uppercase tracking-widest min-w-[100px]">Node Focus</th>
                           {actions.map((a: string) => {
                               const colTotal = matrix[actions.indexOf(a)].reduce((acc:number,v:number)=>acc+v,0);
                               if (colTotal === 0) return null;
                               return <th key={a} className="p-2 text-center text-[9px] text-zinc-400 font-semibold uppercase">{ACTION_LABELS[a]?.split(' ')[0] || a}</th>
                           })}
                       </tr>
                   </thead>
                   <tbody>
                       {zones.map((z: string, cIdx: number) => (
                           <tr key={z} className="border-b border-[#18181b] hover:bg-zinc-900/20">
                               <td className="p-2 text-[11px] text-cyan-100 font-bold border-l-2 border-cyan-800 pl-3">Zone {z}</td>
                               {actions.map((actionKey: string, rIdx: number) => {
                                   const colTotal = matrix[rIdx].reduce((acc:number,v:number)=>acc+v,0);
                                   if (colTotal === 0) return null;
                                   
                                   const val = matrix[rIdx][cIdx];
                                   const colorClass = val > 0 ? (ACTION_COLORS[actionKey] || 'bg-zinc-700 text-white') : 'bg-[#18181b] text-transparent';

                                   return (
                                       <td key={actionKey} className="p-1">
                                          <div className={`w-12 h-6 flex items-center justify-center text-[10px] font-black rounded mx-auto ${colorClass}`}>
                                              {val > 0 ? val : ''}
                                          </div>
                                       </td>
                                   )
                               })}
                           </tr>
                       ))}
                   </tbody>
               </table>
           )}
       </div>
    </div>
  );
}

export function CommandCenterTab({ tasks }: Props) {
  const [selectedTask, setSelectedTask] = useState(() => tasks[1]?.task_id ?? tasks[0]?.task_id ?? 'task_2');
  const [selectedAgent, setSelectedAgent] = useState<'ai_4stage' | 'greedy' | 'random'>('greedy'); // default greedy so it works instantly without key
  const [result, setResult] = useState<SimResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const [heatmapMode, setHeatmapMode] = useState<'type' | 'spread'>('type');

  const runSimulation = async () => {
    setLoading(true);
    setError(null);
    try {
        const r = await simulate(selectedTask, selectedAgent);
        setResult(r);
    } catch(e: any) {
        setError(e.message || String(e));
    } finally {
        setLoading(false);
    }
  };

  // Math Pipelines
  const tsData = useMemo(() => {
      if (!result) return [];
      return result.steps.map((step, i) => {
          const obs = step.observation;
          if (!obs) return { step: i, unattended: 0, supply_gap: 0, severity: 0, logistics: 0 };
          const unattended = obs.zones.reduce((sum, z) => sum + z.casualties_remaining, 0);
          const supplyGap = obs.zones.reduce((sum, z) => sum + z.supply_gap, 0);
          const maxSeverity = obs.zones.reduce((max, z) => Math.max(max, z.severity), 0) * 100;
          const logistics = (obs.zones.filter(z => z.sos_active || z.road_blocked).length / Math.max(1, obs.zones.length)) * 100;
          return { step: i, unattended, supply_gap: supplyGap, severity: maxSeverity, logistics };
      });
  }, [result]);

  const contentionData = useMemo(() => {
      if (!result || result.steps.length < 2) return { zones: [], matrix: [] };
      const zonesSet = new Set<string>();
      result.steps.forEach(s => s.observation?.zones.forEach(z => zonesSet.add(z.zone_id)));
      const zones = Array.from(zonesSet).sort();
      
      const matrix = zones.map(z1 => zones.map(z2 => z1 === z2 ? null : 0 as number | null));

      for (let i = 1; i < result.steps.length; i++) {
          const prevObs = result.steps[i-1].observation;
          const currObs = result.steps[i].observation;
          if (!prevObs || !currObs) continue;

          const severityDiff = zones.map(zId => {
              const pv = prevObs.zones.find(z => z.zone_id === zId)?.severity || 0;
              const cv = currObs.zones.find(z => z.zone_id === zId)?.severity || 0;
              return cv - pv;
          });

          zones.forEach((z1, rIdx) => {
              zones.forEach((z2, cIdx) => {
                  if (rIdx === cIdx) return;
                  if (severityDiff[rIdx] > 0.05 && severityDiff[cIdx] > 0.05) {
                      matrix[rIdx][cIdx]! += 25;
                  } else if (severityDiff[rIdx] > 0 && severityDiff[cIdx] > 0) {
                      matrix[rIdx][cIdx]! += 10;
                  }
              });
          });
      }
      zones.forEach((z1, rIdx) => {
          zones.forEach((z2, cIdx) => {
              if (matrix[rIdx][cIdx] !== null) {
                  matrix[rIdx][cIdx] = Math.min(100, matrix[rIdx][cIdx]!);
              }
          });
      });
      return { zones, matrix };
  }, [result]);

  const heatmapData = useMemo(() => {
     if (!result) return { actions: [], zones: [], matrix: [] };
     const zonesSet = new Set<string>();
     result.steps.forEach(s => s.observation?.zones.forEach(z => zonesSet.add(z.zone_id)));
     const zones = Array.from(zonesSet).sort();
     const actionTypes = ['deploy_team', 'send_supplies', 'airlift', 'wait'];
     const matrix = actionTypes.map(() => zones.map(() => 0));

     result.steps.forEach(s => {
         const a = s.action;
         if (!a) return;
         const targetZone = a.to_zone || a.from_zone; // some actions only have from_zone or to_zone.
         const target = targetZone || (a as any).zone // fallback
         if (!target) return;
         
         const actName = actionTypes.find(type => typeof a.action === 'string' && a.action.includes(type)) || a.action;
         let rIdx = actionTypes.indexOf(actName);
         if (rIdx === -1) {
             actionTypes.push(actName);
             matrix.push(zones.map(() => 0));
             rIdx = actionTypes.length - 1;
         }
         
         const cIdx = zones.indexOf(target);
         if (rIdx >= 0 && cIdx >= 0) {
             matrix[rIdx][cIdx] += 1;
         }
     });
     return { actions: actionTypes, zones, matrix };
  }, [result]);

  return (
    <div className="w-full bg-[#050505] min-h-[85vh] font-sans selection:bg-cyan-900 selection:text-cyan-100 flex flex-col space-y-4 pb-12">
        {/* API Controls */}
        <div className="bg-[#0b0c10] border border-zinc-800 rounded-2xl p-5 flex flex-wrap gap-4 items-end shadow-xl">
           <div className="flex-1 min-w-[200px]">
               <label className="flex items-center gap-2 text-[11px] text-cyan-500 font-bold mb-2 uppercase tracking-widest"><Zap className="w-3 h-3"/> Target Operation</label>
               <select
                   value={selectedTask}
                   onChange={e => setSelectedTask(e.target.value)}
                   className="w-full bg-[#181a20] border border-zinc-700/50 rounded-lg px-3 py-2.5 text-sm text-white font-medium focus:outline-none focus:ring-1 focus:ring-cyan-500/50"
               >
                   {tasks.map(t => (
                   <option key={t.task_id} value={t.task_id}>{t.name} ({t.difficulty})</option>
                   ))}
               </select>
           </div>
           <div className="flex-1 min-w-[200px]">
               <label className="block text-[11px] text-zinc-500 font-bold mb-2 uppercase tracking-widest">Routing Engine</label>
               <select
                   value={selectedAgent}
                   onChange={e => setSelectedAgent(e.target.value as any)}
                   className="w-full bg-[#181a20] border border-zinc-700/50 rounded-lg px-3 py-2.5 text-sm text-white font-medium focus:outline-none focus:ring-1 focus:ring-zinc-500/50"
               >
                   <option value="greedy">Greedy Heuristic (Fast)</option>
                   <option value="ai_4stage">4-Stage AI (Requires Token)</option>
                   <option value="random">Random Baseline</option>
               </select>
           </div>
           <button
             onClick={runSimulation}
             disabled={loading}
             className="px-6 py-2.5 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white font-bold tracking-wider uppercase text-sm rounded-lg transition-all shadow-[0_0_15px_rgba(8,145,178,0.3)] hover:shadow-[0_0_20px_rgba(8,145,178,0.5)]"
           >
             {loading ? 'Fetching API Data...' : '▶ Initialize Link'}
           </button>
        </div>

        {error && (
            <div className="bg-red-950/50 border border-red-800 rounded-xl p-4 text-red-300 text-sm font-mono flex items-center justify-center">
                ERROR STREAM: {error}
            </div>
        )}

        {/* Dashboard Grids */}
        <div className={`grid grid-cols-1 xl:grid-cols-2 gap-4 h-full transition-opacity duration-500 ${loading ? 'opacity-30 pointer-events-none' : 'opacity-100'}`}>
            <div className="h-[450px]">
                <ZoneContentionMatrix data={contentionData} />
            </div>
            <div className="h-[450px]">
                <AgentNetworkRadar result={result} />
            </div>
            <div className="h-[550px]">
                <ResourceHistory data={tsData} />
            </div>
            <div className="h-[550px]">
                <StrategyHeatmap displayData={heatmapData} mode={heatmapMode} setMode={setHeatmapMode} />
            </div>
            {result && (
                <div className="xl:col-span-2 h-[280px]">
                    <CommsInterceptTerminal steps={result.steps} autoPlay={true} />
                </div>
            )}
        </div>
    </div>
  );
}
