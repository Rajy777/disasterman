import React, { useState } from 'react';
import { analyzeScenario } from '../api/client';
import { Printer, Download, Sparkles, Map, Target, Server, CheckCircle2, MapPin, Send } from 'lucide-react';

export function StrategyGeneratorTab() {
  const [scenario, setScenario] = useState('');
  const [loading, setLoading] = useState(false);
  const [strategy, setStrategy] = useState('');
  const [error, setError] = useState<string | null>(null);

  const QUICK_SCENARIOS = [
      "Multi-zone earthquake with cascading road failures", 
      "Category 5 hurricane triggering false SOS anomalies",
      "Urban flooding demanding priority airlift routing",
      "Widespread wildfires with supply chain disruptions"
  ];

  const handleGenerate = async () => {
    if (!scenario.trim()) return;
    setLoading(true);
    setStrategy('');
    setError(null);
    try {
        const response = await analyzeScenario(scenario);
        setStrategy(response.strategy);
    } catch(err: any) {
        setError(err.message || String(err));
    } finally {
        setLoading(false);
    }
  };

  const renderMarkdown = (text: string) => {
    return text.split('\n').map((line, i) => {
        if (line.startsWith('# ')) return <h1 key={i} className="text-xl font-bold mt-4 mb-2 text-white">{line.slice(2)}</h1>;
        if (line.startsWith('## ')) return <h2 key={i} className="text-lg font-bold mt-4 mb-2 text-cyan-400">{line.slice(3)}</h2>;
        if (line.startsWith('### ')) return <h3 key={i} className="text-xs font-bold mt-6 mb-2 text-cyan-600 tracking-widest uppercase">{line.slice(4)}</h3>;
        
        let htmlMode = line;
        htmlMode = htmlMode.replace(/\*\*(.*?)\*\*/g, '<strong class="font-bold text-white">$1</strong>');
        htmlMode = htmlMode.replace(/\*(.*?)\*/g, '<em class="italic text-cyan-100">$1</em>');

        if (line.startsWith('- ')) return <li key={i} className="ml-5 list-disc text-sm text-zinc-300 mt-1.5 leading-relaxed" dangerouslySetInnerHTML={{__html: htmlMode.slice(2)}}></li>;
        if (line.trim() === '') return <div key={i} className="h-3"></div>;
        
        return <p key={i} className="text-sm text-zinc-400 mt-1.5 leading-relaxed" dangerouslySetInnerHTML={{__html: htmlMode}}></p>;
    });
  };

  return (
    <div className="w-full bg-[#050505] print:bg-white min-h-[85vh] font-sans selection:bg-cyan-900 selection:text-cyan-100 pb-12 pt-4">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            
            {/* Left Column: Input and Output */}
            <div className="lg:col-span-2 space-y-6">
                
                {/* Input Area */}
                <div className="bg-[#0b0c10] print:hidden border border-zinc-800 rounded-2xl p-6 shadow-xl">
                    <h2 className="text-xl font-bold text-white mb-1">Scenario Analyzer</h2>
                    <p className="text-xs text-zinc-500 mb-6 font-mono">Describe a situation to generate resource allocation strategy</p>

                    <label className="block text-xs font-semibold text-zinc-400 mb-2 uppercase tracking-wide">Describe the scenario</label>
                    <textarea 
                        className="w-full bg-[#12141a] border border-zinc-700/50 rounded-xl p-4 text-sm text-white focus:outline-none focus:ring-2 focus:ring-cyan-500/50 transition-all font-mono resize-none"
                        rows={4}
                        placeholder="e.g. Major metropolitan earthquake strikes 12 zones simultaneously. Expected casualties high. Road blockages likely."
                        value={scenario}
                        onChange={e => setScenario(e.target.value)}
                    ></textarea>

                    <div className="mt-4 mb-6">
                        <div className="flex justify-between items-center mb-3">
                            <label className="block text-[10px] font-bold text-zinc-600 uppercase tracking-widest">Quick Scenarios</label>
                            <button 
                                onClick={() => {
                                    if (navigator.geolocation) {
                                        navigator.geolocation.getCurrentPosition((pos) => {
                                            setScenario(`Emergency response strategy required for disaster occurring at EXACT COORDINATES: ${pos.coords.latitude.toFixed(4)}, ${pos.coords.longitude.toFixed(4)}. Assume severe infrastructural damage.`);
                                        }, () => {
                                            setScenario(`Emergency response strategy required for local area. (Geolocation permission denied)`);
                                        });
                                    }
                                }}
                                className="flex items-center gap-1.5 text-xs bg-cyan-900/30 text-cyan-400 border border-cyan-800/50 hover:bg-cyan-800/40 rounded-lg px-3 py-1.5 transition-colors font-medium"
                            >
                                <MapPin className="w-3.5 h-3.5" /> Locate Disasters Near Me
                            </button>
                        </div>
                        <div className="flex flex-wrap gap-2">
                           {QUICK_SCENARIOS.map(s => (
                               <button 
                                  key={s} 
                                  onClick={() => setScenario(s)}
                                  className="px-3 py-1.5 bg-[#181a20] border border-zinc-700/50 hover:bg-zinc-800 hover:border-zinc-600 hover:text-white text-xs text-zinc-400 rounded-lg transition-all"
                               >
                                   {s}
                               </button>
                           ))}
                        </div>
                    </div>

                    <button 
                       onClick={handleGenerate}
                       disabled={loading || !scenario.trim()}
                       className="w-full bg-cyan-500 hover:bg-cyan-400 disabled:opacity-50 text-black font-bold text-sm py-3 rounded-xl transition-all shadow-[0_0_15px_rgba(6,182,212,0.3)] hover:shadow-[0_0_20px_rgba(6,182,212,0.6)] flex items-center justify-center gap-2"
                    >
                        {loading ? 'Analyzing Vector Space...' : <><Sparkles className="w-4 h-4"/> Generate Strategy</>}
                    </button>
                </div>

                {/* Output Area */}
                <div className={`bg-[#0b0c10] print:bg-white print:border-none print:shadow-none border border-zinc-800 rounded-2xl p-6 shadow-xl transition-opacity duration-500 ${!strategy && !loading && !error ? 'opacity-50' : 'opacity-100'}`}>
                    <div className="flex justify-between items-center mb-6 print:hidden">
                        <h3 className="text-sm font-bold text-cyan-500 uppercase tracking-widest">Generated Strategy</h3>
                        <div className="flex gap-2">
                            <button onClick={() => window.print()} className="flex items-center gap-1.5 px-3 py-1.5 border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 rounded-lg text-xs font-semibold text-white transition-colors"><Printer className="w-3.5 h-3.5"/> Print</button>
                            <button onClick={() => window.print()} className="flex items-center gap-1.5 px-3 py-1.5 border border-cyan-800 bg-cyan-950/30 hover:bg-cyan-900/40 rounded-lg text-xs font-semibold text-cyan-400 transition-colors"><Download className="w-3.5 h-3.5"/> Export PDF</button>
                            <button 
                                onClick={() => {
                                   if (!strategy) return;
                                   const subject = encodeURIComponent("URGENT: Disaster Strategy Report");
                                   const body = encodeURIComponent(strategy);
                                   window.location.href = `mailto:emergency-response@ndrf.gov.in?subject=${subject}&body=${body}`;
                                }}
                                disabled={!strategy}
                                className="flex items-center gap-1.5 px-3 py-1.5 border border-red-800 bg-red-950/30 hover:bg-red-900/40 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-xs font-semibold text-red-400 transition-colors"
                            >
                                <Send className="w-3.5 h-3.5"/> Escalate to NDRF
                            </button>
                        </div>
                    </div>

                    <div className="bg-[#12141a] print:bg-white print:text-black border border-zinc-800/80 print:border-none rounded-xl p-5 min-h-[300px]">
                        {loading && (
                            <div className="h-full w-full flex flex-col items-center justify-center text-cyan-600/50 py-20">
                                <div className="w-8 h-8 border-4 border-cyan-500/20 border-t-cyan-500 rounded-full animate-spin mb-4"></div>
                                <span className="text-xs uppercase tracking-widest font-bold animate-pulse">Running Neural Simulation...</span>
                            </div>
                        )}
                        {error && <div className="text-red-400 text-sm font-mono border border-red-900/50 bg-red-950/20 p-4 rounded-lg">Error: {error}</div>}
                        {!loading && !error && strategy && (
                            <div className="animate-in fade-in slide-in-from-bottom-2 duration-700">
                                {renderMarkdown(strategy)}
                            </div>
                        )}
                        {!loading && !error && !strategy && (
                            <div className="text-zinc-600 text-xs italic text-center py-20">Awaiting scenario input...</div>
                        )}
                    </div>
                </div>

            </div>

            {/* Right Column: Info Cards - Hide on print */}
            <div className="space-y-6 print:hidden">
               
               <div className="bg-[#0b0c10] border border-zinc-800 rounded-2xl p-6 shadow-xl">
                    <h3 className="text-sm font-bold text-white mb-5 flex items-center gap-2"><Server className="w-4 h-4 text-zinc-400"/> System Capabilities</h3>
                    <div className="grid grid-cols-2 gap-3">
                        <div className="bg-[#12141a] border border-zinc-800/50 p-4 rounded-xl">
                            <div className="text-2xl font-black text-blue-400 mb-1 drop-shadow-[0_0_8px_rgba(96,165,250,0.5)]">106</div>
                            <div className="text-[10px] text-zinc-500 uppercase font-semibold">Verified Test Scenarios</div>
                        </div>
                        <div className="bg-[#12141a] border border-zinc-800/50 p-4 rounded-xl">
                            <div className="text-2xl font-black text-green-400 mb-1 drop-shadow-[0_0_8px_rgba(74,222,128,0.5)]">1ms</div>
                            <div className="text-[10px] text-zinc-500 uppercase font-semibold">Triage Latency</div>
                        </div>
                        <div className="bg-[#12141a] border border-zinc-800/50 p-4 rounded-xl">
                            <div className="text-2xl font-black text-orange-400 mb-1 drop-shadow-[0_0_8px_rgba(251,146,60,0.5)]">4-Stage</div>
                            <div className="text-[10px] text-zinc-500 uppercase font-semibold">Agent Pipeline</div>
                        </div>
                        <div className="bg-[#12141a] border border-zinc-800/50 p-4 rounded-xl">
                            <div className="text-2xl font-black text-red-500 mb-1 drop-shadow-[0_0_8px_rgba(239,68,68,0.5)]">10K+</div>
                            <div className="text-[10px] text-zinc-500 uppercase font-semibold">Evaluated Environments</div>
                        </div>
                    </div>
               </div>

               <div className="bg-[#0b0c10] border border-zinc-800 rounded-2xl p-6 shadow-xl">
                   <h3 className="text-sm font-bold text-white mb-5">How It Works</h3>
                   <div className="space-y-4 text-xs font-medium text-zinc-400">
                       <div className="flex gap-3">
                           <div className="w-5 h-5 rounded-full bg-cyan-900/50 border border-cyan-800 flex items-center justify-center text-[10px] text-cyan-400 font-bold shrink-0">1</div>
                           <p>Describe a scenario or select from quick options</p>
                       </div>
                       <div className="flex gap-3">
                           <div className="w-5 h-5 rounded-full bg-cyan-900/50 border border-cyan-800 flex items-center justify-center text-[10px] text-cyan-400 font-bold shrink-0">2</div>
                           <p>DisasterMan AI agents analyze and simulate outcomes</p>
                       </div>
                       <div className="flex gap-3">
                           <div className="w-5 h-5 rounded-full bg-cyan-900/50 border border-cyan-800 flex items-center justify-center text-[10px] text-cyan-400 font-bold shrink-0">3</div>
                           <p>Receive comprehensive resource allocation strategy</p>
                       </div>
                       <div className="flex gap-3">
                           <div className="w-5 h-5 rounded-full bg-cyan-900/50 border border-cyan-800 flex items-center justify-center text-[10px] text-cyan-400 font-bold shrink-0">4</div>
                           <p>Export or print for implementation</p>
                       </div>
                   </div>
               </div>

               <div className="bg-[#0d1218] border border-cyan-900/30 rounded-2xl p-6 shadow-[0_0_20px_rgba(8,145,178,0.05)]">
                   <h3 className="text-sm font-bold text-cyan-500 mb-4">Example Queries</h3>
                   <ul className="space-y-3 text-[11px] text-zinc-400 font-mono">
                       <li className="flex gap-2 items-start"><CheckCircle2 className="w-3.5 h-3.5 text-cyan-700 shrink-0 mt-0.5"/> "Urban flood affecting Zones A, B, C with high casualty risk"</li>
                       <li className="flex gap-2 items-start"><CheckCircle2 className="w-3.5 h-3.5 text-cyan-700 shrink-0 mt-0.5"/> "False SOS signals flooding HQ communication channels"</li>
                       <li className="flex gap-2 items-start"><CheckCircle2 className="w-3.5 h-3.5 text-cyan-700 shrink-0 mt-0.5"/> "Multi-vector cyclone destroying primary land routes"</li>
                       <li className="flex gap-2 items-start"><CheckCircle2 className="w-3.5 h-3.5 text-cyan-700 shrink-0 mt-0.5"/> "Chemical spill trapped victims requiring immediate airlift extraction"</li>
                   </ul>
               </div>

            </div>
        </div>
    </div>
  );
}
