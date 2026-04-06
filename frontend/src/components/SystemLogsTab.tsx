import React, { useEffect, useState, useRef } from 'react';
import { Terminal, Database, Cpu, Activity, Server, RadioTower } from 'lucide-react';

const BOOT_LOGS = [
    "[SYS] Initializing DRC-Env v3 Protocol...",
    "[WARN] GPU Acceleration enabled. PyTorch weights loaded.",
    "[NET] Establishing secure connection to Groq Inference nodes...",
    "[MEM] Allocating 4096MB VRAM for MAPPO Training Matrix.",
    "[DB] Restoring cached topological graphs for Zone routing.",
    "[SYS] Anti-Hallucination Validator online.",
    "[OK] System ready. Awaiting telemetry."
];

const LIVE_LOG_TEMPLATES = [
    "[NET] Incoming ping from Node {node}. Latency: {lat}ms.",
    "[INF] Recalculating casualty vectors for grid {gridId}...",
    "[SYS] Memory pool garbage collection triggered. Freed {mem}MB.",
    "[SEC] Rejecting unauthorized payload from edge device.",
    "[AI] Greedy Heuristic cache hit. Serving cached action.",
    "[AI] Overriding wait penalty at grid {gridId} due to severity spike.",
    "[DB] Syncing step {step} to persistent storage.",
    "[WARN] High resource contention detected on route alpha-9.",
    "[NET] Packet loss detected on satellite downlink. Retrying...",
    "[OK] Data block {block} verified and committed."
];

