import React, { useMemo, useEffect, useRef } from 'react';
import { motion, useScroll, useTransform } from 'framer-motion';
import { Network, Zap, Cpu, Globe2, ShieldAlert, Sparkles, MessageSquare, Radio, Terminal, Database, Server, Component } from 'lucide-react';

interface LandingPageProps {
  onLaunch: () => void;
}

const AgentNetworkCanvas = () => {
    const canvasRef = useRef<HTMLCanvasElement>(null);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        let width = window.innerWidth;
        let height = window.innerHeight;
        canvas.width = width;
        canvas.height = height;

        const handleResize = () => {
            width = window.innerWidth;
            height = window.innerHeight;
            canvas.width = width;
            canvas.height = height;
        };
        window.addEventListener('resize', handleResize);

        const particles: any[] = [];
        const colors = ['#22d3ee', '#f43f5e', '#34d399', '#818cf8']; // Cyan, Rose, Emerald, Indigo

        for (let i = 0; i < 40; i++) {
            particles.push({
                x: Math.random() * width,
                y: Math.random() * height,
                vx: (Math.random() - 0.5) * 2.0,
                vy: (Math.random() - 0.5) * 2.0,
                size: Math.random() * 5 + 4, // Much larger
                color: colors[Math.floor(Math.random() * colors.length)]
            });
        }

        let animationFrameId: number;

        const render = () => {
            ctx.clearRect(0, 0, width, height);

            // Update positions
            particles.forEach(p => {
                p.x += p.vx;
                p.y += p.vy;

                if (p.x < 0 || p.x > width) p.vx *= -1;
                if (p.y < 0 || p.y > height) p.vy *= -1;
            });

            // Draw connections
            const connectionDistance = 180;
            for (let i = 0; i < particles.length; i++) {
                for (let j = i + 1; j < particles.length; j++) {
                    const p1 = particles[i];
                    const p2 = particles[j];
                    const dx = p1.x - p2.x;
                    const dy = p1.y - p2.y;
                    const distance = Math.sqrt(dx * dx + dy * dy);

                    if (distance < connectionDistance) {
                        const opacity = 1 - (distance / connectionDistance);
                        ctx.beginPath();
                        ctx.strokeStyle = `rgba(34, 211, 238, ${opacity * 0.9})`; // Brighter Cyan glowing lines
                        ctx.lineWidth = 2.5; // Thicker lines
                        ctx.moveTo(p1.x, p1.y);
                        ctx.lineTo(p2.x, p2.y);
                        ctx.stroke();
                    }
                }
            }

            // Draw particles
            particles.forEach(p => {
                ctx.beginPath();
                ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
                ctx.fillStyle = p.color;
                ctx.fill();
                
                // Glow
                ctx.shadowBlur = 30; // Brighter glow
                ctx.shadowColor = p.color;
            });
            ctx.shadowBlur = 0; // reset

            animationFrameId = requestAnimationFrame(render);
        };

        render();

        return () => {
            window.removeEventListener('resize', handleResize);
            cancelAnimationFrame(animationFrameId);
        };
    }, []);

    return (
        <canvas 
            ref={canvasRef} 
            className="absolute inset-0 z-10 pointer-events-none opacity-60"
        />
    );
};

