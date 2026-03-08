/**
 * Live swarm topology visualization.
 *
 * Renders an SVG network graph with the swarm hub at center and connected
 * team nodes arranged radially. An MCP server node is shown as an inner
 * satellite. All nodes are clickable for navigation. Status is indicated
 * by color; edges pulse to convey liveness. Fully responsive via viewBox.
 */

import { useState, useMemo, useCallback, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import type { SwarmNode } from "@/hooks/use-swarm-nodes";

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const HUB_R = 40;
const NODE_R = 28;
const INNER_R = 22;

const STATUS_COLORS = {
    connected: { fill: "#3b82f6", glow: "#3b82f6", ring: "#2563eb" },
    stale: { fill: "#eab308", glow: "#eab308", ring: "#ca8a04" },
    disconnected: { fill: "#6b7280", glow: "#6b7280", ring: "#4b5563" },
} as const;

const HUB_COLORS = {
    connected: { fill: "#2a9d8f", glow: "#2a9d8f", ring: "#1a6b62" },
    disconnected: { fill: "#6b7280", glow: "#6b7280", ring: "#4b5563" },
} as const;

const MCP_COLORS = {
    online: { fill: "#8b5cf6", glow: "#8b5cf6", ring: "#7c3aed" },
    offline: { fill: "#6b7280", glow: "#6b7280", ring: "#4b5563" },
} as const;

type StatusKey = keyof typeof STATUS_COLORS;
const statusOf = (s: string): StatusKey =>
    s in STATUS_COLORS ? (s as StatusKey) : "disconnected";

/* MCP tool names exposed by the swarm server */
const MCP_TOOLS = ["swarm_search", "swarm_nodes", "swarm_status", "swarm_fetch"];

/* Search categories available across the swarm */
const SEARCH_CATEGORIES = ["Memories", "Plans", "Sessions"];

const SEARCH_COLORS = {
    online: { fill: "#f59e0b", glow: "#f59e0b", ring: "#d97706" },
    offline: { fill: "#6b7280", glow: "#6b7280", ring: "#4b5563" },
} as const;

/* ------------------------------------------------------------------ */
/*  Hub icon                                                           */
/* ------------------------------------------------------------------ */

function HubIcon({ size }: { size: number }) {
    const half = size / 2;
    const scale = size / 100;
    return (
        <g transform={`translate(${-half},${-half}) scale(${scale})`}>
            <polygon
                points="50,8 88,30 88,70 50,92 12,70 12,30"
                fill="currentColor"
                className="text-primary"
                opacity={0.25}
            />
            <polygon
                points="50,24 74,38 74,62 50,76 26,62 26,38"
                fill="currentColor"
                className="text-background"
                opacity={0.6}
            />
            <circle cx={50} cy={50} r={7} fill="currentColor" className="text-primary" />
            <line x1={50} y1={43} x2={50} y2={24} stroke="currentColor" className="text-primary" strokeWidth={2} />
            <line x1={56} y1={46} x2={70} y2={38} stroke="currentColor" className="text-primary" strokeWidth={2} />
            <line x1={56} y1={54} x2={70} y2={62} stroke="currentColor" className="text-primary" strokeWidth={2} />
            <line x1={50} y1={57} x2={50} y2={76} stroke="currentColor" className="text-primary" strokeWidth={2} />
            <line x1={44} y1={54} x2={30} y2={62} stroke="currentColor" className="text-primary" strokeWidth={2} />
            <line x1={44} y1={46} x2={30} y2={38} stroke="currentColor" className="text-primary" strokeWidth={2} />
        </g>
    );
}

/* ------------------------------------------------------------------ */
/*  MCP icon — plug/socket shape                                       */
/* ------------------------------------------------------------------ */

function McpIcon({ color }: { color: string }) {
    return (
        <g>
            <rect x={-4} y={-6} width={8} height={12} rx={1.5} fill="none" stroke={color} strokeWidth={1.5} />
            <line x1={-1.5} y1={-3} x2={-1.5} y2={1} stroke={color} strokeWidth={1.5} strokeLinecap="round" />
            <line x1={1.5} y1={-3} x2={1.5} y2={1} stroke={color} strokeWidth={1.5} strokeLinecap="round" />
            <line x1={0} y1={6} x2={0} y2={9} stroke={color} strokeWidth={1.5} strokeLinecap="round" />
        </g>
    );
}

/* ------------------------------------------------------------------ */
/*  Geometry helpers                                                    */
/* ------------------------------------------------------------------ */

interface Point { x: number; y: number }

function radialPositions(n: number, radius: number): Point[] {
    if (n === 0) return [];
    const offset = -Math.PI / 2;
    return Array.from({ length: n }, (_, i) => {
        const angle = offset + (2 * Math.PI * i) / n;
        return { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius };
    });
}

function computeLayout(nodeCount: number) {
    const orbit = Math.max(160, Math.min(220, 140 + nodeCount * 14));
    const extent = orbit + NODE_R + 50;
    return { orbit, extent };
}

/* ------------------------------------------------------------------ */
/*  Sub-components                                                     */
/* ------------------------------------------------------------------ */

interface EdgeProps {
    x1: number;
    y1: number;
    x2: number;
    y2: number;
    active: boolean;
    color: { glow: string };
    index: number;
}

function Edge({ x1, y1, x2, y2, active, color, index }: EdgeProps) {
    return (
        <line
            x1={x1} y1={y1} x2={x2} y2={y2}
            stroke={color.glow}
            strokeWidth={active ? 2 : 1.5}
            strokeOpacity={active ? 0.35 : 0.15}
            strokeDasharray={active ? undefined : "6 6"}
        >
            {active && (
                <animate
                    attributeName="stroke-opacity"
                    values="0.15;0.55;0.15"
                    dur={`${2.5 + index * 0.3}s`}
                    repeatCount="indefinite"
                />
            )}
        </line>
    );
}

interface SatelliteProps {
    node: SwarmNode;
    pos: Point;
    onHover: (node: SwarmNode | null, pos: Point | null) => void;
    onClick?: () => void;
}

function Satellite({ node, pos, onHover, onClick }: SatelliteProps) {
    const status = statusOf(node.status);
    const color = STATUS_COLORS[status];

    return (
        <g
            transform={`translate(${pos.x},${pos.y})`}
            className="cursor-pointer"
            onMouseEnter={() => onHover(node, pos)}
            onMouseLeave={() => onHover(null, null)}
            onClick={onClick}
        >
            <circle r={NODE_R + 6} fill={color.glow} opacity={0.08}>
                {status === "connected" && (
                    <animate
                        attributeName="r"
                        values={`${NODE_R + 3};${NODE_R + 9};${NODE_R + 3}`}
                        dur="3s"
                        repeatCount="indefinite"
                    />
                )}
            </circle>
            <circle r={NODE_R} fill="none" stroke={color.ring} strokeWidth={2} opacity={0.5} />
            <circle r={NODE_R - 4} fill={color.fill} opacity={0.15} />
            <circle r={4.5} fill={color.fill} opacity={0.9} />

            <text
                y={NODE_R + 18}
                textAnchor="middle"
                className="fill-foreground font-medium"
                style={{ fontFamily: "inherit", fontSize: 13 }}
            >
                {node.project_slug.length > 18 ? `${node.project_slug.slice(0, 16)}\u2026` : node.project_slug}
            </text>
            <text
                y={NODE_R + 33}
                textAnchor="middle"
                className="fill-muted-foreground"
                style={{ fontFamily: "inherit", fontSize: 10 }}
            >
                {node.status}
            </text>
        </g>
    );
}

/* ------------------------------------------------------------------ */
/*  MCP satellite (inner node, smaller)                                */
/* ------------------------------------------------------------------ */

interface McpNodeProps {
    pos: Point;
    online: boolean;
    mcpEndpoint: string | null;
    onHover: (hovered: boolean) => void;
    onClick?: () => void;
}

function McpNode({ pos, online, onHover, onClick }: McpNodeProps) {
    const color = online ? MCP_COLORS.online : MCP_COLORS.offline;
    return (
        <g
            transform={`translate(${pos.x},${pos.y})`}
            className="cursor-pointer"
            onMouseEnter={() => onHover(true)}
            onMouseLeave={() => onHover(false)}
            onClick={onClick}
        >
            <circle r={INNER_R + 4} fill={color.glow} opacity={0.06}>
                {online && (
                    <animate
                        attributeName="r"
                        values={`${INNER_R + 2};${INNER_R + 7};${INNER_R + 2}`}
                        dur="3s"
                        repeatCount="indefinite"
                    />
                )}
            </circle>
            <circle r={INNER_R} fill="none" stroke={color.ring} strokeWidth={1.5} opacity={0.5} />
            <circle r={INNER_R - 3} fill={color.fill} opacity={0.12} />
            <McpIcon color={color.fill} />
            <text
                y={INNER_R + 14}
                textAnchor="middle"
                className="fill-foreground font-medium"
                style={{ fontFamily: "inherit", fontSize: 11 }}
            >
                MCP Server
            </text>
            <text
                y={INNER_R + 26}
                textAnchor="middle"
                className="fill-muted-foreground"
                style={{ fontFamily: "inherit", fontSize: 9 }}
            >
                {online ? `${MCP_TOOLS.length} tools` : "Offline"}
            </text>
        </g>
    );
}

/* ------------------------------------------------------------------ */
/*  Search satellite (inner node, smaller)                              */
/* ------------------------------------------------------------------ */

function SearchIcon({ color }: { color: string }) {
    return (
        <g>
            <circle cx={-1} cy={-1} r={5} fill="none" stroke={color} strokeWidth={1.5} />
            <line x1={2.5} y1={2.5} x2={6} y2={6} stroke={color} strokeWidth={1.5} strokeLinecap="round" />
        </g>
    );
}

interface SearchNodeProps {
    pos: Point;
    online: boolean;
    onHover: (hovered: boolean) => void;
    onClick?: () => void;
}

function SearchNode({ pos, online, onHover, onClick }: SearchNodeProps) {
    const color = online ? SEARCH_COLORS.online : SEARCH_COLORS.offline;
    return (
        <g
            transform={`translate(${pos.x},${pos.y})`}
            className="cursor-pointer"
            onMouseEnter={() => onHover(true)}
            onMouseLeave={() => onHover(false)}
            onClick={onClick}
        >
            <circle r={INNER_R + 4} fill={color.glow} opacity={0.06}>
                {online && (
                    <animate
                        attributeName="r"
                        values={`${INNER_R + 2};${INNER_R + 7};${INNER_R + 2}`}
                        dur="3s"
                        repeatCount="indefinite"
                    />
                )}
            </circle>
            <circle r={INNER_R} fill="none" stroke={color.ring} strokeWidth={1.5} opacity={0.5} />
            <circle r={INNER_R - 3} fill={color.fill} opacity={0.12} />
            <SearchIcon color={color.fill} />
            <text
                y={INNER_R + 14}
                textAnchor="middle"
                className="fill-foreground font-medium"
                style={{ fontFamily: "inherit", fontSize: 11 }}
            >
                Search
            </text>
            <text
                y={INNER_R + 26}
                textAnchor="middle"
                className="fill-muted-foreground"
                style={{ fontFamily: "inherit", fontSize: 9 }}
            >
                {online ? "Cross-project" : "Offline"}
            </text>
        </g>
    );
}

/* ------------------------------------------------------------------ */
/*  Tooltips                                                           */
/* ------------------------------------------------------------------ */

interface TeamTooltipProps {
    node: SwarmNode;
    pos: Point;
    extent: number;
}

function TeamTooltip({ node, pos, extent }: TeamTooltipProps) {
    const status = statusOf(node.status);
    const color = STATUS_COLORS[status];

    const shortVersion = node.oak_version
        ? node.oak_version.replace(/\.dev\d+.*$/, "").replace(/\+.*$/, "")
        : "";

    const line1 = node.project_slug;
    const detailParts = [node.status];
    if (shortVersion) detailParts.push(`v${shortVersion}`);
    if (node.node_count != null) detailParts.push(`${node.node_count} node${node.node_count !== 1 ? "s" : ""}`);
    const line2 = detailParts.join(" \u00b7 ");

    const maxLen = Math.max(line1.length, line2.length);
    const tooltipW = Math.max(150, Math.min(360, maxLen * 6.5 + 40));
    const tooltipH = 46;
    const tx = Math.max(-extent + tooltipW / 2 + 8, Math.min(extent - tooltipW / 2 - 8, pos.x));
    const aboveY = pos.y - NODE_R - 50;
    const belowY = pos.y + NODE_R + 45;
    const ty = aboveY - tooltipH / 2 < -extent ? belowY : aboveY;

    return (
        <g transform={`translate(${tx},${ty})`} pointerEvents="none">
            <rect x={-tooltipW / 2} y={-tooltipH / 2} width={tooltipW} height={tooltipH} rx={6}
                className="fill-popover stroke-border" strokeWidth={1} />
            <text y={-6} textAnchor="middle" className="fill-foreground font-semibold"
                style={{ fontFamily: "inherit", fontSize: 11 }}>
                {line1}
            </text>
            <g transform="translate(0, 10)">
                <circle cx={-tooltipW / 2 + 12} cy={0} r={3} fill={color.fill} />
                <text x={-tooltipW / 2 + 20} y={3} className="fill-muted-foreground"
                    style={{ fontFamily: "inherit", fontSize: 9 }}>
                    {line2}
                </text>
            </g>
        </g>
    );
}

interface HubTooltipProps {
    pos: Point;
    extent: number;
    workerUrl: string | null;
    customDomain: string | null;
    deployed: boolean;
}

function HubTooltip({ pos, extent, workerUrl, customDomain, deployed }: HubTooltipProps) {
    const lines: string[] = [];
    if (deployed) lines.push("Deployed");
    else lines.push("Not deployed");
    if (customDomain) lines.push(customDomain);
    else if (workerUrl) {
        try { lines.push(new URL(workerUrl).hostname); } catch { lines.push(workerUrl); }
    }

    // Size tooltip to fit content
    const maxLineLen = Math.max(...lines.map(l => l.length));
    const tooltipW = Math.max(170, Math.min(360, maxLineLen * 6.5 + 30));
    const tooltipH = 18 + lines.length * 14;
    const tx = Math.max(-extent + tooltipW / 2 + 8, Math.min(extent - tooltipW / 2 - 8, pos.x));
    const ty = pos.y - HUB_R - 40;

    return (
        <g transform={`translate(${tx},${ty})`} pointerEvents="none">
            <rect x={-tooltipW / 2} y={-tooltipH / 2} width={tooltipW} height={tooltipH} rx={6}
                className="fill-popover stroke-border" strokeWidth={1} />
            {lines.map((line, i) => (
                <text
                    key={i}
                    y={-tooltipH / 2 + 14 + i * 14}
                    textAnchor="middle"
                    className={i === 0 ? "fill-foreground font-semibold" : "fill-muted-foreground"}
                    style={{ fontFamily: "inherit", fontSize: i === 0 ? 11 : 9 }}
                >
                    {line}
                </text>
            ))}
        </g>
    );
}

interface McpTooltipProps {
    pos: Point;
    extent: number;
    mcpEndpoint: string | null;
}

function McpTooltip({ pos, extent, mcpEndpoint }: McpTooltipProps) {
    // Measure width based on longest content line
    const endpointLen = mcpEndpoint ? mcpEndpoint.length * 5.5 : 0;
    const toolLen = Math.max(...MCP_TOOLS.map(t => t.length)) * 7;
    const tooltipW = Math.max(180, Math.min(360, Math.max(toolLen, endpointLen) + 40));
    const tooltipH = 18 + MCP_TOOLS.length * 13 + (mcpEndpoint ? 16 : 0);
    const tx = Math.max(-extent + tooltipW / 2 + 8, Math.min(extent - tooltipW / 2 - 8, pos.x));
    const aboveY = pos.y - INNER_R - 40;
    const belowY = pos.y + INNER_R + 35;
    const ty = aboveY - tooltipH / 2 < -extent ? belowY : aboveY;

    return (
        <g transform={`translate(${tx},${ty})`} pointerEvents="none">
            <rect x={-tooltipW / 2} y={-tooltipH / 2} width={tooltipW} height={tooltipH} rx={6}
                className="fill-popover stroke-border" strokeWidth={1} />
            <text y={-tooltipH / 2 + 14} textAnchor="middle"
                className="fill-foreground font-semibold"
                style={{ fontFamily: "inherit", fontSize: 11 }}>
                MCP Tools
            </text>
            {MCP_TOOLS.map((tool, i) => (
                <text key={tool}
                    y={-tooltipH / 2 + 28 + i * 13}
                    textAnchor="middle"
                    className="fill-muted-foreground"
                    style={{ fontFamily: "inherit", fontSize: 9 }}>
                    {tool}
                </text>
            ))}
            {mcpEndpoint && (
                <text
                    y={tooltipH / 2 - 6}
                    textAnchor="middle"
                    className="fill-muted-foreground"
                    style={{ fontFamily: "inherit", fontSize: 8, fontStyle: "italic" }}>
                    {mcpEndpoint}
                </text>
            )}
        </g>
    );
}

interface SearchTooltipProps {
    pos: Point;
    extent: number;
    nodeCount: number;
}

function SearchTooltip({ pos, extent, nodeCount }: SearchTooltipProps) {
    const lines = SEARCH_CATEGORIES;
    const tooltipW = 180;
    const tooltipH = 18 + lines.length * 13 + 14;
    const tx = Math.max(-extent + tooltipW / 2 + 8, Math.min(extent - tooltipW / 2 - 8, pos.x));
    const aboveY = pos.y - INNER_R - 40;
    const belowY = pos.y + INNER_R + 35;
    const ty = aboveY - tooltipH / 2 < -extent ? belowY : aboveY;

    return (
        <g transform={`translate(${tx},${ty})`} pointerEvents="none">
            <rect x={-tooltipW / 2} y={-tooltipH / 2} width={tooltipW} height={tooltipH} rx={6}
                className="fill-popover stroke-border" strokeWidth={1} />
            <text y={-tooltipH / 2 + 14} textAnchor="middle"
                className="fill-foreground font-semibold"
                style={{ fontFamily: "inherit", fontSize: 11 }}>
                Cross-Project Search
            </text>
            {lines.map((cat, i) => (
                <text key={cat}
                    y={-tooltipH / 2 + 28 + i * 13}
                    textAnchor="middle"
                    className="fill-muted-foreground"
                    style={{ fontFamily: "inherit", fontSize: 9 }}>
                    {cat}
                </text>
            ))}
            <text
                y={tooltipH / 2 - 6}
                textAnchor="middle"
                className="fill-muted-foreground"
                style={{ fontFamily: "inherit", fontSize: 8, fontStyle: "italic" }}>
                {nodeCount} project{nodeCount !== 1 ? "s" : ""} indexed
            </text>
        </g>
    );
}

/* ------------------------------------------------------------------ */
/*  Main component                                                     */
/* ------------------------------------------------------------------ */

interface SwarmTopologyProps {
    swarmId: string;
    connected: boolean;
    nodes: SwarmNode[];
    workerUrl?: string | null;
    customDomain?: string | null;
    mcpEndpoint?: string | null;
}

type HoverState =
    | { type: "team"; node: SwarmNode; pos: Point }
    | { type: "hub"; pos: Point }
    | { type: "mcp"; pos: Point }
    | { type: "search"; pos: Point }
    | null;

export function SwarmTopology({
    swarmId,
    connected,
    nodes,
    workerUrl,
    customDomain,
    mcpEndpoint,
}: SwarmTopologyProps) {
    const navigate = useNavigate();
    const [hovered, setHovered] = useState<HoverState>(null);

    const handleTeamHover = useCallback(
        (node: SwarmNode | null, pos: Point | null) => {
            setHovered(node && pos ? { type: "team", node, pos } : null);
        },
        [],
    );

    const { orbit, extent } = useMemo(
        () => computeLayout(Math.max(nodes.length, 1)),
        [nodes.length],
    );

    const positions = useMemo(
        () => radialPositions(nodes.length, orbit),
        [nodes.length, orbit],
    );

    // Inner satellite positions — spread on opposite sides of the hub
    const mcpPos: Point = useMemo(() => {
        const innerOrbit = orbit * 0.6;
        const angle = nodes.length > 0 ? -Math.PI / 4 : -Math.PI / 6;
        return { x: Math.cos(angle) * innerOrbit, y: Math.sin(angle) * innerOrbit };
    }, [orbit, nodes.length]);

    const searchPos: Point = useMemo(() => {
        const innerOrbit = orbit * 0.6;
        const angle = nodes.length > 0 ? (-3 * Math.PI) / 4 : (5 * Math.PI) / 6;
        return { x: Math.cos(angle) * innerOrbit, y: Math.sin(angle) * innerOrbit };
    }, [orbit, nodes.length]);

    const hubKey = connected ? "connected" : "disconnected";
    const hubColor = HUB_COLORS[hubKey];

    /* Orbit ring rotation */
    const rotationRef = useRef(0);
    const rafRef = useRef<number>(undefined);
    const orbitRingRef = useRef<SVGCircleElement>(null);

    useEffect(() => {
        if (nodes.length === 0) return;
        const tick = () => {
            rotationRef.current = (rotationRef.current + 0.15) % 360;
            if (orbitRingRef.current) {
                orbitRingRef.current.setAttribute("stroke-dashoffset", String(rotationRef.current));
            }
            rafRef.current = requestAnimationFrame(tick);
        };
        rafRef.current = requestAnimationFrame(tick);
        return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
    }, [nodes.length]);

    const deployed = !!workerUrl;

    return (
        <div className="rounded-lg border bg-card text-card-foreground shadow-sm">
            <div className="p-4 pb-2">
                <h3 className="text-sm font-medium tracking-tight">Swarm Topology</h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                    {nodes.length === 0
                        ? "No nodes connected"
                        : `${nodes.length} node${nodes.length !== 1 ? "s" : ""} connected`}
                </p>
            </div>

            <div className="px-4 pb-4">
                {nodes.length === 0 && !connected ? (
                    <EmptyState />
                ) : (
                    <svg
                        viewBox={`${-extent} ${-extent} ${extent * 2} ${extent * 2}`}
                        className="w-full"
                        style={{ minHeight: 360 }}
                    >
                        <defs>
                            <filter id="hub-glow" x="-50%" y="-50%" width="200%" height="200%">
                                <feGaussianBlur stdDeviation="6" result="blur" />
                                <feMerge>
                                    <feMergeNode in="blur" />
                                    <feMergeNode in="SourceGraphic" />
                                </feMerge>
                            </filter>
                        </defs>

                        {/* Orbit ring */}
                        {nodes.length > 0 && (
                            <circle
                                ref={orbitRingRef}
                                r={orbit}
                                fill="none"
                                stroke="currentColor"
                                className="text-border"
                                strokeWidth={1}
                                strokeDasharray="4 8"
                                opacity={0.4}
                            />
                        )}

                        {/* Edges: hub → teams */}
                        {nodes.map((node, i) => (
                            <Edge
                                key={node.team_id || node.project_slug}
                                x1={0} y1={0}
                                x2={positions[i].x} y2={positions[i].y}
                                active={statusOf(node.status) === "connected"}
                                color={STATUS_COLORS[statusOf(node.status)]}
                                index={i}
                            />
                        ))}

                        {/* Edge: hub → MCP */}
                        <Edge
                            x1={0} y1={0}
                            x2={mcpPos.x} y2={mcpPos.y}
                            active={connected}
                            color={connected ? MCP_COLORS.online : MCP_COLORS.offline}
                            index={nodes.length}
                        />

                        {/* Edge: hub → Search */}
                        <Edge
                            x1={0} y1={0}
                            x2={searchPos.x} y2={searchPos.y}
                            active={connected}
                            color={connected ? SEARCH_COLORS.online : SEARCH_COLORS.offline}
                            index={nodes.length + 1}
                        />

                        {/* Team satellite nodes */}
                        {nodes.map((node, i) => (
                            <Satellite
                                key={node.team_id || node.project_slug}
                                node={node}
                                pos={positions[i]}
                                onHover={handleTeamHover}
                                onClick={() => navigate("/nodes")}
                            />
                        ))}

                        {/* MCP node */}
                        <McpNode
                            pos={mcpPos}
                            online={connected}
                            mcpEndpoint={mcpEndpoint ?? null}
                            onHover={(h) => setHovered(h ? { type: "mcp", pos: mcpPos } : null)}
                            onClick={() => navigate("/connect")}
                        />

                        {/* Search node */}
                        <SearchNode
                            pos={searchPos}
                            online={connected}
                            onHover={(h) => setHovered(h ? { type: "search", pos: searchPos } : null)}
                            onClick={() => navigate("/search")}
                        />

                        {/* Hub node (on top, clickable) */}
                        <g
                            filter="url(#hub-glow)"
                            className="cursor-pointer"
                            onMouseEnter={() => setHovered({ type: "hub", pos: { x: 0, y: 0 } })}
                            onMouseLeave={() => setHovered(null)}
                            onClick={() => navigate("/deploy")}
                        >
                            <circle r={HUB_R + 12} fill={hubColor.glow} opacity={0.06}>
                                {connected && (
                                    <animate
                                        attributeName="opacity"
                                        values="0.04;0.14;0.04"
                                        dur="2.5s"
                                        repeatCount="indefinite"
                                    />
                                )}
                            </circle>
                            <circle r={HUB_R} fill="none" stroke={hubColor.ring} strokeWidth={2.5} opacity={0.6} />
                            <circle r={HUB_R - 4} fill={hubColor.fill} opacity={0.1} />
                            <HubIcon size={HUB_R * 1.4} />
                            <text
                                y={HUB_R + 20}
                                textAnchor="middle"
                                className="fill-foreground font-semibold"
                                style={{ fontFamily: "inherit", fontSize: 14 }}
                            >
                                {swarmId.length > 20 ? `${swarmId.slice(0, 18)}\u2026` : swarmId || "Hub"}
                            </text>
                        </g>

                        {/* Tooltips */}
                        {hovered?.type === "team" && (
                            <TeamTooltip node={hovered.node} pos={hovered.pos} extent={extent} />
                        )}
                        {hovered?.type === "hub" && (
                            <HubTooltip
                                pos={hovered.pos}
                                extent={extent}
                                workerUrl={workerUrl ?? null}
                                customDomain={customDomain ?? null}
                                deployed={deployed}
                            />
                        )}
                        {hovered?.type === "mcp" && (
                            <McpTooltip pos={hovered.pos} extent={extent} mcpEndpoint={mcpEndpoint ?? null} />
                        )}
                        {hovered?.type === "search" && (
                            <SearchTooltip pos={hovered.pos} extent={extent} nodeCount={nodes.length} />
                        )}
                    </svg>
                )}
            </div>
        </div>
    );
}

/* ------------------------------------------------------------------ */
/*  Empty state                                                        */
/* ------------------------------------------------------------------ */

function EmptyState() {
    return (
        <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="relative mb-5">
                <svg width={140} height={140} viewBox="-70 -70 140 140">
                    <circle
                        r={50} fill="none" stroke="currentColor" className="text-border"
                        strokeWidth={1} strokeDasharray="3 6" opacity={0.4}
                    />
                    <circle r={18} fill="currentColor" className="text-muted-foreground" opacity={0.06} />
                    <g opacity={0.4}><HubIcon size={28} /></g>
                </svg>
            </div>
            <p className="text-sm text-muted-foreground">No teams connected yet</p>
            <p className="text-xs text-muted-foreground mt-1">
                Share the invite credentials to connect teams to this swarm
            </p>
        </div>
    );
}