export function SystemLogsTab() {
    const [logs, setLogs] = useState<string[]>([]);
    const scrollRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        // Run boot sequence
        let bootIndex = 0;
        const bootInterval = setInterval(() => {
            if (bootIndex < BOOT_LOGS.length) {
                setLogs(prev => [...prev, `${new Date().toISOString()} ${BOOT_LOGS[bootIndex]}`]);
                bootIndex++;
            } else {
                clearInterval(bootInterval);
            }
        }, 300);

        return () => clearInterval(bootInterval);
    }, []);

    useEffect(() => {
        // Run live faux logs after 3 seconds
        const liveInterval = setInterval(() => {
            const template = LIVE_LOG_TEMPLATES[Math.floor(Math.random() * LIVE_LOG_TEMPLATES.length)];
            const logLine = template
                .replace('{node}', `0x${Math.floor(Math.random()*16777215).toString(16).toUpperCase()}`)
                .replace('{lat}', Math.floor(Math.random() * 80).toString())
                .replace('{gridId}', ["A","B","C","D","E"][Math.floor(Math.random()*5)])
                .replace('{mem}', Math.floor(Math.random() * 50).toString())
                .replace('{step}', Math.floor(Math.random() * 1000).toString())
                .replace('{block}', `BLK-${Math.floor(Math.random() * 9999)}`);
            
            setLogs(prev => [...prev, `${new Date().toISOString()} ${logLine}`].slice(-100)); // Keep last 100
        }, Math.random() * 2000 + 1000); // Random interval between 1s and 3s

        return () => clearInterval(liveInterval);
    }, []);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [logs]);

    return (
        <div className="w-full bg-[#050505] min-h-[85vh] font-sans selection:bg-emerald-900 selection:text-emerald-100 pb-12 pt-4">
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
                
                {/* Left Side: Terminal */}
                <div className="lg:col-span-3 h-[700px] bg-[#0b0c10] border border-zinc-800 rounded-2xl flex flex-col overflow-hidden shadow-xl relative">
                    <div className="bg-[#12141a] border-b border-zinc-800 p-3 flex justify-between items-center z-10 shrink-0">
                        <div className="flex items-center gap-2 text-zinc-400">
                            <Terminal className="w-4 h-4" />
                            <h3 className="text-xs font-bold uppercase tracking-widest font-mono">Server Instance: Prod-01</h3>
                        </div>
                        <div className="flex gap-2 items-center">
                            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse drop-shadow-[0_0_5px_rgba(16,185,129,1)]"></div>
                            <span className="text-[10px] text-zinc-500 uppercase font-mono tracking-widest">Listening port 8001</span>
                        </div>
                    </div>
                    
                    {/* Scanlines */}
                    <div className="absolute inset-0 pointer-events-none opacity-5 bg-[linear-gradient(transparent_50%,rgba(0,0,0,1)_50%)] bg-[length:100%_4px] mt-12 z-0 mix-blend-overlay"></div>

                    <div ref={scrollRef} className="flex-1 p-5 overflow-y-auto font-mono text-xs sm:text-sm leading-loose space-y-1 z-10 relative" style={{ scrollbarWidth: 'thin', scrollbarColor: '#27272a #0b0c10' }}>
                        {logs.map((log, i) => {
                            let color = "text-zinc-400";
                            if (log.includes("[WARN]")) color = "text-amber-400 font-bold";
                            else if (log.includes("[OK]")) color = "text-emerald-400 font-bold drop-shadow-[0_0_3px_rgba(52,211,153,0.5)]";
                            else if (log.includes("[SEC]")) color = "text-red-500 font-bold drop-shadow-[0_0_3px_rgba(239,68,68,0.5)]";
                            else if (log.includes("[AI]")) color = "text-cyan-400 dropdown-shadow-[0_0_3px_rgba(34,211,238,0.5)]";
                            
                            // Highlight timestamp
                            const splitLog = log.split('] ');
                            const timePart = splitLog[0] + ']';
                            const msgPart = splitLog.slice(1).join('] ');

                            return (
                                <div key={i} className={`animate-in fade-in slide-in-from-bottom-1 duration-300 ${color}`}>
                                    <span className="text-zinc-600 mr-3">{timePart.substring(0, 24)}</span>
                                    {timePart.substring(25)} {msgPart}
                                </div>
                            );
                        })}
                    </div>
                </div>

                {/* Right Side: Server Vitals */}
                <div className="space-y-6">
                    <div className="bg-[#0b0c10] border border-zinc-800 rounded-2xl p-6 shadow-xl space-y-6">
                        <h3 className="text-sm font-bold text-white flex items-center gap-2 border-b border-zinc-800 pb-4"><Activity className="w-4 h-4 text-emerald-400"/> System Vitals</h3>
                        
                        <div className="space-y-2">
                            <div className="flex justify-between text-xs font-mono">
                                <span className="text-zinc-500">CPU Usage</span>
                                <span className="text-emerald-400 font-bold">14%</span>
                            </div>
                            <div className="w-full bg-zinc-900 rounded-full h-1.5 opacity-80">
                                <div className="bg-emerald-400 h-1.5 rounded-full" style={{ width: '14%' }}></div>
                            </div>
                        </div>

                        <div className="space-y-2">
                            <div className="flex justify-between text-xs font-mono">
                                <span className="text-zinc-500">Memory (VRAM)</span>
                                <span className="text-cyan-400 font-bold">4.2 / 8 GB</span>
                            </div>
                            <div className="w-full bg-zinc-900 rounded-full h-1.5 opacity-80">
                                <div className="bg-cyan-400 h-1.5 rounded-full" style={{ width: '52%' }}></div>
                            </div>
                        </div>

                        <div className="space-y-2">
                            <div className="flex justify-between text-xs font-mono">
                                <span className="text-zinc-500">Network I/O</span>
                                <span className="text-blue-400 font-bold">128 Kbps</span>
                            </div>
                            <div className="w-full bg-zinc-900 rounded-full h-1.5 opacity-80">
                                <div className="bg-blue-400 h-1.5 rounded-full" style={{ width: '30%' }}></div>
                            </div>
                        </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <div className="bg-[#0b0c10] border border-zinc-800 rounded-xl p-4 flex flex-col items-center justify-center gap-2">
                            <Database className="w-6 h-6 text-indigo-400 drop-shadow-[0_0_8px_rgba(129,140,248,0.5)]"/>
                            <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-widest">Redis Cache</span>
                            <span className="text-xs font-mono text-emerald-500">ONLINE</span>
                        </div>
                        <div className="bg-[#0b0c10] border border-zinc-800 rounded-xl p-4 flex flex-col items-center justify-center gap-2">
                            <RadioTower className="w-6 h-6 text-rose-400 drop-shadow-[0_0_8px_rgba(251,113,133,0.5)] animate-pulse"/>
                            <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-widest">SSE Stream</span>
                            <span className="text-xs font-mono text-emerald-500">ACTIVE</span>
                        </div>
                    </div>
                </div>

            </div>
        </div>
    );
}