const RescueUnitsLayer = () => {
    const units = useMemo(() => Array.from({ length: 12 }).map((_, i) => ({
        id: i,
        startX: Math.random() * 100,
        startY: Math.random() * 100,
        endX: Math.random() * 100,
        endY: Math.random() * 100,
        duration: Math.random() * 20 + 20,
        delay: Math.random() * 10,
        type: Math.random() > 0.5 ? 'AIR' : 'GND',
        targetColor: Math.random() > 0.5 ? 'bg-cyan-500' : 'bg-emerald-500',
        textColor: Math.random() > 0.5 ? 'text-cyan-500' : 'text-emerald-500'
    })), []);

    return (
        <div className="absolute inset-0 z-15 pointer-events-none opacity-60">
            {units.map((u) => (
                <motion.div
                    key={u.id}
                    className={`absolute w-1.5 h-1.5 rounded-full ${u.targetColor}`}
                    initial={{ left: `${u.startX}%`, top: `${u.startY}%` }}
                    animate={{ left: `${u.endX}%`, top: `${u.endY}%` }}
                    transition={{
                        duration: u.duration,
                        repeat: Infinity,
                        repeatType: 'reverse',
                        ease: 'linear',
                        delay: u.delay
                    }}
                >
                    {/* Ping effect */}
                    <div className={`absolute -inset-1.5 rounded-full animate-ping opacity-40 ${u.targetColor}`}></div>
                    
                    {/* Label */}
                    <div className={`absolute top-2 left-2 text-[8px] font-mono tracking-widest ${u.textColor}`}>
                        {u.type}-{u.id} {u.type === 'AIR' ? 'MEDEVAC' : 'SUPPLY'}
                    </div>
                </motion.div>
            ))}
        </div>
    );
};

const DataStreamsLayer = () => {
    const streams = useMemo(() => Array.from({ length: 20 }).map((_, i) => ({
        id: i,
        isHorizontal: Math.random() > 0.5,
        pos: `${Math.random() * 100}%`,
        delay: Math.random() * 5,
        duration: Math.random() * 2 + 1.5,
        direction: Math.random() > 0.5 ? 1 : -1,
        isAlert: Math.random() > 0.8
    })), []);

    return (
        <div className="absolute inset-0 z-10 pointer-events-none overflow-hidden opacity-60">
            {streams.map(s => {
                const colorBase = s.isAlert ? 'rose-500' : 'cyan-400';
                const shadow = s.isAlert ? 'rgba(244,63,94,0.8)' : 'rgba(34,211,238,0.8)';
                const className = `absolute ${s.isHorizontal ? 'h-[3px] w-[500px] bg-gradient-to-r' : 'w-[3px] h-[500px] bg-gradient-to-b'} from-transparent via-${colorBase} to-transparent`;

                return (
                    <motion.div
                        key={s.id}
                        className={className}
                        style={{
                            ...(s.isHorizontal ? { top: s.pos } : { left: s.pos }),
                            boxShadow: `0 0 20px ${shadow}`
                        }}
                        initial={s.isHorizontal 
                            ? { left: s.direction > 0 ? '-500px' : '100%' } 
                            : { top: s.direction > 0 ? '-500px' : '100%' }
                        }
                        animate={s.isHorizontal 
                            ? { left: s.direction > 0 ? '100%' : '-500px' } 
                            : { top: s.direction > 0 ? '100%' : '-500px' }
                        }
                        transition={{
                            duration: s.duration,
                            repeat: Infinity,
                            ease: "linear",
                            delay: s.delay
                        }}
                    >
                       <div className={`absolute ${s.isHorizontal ? (s.direction > 0 ? 'right-1/2' : 'left-1/2') : (s.direction > 0 ? 'bottom-1/2' : 'top-1/2')} w-[4px] h-[4px] bg-white rounded-full shadow-[0_0_15px_white]`}></div>
                    </motion.div>
                );
            })}
        </div>
    );
};

