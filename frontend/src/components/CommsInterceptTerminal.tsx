import React, { useEffect, useState, useRef } from 'react';
import { Radio } from 'lucide-react';
import type { SimStep } from '../types';

interface Props {
  steps: SimStep[];
  autoPlay?: boolean;
}

const ACTION_MESSAGES = {
    'airlift': [
        "AIRLIFT-CMD > Priority clearance for {zone}. Severe casualty vector detected.",
        "AIRLIFT-CMD > Scrambling MedEvac to {zone}. Holding pattern established.",
        "AIRLIFT-CMD > Bird is en route to {zone}. ETA 3 Mike."
    ],
    'deploy_team': [
        "GROUND-OPS > Moving rescue convoy to {zone}. Expecting heavy debris.",
        "GROUND-OPS > Tactical team deployed. Destination: {zone}.",
        "GROUND-OPS > Ground units mobilized to {zone}. Checking structural integrity."
    ],
    'send_supplies': [
        "LOGISTICS > Route confirmed. Supplying critical medical aid to {zone}.",
        "LOGISTICS > Dispatching transport. {zone} supply gap critical.",
        "LOGISTICS > Cargo secured. Routing to {zone} immediately."
    ],
    'wait': [
        "AI-OVERSEER > High risk detected. Wait penalty enforced. Re-calculating...",
        "AI-OVERSEER > Operations paused. Scanning telemetry.",
        "SYSTEM > Wait protocol engaged. Awaiting optimal deployment window."
    ]
};

function generateMessage(step: SimStep): string {
    if (!step.action) return "SYSTEM > Analyzing telemetry data...";
    
    // Normalize action name
    let actName = step.action.action;
    if (typeof actName === 'string') {
        if (actName.includes('airlift')) actName = 'airlift';
        else if (actName.includes('deploy')) actName = 'deploy_team';
        else if (actName.includes('supplies')) actName = 'send_supplies';
        else if (actName.includes('wait')) actName = 'wait';
    }

    const target = step.action.to_zone || step.action.from_zone || (step.action as any).zone || 'Unknown';
    const msgList = ACTION_MESSAGES[actName as keyof typeof ACTION_MESSAGES] || ["SYSTEM > Executing unspecified action on {zone}."];
    
    // Pick deterministic but varied message based on step index (or just random, but deterministic is better so it doesn't flicker).
    const msgIndex = (step.reward ? Math.abs(Math.floor(step.reward * 100)) : 0) % msgList.length;
    let text = msgList[msgIndex];
    return text.replace('{zone}', `Zone ${target}`);
}

export function CommsInterceptTerminal({ steps, autoPlay = false }: Props) {
    const [visibleCount, setVisibleCount] = useState(autoPlay ? 0 : steps.length);
    const scrollRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (autoPlay) {
            setVisibleCount(0);
            const interval = setInterval(() => {
                setVisibleCount(prev => {
                    if (prev < steps.length) return prev + 1;
                    clearInterval(interval);
                    return prev;
                });
            }, 800); // New message every 800ms
            return () => clearInterval(interval);
        } else {
            setVisibleCount(steps.length);
        }
    }, [steps, autoPlay]);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [visibleCount, steps]);

    const visibleSteps = steps.slice(0, visibleCount);

    return (
        <div className="bg-[#050505] border border-cyan-900/40 rounded-xl overflow-hidden flex flex-col h-full shadow-[0_0_20px_rgba(8,145,178,0.1)] relative">
            {/* Header */}
            <div className="bg-[#0b0c10] border-b border-zinc-800 p-3 flex justify-between items-center z-10 w-full shrink-0">
                <div className="flex items-center gap-2">
                    <Radio className="w-4 h-4 text-cyan-500 animate-pulse" />
                    <h3 className="text-xs font-bold text-cyan-400 uppercase tracking-widest font-mono">Live Comms Intercept</h3>
                </div>
                <div className="flex gap-2 items-center">
                    <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></div>
                    <span className="text-[9px] text-zinc-500 uppercase font-mono tracking-widest">Encrypted SECURE</span>
                </div>
            </div>

            {/* Scanlines Overlay - Add pointer-events-none so it doesn't block scrolling */}
            <div className="absolute inset-0 pointer-events-none opacity-[0.03] bg-[linear-gradient(transparent_50%,rgba(255,255,255,1)_50%)] bg-[length:100%_4px] z-0 mt-10 mix-blend-overlay"></div>

            {/* Terminal Content */}
            <div ref={scrollRef} className="flex-1 p-4 overflow-y-auto font-mono text-[11px] sm:text-xs leading-relaxed space-y-3 z-10 relative scroll-smooth" style={{ scrollbarWidth: 'thin', scrollbarColor: '#27272a transparent' }}>
                {visibleSteps.length === 0 && (
                    <div className="text-zinc-600 italic">Awaiting signals...</div>
                )}
                {visibleSteps.map((step, index) => {
                    const msg = generateMessage(step);
                    const isSystem = msg.startsWith("SYSTEM") || msg.startsWith("AI-OVERSEER");
                    const isAirlift = msg.startsWith("AIRLIFT-CMD");
                    const isGround = msg.startsWith("GROUND-OPS");
                    const isLogistics = msg.startsWith("LOGISTICS");

                    let colorClass = "text-zinc-400";
                    if (isSystem) colorClass = "text-amber-500";
                    if (isAirlift) colorClass = "text-cyan-400 drop-shadow-[0_0_5px_rgba(6,182,212,0.6)]";
                    if (isGround) colorClass = "text-blue-400 font-bold";
                    if (isLogistics) colorClass = "text-orange-400 font-bold";

                    // Calculate a deterministic faux timestamp based on index
                    const time = new Date();
                    time.setSeconds(time.getSeconds() - (steps.length - index));
                    const timestamp = time.toISOString().split('T')[1].slice(0,8);

                    return (
                        <div key={index} className="animate-in fade-in slide-in-from-bottom-2 duration-300">
                            <span className="text-zinc-600 mr-3">[{timestamp}]</span>
                            <span className={`${colorClass}`}>{msg.split(' > ')[0]}</span>
                            <span className="text-zinc-600 mx-2">{'>'}</span>
                            <span className="text-zinc-300">{msg.split(' > ')[1] || msg}</span>
                        </div>
                    );
                })}
                {autoPlay && visibleCount < steps.length && (
                    <div className="text-zinc-500 animate-pulse mt-2">_</div>
                )}
            </div>
            {/* Soft gradient at bottom to fade out text if crowded */}
            <div className="h-4 bg-gradient-to-t from-[#050505] to-transparent absolute bottom-0 left-0 right-0 z-10 pointer-events-none"></div>
        </div>
    );
}