const GlobalRadarBackground = () => {
    return (
        <div className="absolute inset-0 z-0 overflow-hidden bg-[#050505] flex justify-center items-center pointer-events-none">
            {/* Concentric grid rings */}
            <div className="absolute inset-x-0 bottom-0 h-[80%] bg-gradient-to-t from-cyan-950/20 to-transparent z-0 blur-3xl"></div>
            
            <AgentNetworkCanvas />
            <RescueUnitsLayer />
            <DataStreamsLayer />

            <motion.div 
                animate={{ rotate: 360 }}
                transition={{ duration: 60, repeat: Infinity, ease: 'linear' }}
                className="absolute w-[800px] h-[800px] md:w-[1200px] md:h-[1200px] rounded-full border border-cyan-900/10 flex items-center justify-center opacity-60"
            >
                <div className="w-[80%] h-[80%] rounded-full border border-cyan-900/20 flex items-center justify-center">
                    <div className="w-[70%] h-[70%] rounded-full border border-cyan-900/30 flex items-center justify-center">
                        <div className="w-[50%] h-[50%] rounded-full border border-cyan-800/40 border-dashed"></div>
                    </div>
                </div>
                {/* Radar Sweep Effect */}
                <div className="absolute top-1/2 left-1/2 w-1/2 h-1 bg-gradient-to-r from-cyan-500/0 via-cyan-500/20 to-cyan-400/80 origin-left -translate-y-1/2 shadow-[0_0_20px_rgba(34,211,238,0.5)] blur-[1px]"></div>
            </motion.div>
            
            <RescueUnitsLayer />
            <DataStreamsLayer />

            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_transparent_30%,_#050505_100%)] z-20"></div>
            <div className="absolute inset-0 bg-[linear-gradient(rgba(34,211,238,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(34,211,238,0.03)_1px,transparent_1px)] bg-[size:40px_40px] z-20 [mask-image:radial-gradient(ellipse_at_center,black_40%,transparent_100%)]"></div>
        </div>
    );
};

export function LandingPage({ onLaunch }: LandingPageProps) {
    const { scrollYProgress } = useScroll();
    const heroOpacity = useTransform(scrollYProgress, [0, 0.2], [1, 0]);
    const heroY = useTransform(scrollYProgress, [0, 0.2], [0, -100]);

    return (
        <div className="min-h-screen bg-[#050505] text-zinc-300 font-sans selection:bg-cyan-900 selection:text-cyan-100 overflow-x-hidden">
            <GlobalRadarBackground />

            {/* --- HERO SECTION --- */}
            <motion.div 
                style={{ opacity: heroOpacity, y: heroY }}
                className="relative z-20 min-h-[95vh] flex flex-col items-center justify-center px-4 max-w-7xl mx-auto pt-20 pb-32"
            >
                {/* HUD Elements */}
                <div className="absolute top-24 left-10 hidden lg:block space-y-4 font-mono">
                    <div className="bg-black/40 border border-cyan-900/50 backdrop-blur-md p-3 rounded-lg shadow-[0_0_15px_rgba(8,145,178,0.2)]">
                        <div className="text-[10px] text-cyan-600 uppercase tracking-widest font-bold mb-1">Target Engine</div>
                        <div className="text-cyan-400 text-sm">Groq Llama-3 70B</div>
                    </div>
                     <div className="bg-black/40 border border-red-900/50 backdrop-blur-md p-3 rounded-lg shadow-[0_0_15px_rgba(220,38,38,0.1)]">
                        <div className="text-[10px] text-red-600 uppercase tracking-widest font-bold mb-1">Threat Level</div>
                        <div className="text-red-400 text-sm animate-pulse">Critical Vectors Active</div>
                    </div>
                </div>

                <div className="absolute top-32 right-10 hidden lg:block space-y-4 font-mono">
                    <div className="bg-black/40 border border-emerald-900/50 backdrop-blur-md p-3 rounded-lg text-right shadow-[0_0_15px_rgba(16,185,129,0.1)]">
                        <div className="text-[10px] text-emerald-600 uppercase tracking-widest font-bold mb-1">MAPPO Inference</div>
                        <div className="text-emerald-400 text-sm">&lt; 1ms Latency</div>
                    </div>
                    <div className="bg-black/40 border border-zinc-800/50 backdrop-blur-md p-3 rounded-lg text-right">
                        <div className="text-[10px] text-zinc-600 uppercase tracking-widest font-bold mb-1">Live Agents</div>
                        <div className="text-zinc-400 text-sm">Online (4-Stage)</div>
                    </div>
                </div>

                {/* Hero Content */}
                <div className="text-center w-full mt-12">
                    <motion.div
                        initial={{ opacity: 0, y: -20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.6 }}
                        className="inline-flex mb-8 px-4 py-1.5 rounded-full border border-cyan-800/50 bg-[#0b0c10]/80 shadow-[0_0_20px_rgba(8,145,178,0.2)] backdrop-blur-md items-center gap-2"
                    >
                        <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse"></div>
                        <span className="text-[10px] sm:text-xs font-bold text-zinc-300 uppercase tracking-[0.2em]">Disaster Command Core V3</span>
                    </motion.div>

                    <motion.h1 
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ duration: 0.8, delay: 0.1 }}
                        className="text-6xl sm:text-8xl md:text-[9rem] font-black mb-6 tracking-tighter leading-none"
                    >
                        <span className="text-transparent bg-clip-text bg-gradient-to-b from-white via-zinc-200 to-zinc-600 drop-shadow-[0_0_30px_rgba(255,255,255,0.1)]">DISASTER</span>
                        <br/>
                        <span className="text-transparent bg-clip-text bg-gradient-to-b from-cyan-400 to-blue-700 drop-shadow-[0_0_40px_rgba(34,211,238,0.3)] block -mt-4">MAN</span>
                    </motion.h1>

                    <motion.p 
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ duration: 0.6, delay: 0.3 }}
                        className="max-w-3xl mx-auto text-sm sm:text-base md:text-lg text-zinc-400 leading-relaxed mb-12 font-medium px-4"
                    >
                        Transform chaos into coordination. Powered by <span className="text-cyan-400 font-bold">Groq LLM Intelligence</span> and <span className="text-emerald-400 font-bold">zero-latency PyTorch heuristics</span>. 
                        Generate strategies from text, intercept live agent tactical telemetry, and orchestrate rescue maneuvers globally.
                    </motion.p>

                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.6, delay: 0.4 }}
                        className="flex flex-col sm:flex-row items-center justify-center gap-6"
                    >
                        <button 
                            onClick={onLaunch}
                            className="group relative px-10 py-5 bg-transparent border-2 border-cyan-500/50 hover:border-cyan-400 rounded-lg font-black text-cyan-400 tracking-[0.2em] uppercase overflow-hidden shadow-[0_0_30px_rgba(8,145,178,0.2)] hover:shadow-[0_0_50px_rgba(8,145,178,0.5)] transition-all duration-300"
                        >
                            <div className="absolute inset-0 bg-cyan-500/10 translate-y-full group-hover:translate-y-0 transition-transform duration-300 ease-out"></div>
                            <span className="relative flex items-center justify-center gap-3">
                                INITIATE SYSTEM <Globe2 className="w-5 h-5 group-hover:animate-spin" />
                            </span>
                        </button>
                    </motion.div>
                </div>
            </motion.div>

            {/* --- ABOUT SECTION --- */}
            <div className="relative z-20 bg-[#030303] border-t border-zinc-900 py-32">
                <div className="max-w-7xl mx-auto px-6">
                    <div className="text-center mb-20">
                         <h2 className="text-xs text-cyan-600 font-black tracking-[0.3em] uppercase mb-4">Mission Parameters</h2>
                         <h3 className="text-3xl md:text-5xl font-bold text-white tracking-tight">Intelligence under total collapse.</h3>
                         <p className="max-w-2xl mx-auto mt-6 text-zinc-400 text-base md:text-lg">
                             DisasterMan is an OpenEnv-compliant Multi-Agent Reinforcement Learning framework built specifically to solve non-linear logistical nightmares occurring in natural disasters.
                         </p>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 font-sans">
                        {[
                            {
                                icon: <ShieldAlert className="w-8 h-8 text-rose-500" />,
                                title: "Cascading Failures",
                                desc: "Real-world disasters escalate. A local flood turns into a bridge collapse, severing supply lines entirely. DisasterMan dynamically re-paths convoys mid-mission when parameters collapse."
                            },
                            {
                                icon: <Radio className="w-8 h-8 text-cyan-500" />,
                                title: "False SOS Vectors",
                                desc: "In chaos, panicked civilians broadcast false locations. The AI validates inputs, prioritizing heavy casualties and ignoring generic noise vectors."
                            },
                            {
                                icon: <Zap className="w-8 h-8 text-amber-500" />,
                                title: "Cost-Optimized Fallbacks",
                                desc: "Heavy inference running on Edge devices isn't realistic. The system automatically switches between Groq LLM intelligence and lightweight PyTorch Heuristics during blackout conditions."
                            }
                        ].map((feature, i) => (
                            <motion.div 
                                key={i}
                                initial={{ opacity: 0, y: 20 }}
                                whileInView={{ opacity: 1, y: 0 }}
                                viewport={{ once: true, margin: "-100px" }}
                                transition={{ delay: i * 0.2 }}
                                className="bg-[#0a0a0a] border border-zinc-800/50 p-8 rounded-2xl hover:border-zinc-700 hover:bg-[#0f0f0f] transition-colors"
                            >
                                <div className="p-4 bg-zinc-900/50 inline-block rounded-xl border border-zinc-800 mb-6 shadow-inner">
                                    {feature.icon}
                                </div>
                                <h4 className="text-xl font-bold text-white mb-3">{feature.title}</h4>
                                <p className="text-zinc-400 leading-relaxed text-sm">
                                    {feature.desc}
                                </p>
                            </motion.div>
                        ))}
                    </div>
                </div>
            </div>

            {/* --- ADVANCED OPERATIONS --- */}
            <div className="relative z-20 bg-[#080808] border-t border-zinc-900 py-32">
                <div className="max-w-7xl mx-auto px-6">
                    <div className="text-center mb-20">
                         <h2 className="text-xs text-rose-500 font-black tracking-[0.3em] uppercase mb-4">Core Modules</h2>
                         <h3 className="text-3xl md:text-5xl font-bold text-white tracking-tight">Advanced Operations Framework.</h3>
                    </div>

                    <div className="flex flex-col gap-16 lg:gap-24">
                        {/* Module 1 */}
                        <div className="flex flex-col lg:flex-row items-center gap-8 lg:gap-16">
                            <div className="lg:w-1/2 order-2 lg:order-1">
                                <h4 className="text-2xl md:text-3xl font-bold text-white mb-4">Groq-Powered Strategy Analyzer</h4>
                                <p className="text-zinc-400 leading-relaxed mb-6 text-sm md:text-base">
                                    A massive leap in disaster preparedness. Instead of parsing raw telemetry, Ground Commanders simply describe scenarios in plain English (e.g. "Category 5 hurricane hitting Miami"). The integrated Groq LLM parses the narrative, queries real-world geolocations, and generates an official, print-ready tactical strategy in seconds.
                                </p>
                                <ul className="space-y-3 text-xs md:text-sm text-zinc-500 font-mono">
                                    <li className="flex gap-3 items-center"><Sparkles className="w-4 h-4 text-cyan-500 shrink-0" /> Export to clean PDF for field deployment</li>
                                    <li className="flex gap-3 items-center"><Sparkles className="w-4 h-4 text-cyan-500 shrink-0" /> Exact coordinate Geolocation via browser</li>
                                    <li className="flex gap-3 items-center"><Sparkles className="w-4 h-4 text-cyan-500 shrink-0" /> Direct one-click email escalation to NDRF</li>
                                </ul>
                            </div>
                            <div className="lg:w-1/2 order-1 lg:order-2 w-full h-[300px] bg-[#0a0a0a] border border-cyan-900/30 rounded-3xl flex items-center justify-center shadow-[inset_0_0_50px_rgba(8,145,178,0.1)] relative overflow-hidden">
                                <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_transparent_30%,_#0a0a0a_100%)] z-10"></div>
                                <div className="absolute inset-0 bg-[linear-gradient(rgba(34,211,238,0.1)_1px,transparent_1px),linear-gradient(90deg,rgba(34,211,238,0.1)_1px,transparent_1px)] bg-[size:20px_20px] z-0"></div>
                                <Database className="w-20 h-20 text-cyan-500/80 z-20 drop-shadow-[0_0_15px_rgba(8,145,178,0.8)]" />
                            </div>
                        </div>

                        {/* Module 2 */}
                        <div className="flex flex-col lg:flex-row items-center gap-8 lg:gap-16">
                            <div className="lg:w-1/2 w-full h-[300px] bg-[#0a0a0a] border border-rose-900/30 rounded-3xl flex items-center justify-center shadow-[inset_0_0_50px_rgba(225,29,72,0.1)] relative overflow-hidden">
                                <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_transparent_30%,_#0a0a0a_100%)] z-10"></div>
                                <div className="absolute inset-0 bg-[linear-gradient(rgba(244,63,94,0.1)_1px,transparent_1px),linear-gradient(90deg,rgba(244,63,94,0.1)_1px,transparent_1px)] bg-[size:20px_20px] z-0"></div>
                                <Radio className="w-20 h-20 text-rose-500/80 z-20 drop-shadow-[0_0_15px_rgba(225,29,72,0.8)]" />
                            </div>
                            <div className="lg:w-1/2">
                                <h4 className="text-2xl md:text-3xl font-bold text-white mb-4">Agent-to-Agent Comms Intercept</h4>
                                <p className="text-zinc-400 leading-relaxed mb-6 text-sm md:text-base">
                                    We solved the "Black Box AI" problem. As the mathematical MAPPO models route helicopters and supplies internally, our Comms Intercept decrypts their matrix decisions and translates them into visceral, human-readable radio chatter. Watch the Airlift Commander argue with Ground Logistics in real time.
                                </p>
                                <ul className="space-y-3 text-xs md:text-sm text-zinc-500 font-mono">
                                    <li className="flex gap-3 items-center"><Radio className="w-4 h-4 text-rose-500 shrink-0" /> Real-time neural action decoding</li>
                                    <li className="flex gap-3 items-center"><Radio className="w-4 h-4 text-rose-500 shrink-0" /> Step-by-step map playback synchronization</li>
                                    <li className="flex gap-3 items-center"><Radio className="w-4 h-4 text-rose-500 shrink-0" /> Deep explainability for absolute AI Trust</li>
                                </ul>
                            </div>
                        </div>

                        {/* Module 3 */}
                        <div className="flex flex-col lg:flex-row items-center gap-8 lg:gap-16">
                            <div className="lg:w-1/2 order-2 lg:order-1">
                                <h4 className="text-2xl md:text-3xl font-bold text-white mb-4">Global Command Center & Telemetry</h4>
                                <p className="text-zinc-400 leading-relaxed mb-6 text-sm md:text-base">
                                    Monitor the entire ecosystem. The Command Center provides high-altitude heatmaps tracking API action frequencies, predictive inter-zone conflict matrices, and real-time backend agent tracking via our Linux-style System Vitals terminal.
                                </p>
                                <ul className="space-y-3 text-xs md:text-sm text-zinc-500 font-mono">
                                    <li className="flex gap-3 items-center"><Terminal className="w-4 h-4 text-emerald-500 shrink-0" /> Live scrolling server logs view</li>
                                    <li className="flex gap-3 items-center"><Terminal className="w-4 h-4 text-emerald-500 shrink-0" /> Network & VRAM hardware monitoring</li>
                                    <li className="flex gap-3 items-center"><Terminal className="w-4 h-4 text-emerald-500 shrink-0" /> Predictive Conflict Escalation Heatmaps</li>
                                </ul>
                            </div>
                            <div className="lg:w-1/2 order-1 lg:order-2 w-full h-[300px] bg-[#0a0a0a] border border-emerald-900/30 rounded-3xl flex items-center justify-center shadow-[inset_0_0_50px_rgba(16,185,129,0.1)] relative overflow-hidden">
                                <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_transparent_30%,_#0a0a0a_100%)] z-10"></div>
                                <div className="absolute inset-0 bg-[linear-gradient(rgba(16,185,129,0.1)_1px,transparent_1px),linear-gradient(90deg,rgba(16,185,129,0.1)_1px,transparent_1px)] bg-[size:20px_20px] z-0"></div>
                                <Terminal className="w-20 h-20 text-emerald-500/80 z-20 drop-shadow-[0_0_15px_rgba(16,185,129,0.8)]" />
                            </div>
                        </div>

                    </div>
                </div>
            </div>

            {/* --- TECHNOLOGY STACK --- */}
            <div className="relative z-20 bg-[#050505] py-32 border-t border-zinc-900">
                <div className="max-w-7xl mx-auto px-6">
                    <div className="text-center mb-20">
                         <h2 className="text-xs text-purple-500 font-black tracking-[0.3em] uppercase mb-4">Architecture</h2>
                         <h3 className="text-3xl md:text-5xl font-bold text-white tracking-tight">The Neural Stack.</h3>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
                        {[
                            {
                                icon: <Sparkles className="w-6 h-6 text-indigo-400" />,
                                name: "Groq API",
                                category: "LLM INFERENCE",
                                desc: "Powering the Strategy Generator with blazingly fast Llama-3 tactical intelligence parsing."
                            },
                            {
                                icon: <Cpu className="w-6 h-6 text-emerald-400" />,
                                name: "PyTorch MAPPO",
                                category: "REINFORCEMENT LEARNING",
                                desc: "Hard-coded neural networks mathematically evaluating Zone severity in < 1ms."
                            },
                            {
                                icon: <Terminal className="w-6 h-6 text-green-500" />,
                                name: "FastAPI / Python",
                                category: "BACKEND ENGINE",
                                desc: "High-throughput asynchronous Python architecture handling massive multi-agent telemetry streams."
                            },
                            {
                                icon: <Component className="w-6 h-6 text-cyan-400" />,
                                name: "React + Framer",
                                category: "FRONTEND VISUALS",
                                desc: "Cinematic, hardware-accelerated dashboard mapping mathematical models into human-readable data."
                            }
                        ].map((tech, i) => (
                            <div key={i} className="group relative bg-[#0b0c10] border border-zinc-800 rounded-2xl overflow-hidden hover:border-cyan-900/50 transition-colors duration-500">
                                <div className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-[#111318] to-transparent pointer-events-none group-hover:from-cyan-950/20 transition-colors duration-500"></div>
                                <div className="p-8 relative z-10">
                                    <div className="flex justify-between items-start mb-8">
                                        <div className="text-[10px] text-zinc-500 font-bold uppercase tracking-widest">{tech.category}</div>
                                        {tech.icon}
                                    </div>
                                    <h4 className="text-xl font-bold text-white mb-2">{tech.name}</h4>
                                    <p className="text-xs text-zinc-500 leading-relaxed">{tech.desc}</p>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            {/* Footer */}
            <footer className="bg-black py-8 border-t border-zinc-900 text-center relative z-20">
                <p className="text-[10px] font-mono text-zinc-600 uppercase tracking-[0.2em] mb-2">DisasterMan Core // Open Source Intelligence</p>
                <p className="text-[10px] text-zinc-700">Powered by the Voiceflow integration</p>
            </footer>
        </div>
    );
}
