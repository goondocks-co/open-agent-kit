/**
 * Live system topology visualization for the team daemon dashboard.
 *
 * Renders an SVG network graph with the OAK daemon as a central hub
 * and satellite nodes for each active subsystem. The hub is clickable
 * (navigates to /config). Two offshoots branch from the Team Relay:
 * Swarm (cross-project federation) and MCP (tool server for agents).
 * When governance is enabled, a governance node appears in the ring
 * with per-action breakdown on hover. Fully responsive via viewBox.
 */

import { useState, useMemo, useCallback, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import type { DaemonStatus } from "@/hooks/use-status";
import type { SessionItem } from "@/hooks/use-activity";

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const HUB_R = 38;
const NODE_R = 26;
const SWARM_R = 22;
const MCP_R = 22;

const CATEGORY_COLORS = {
    hub:        { fill: "#14b8a6", glow: "#14b8a6", ring: "#0d9488" },
    input:      { fill: "#10b981", glow: "#10b981", ring: "#059669" },
    data:       { fill: "#8b5cf6", glow: "#8b5cf6", ring: "#7c3aed" },
    storage:    { fill: "#3b82f6", glow: "#3b82f6", ring: "#2563eb" },
    network:    { fill: "#f59e0b", glow: "#f59e0b", ring: "#d97706" },
    swarm:      { fill: "#ec4899", glow: "#ec4899", ring: "#db2777" },
    mcp:        { fill: "#a855f7", glow: "#a855f7", ring: "#9333ea" },
    governance: { fill: "#06b6d4", glow: "#06b6d4", ring: "#0891b2" },
    inactive:   { fill: "#6b7280", glow: "#6b7280", ring: "#4b5563" },
} as const;

type Category = keyof typeof CATEGORY_COLORS;

/** Team MCP tool names shown in tooltip (subset; count indicates full set). */
const TEAM_MCP_TOOLS = ["oak_search", "oak_remember", "oak_context", "oak_resolve_memory", "oak_stats"];
const TEAM_MCP_TOTAL_TOOLS = 11;

/** Governance action colors for the breakdown tooltip. */
const GOV_ACTION_COLORS: Record<string, string> = {
    allow: "#10b981",
    observe: "#3b82f6",
    warn: "#f59e0b",
    deny: "#ef4444",
};
const GOV_ACTIONS = ["allow", "observe", "warn", "deny"];

/* ------------------------------------------------------------------ */
/*  Data types                                                         */
/* ------------------------------------------------------------------ */

export interface GovernanceData {
    enabled: boolean;
    total: number;
    byAction: Record<string, number>;
}

interface TopoNode {
    id: string;
    label: string;
    sublabel: string;
    detail?: string;
    href?: string;
    category: Category;
    active: boolean;
}

interface TopologyData {
    primary: TopoNode[];
    swarm: TopoNode | null;
    showMcp: boolean;
}

interface Point { x: number; y: number }

type HoverState =
    | { type: "node"; node: TopoNode; pos: Point }
    | { type: "hub" }
    | { type: "mcp"; pos: Point }
    | null;

/* ------------------------------------------------------------------ */
/*  Build topology from daemon status                                  */
/* ------------------------------------------------------------------ */

function buildTopology(
    status: DaemonStatus | undefined,
    sessions: SessionItem[],
    totalSessions: number,
    totalPlans: number,
    swarmName?: string,
    governance?: GovernanceData,
): TopologyData {
    if (!status) return { primary: [], swarm: null, showMcp: false };

    const activeSessions = sessions.filter((s) => s.status === "active").length;
    const memoriesCount = status.index_stats?.memories_stored ?? 0;

    const summModel = status.summarization?.enabled
        ? `${status.summarization.provider}:${status.summarization.model}`
        : null;
    const embeddingModel = status.embedding_provider || null;

    const primary: TopoNode[] = [
        {
            id: "sessions",
            label: activeSessions > 0 ? `${activeSessions} active` : "No active",
            sublabel: `${totalSessions} session${totalSessions !== 1 ? "s" : ""} total`,
            detail: summModel ? `Summarization: ${summModel}` : undefined,
            href: "/activity/sessions",
            category: activeSessions > 0 ? "input" : "inactive",
            active: activeSessions > 0,
        },
        {
            id: "observations",
            label: `${memoriesCount} obs`,
            sublabel: "Observations",
            detail: summModel ? `Model: ${summModel}` : undefined,
            href: "/activity/memories",
            category: memoriesCount > 0 ? "data" : "inactive",
            active: memoriesCount > 0,
        },
        {
            id: "plans",
            label: `${totalPlans} plan${totalPlans !== 1 ? "s" : ""}`,
            sublabel: "Implementation plans",
            href: "/activity/plans",
            category: totalPlans > 0 ? "data" : "inactive",
            active: totalPlans > 0,
        },
        {
            id: "chroma",
            label: `${status.index_stats?.files_indexed ?? 0} files`,
            sublabel: `ChromaDB ${status.storage?.chromadb_size_mb ?? "0"} MB`,
            detail: embeddingModel ? `Embedding: ${embeddingModel}` : undefined,
            href: "/devtools",
            category: "storage",
            active: (status.index_stats?.files_indexed ?? 0) > 0,
        },
        {
            id: "sqlite",
            label: `${status.storage?.sqlite_size_mb ?? "0"} MB`,
            sublabel: "SQLite",
            href: "/devtools",
            category: "storage",
            active: true,
        },
        {
            id: "filewatcher",
            label: status.file_watcher?.running
                ? `${status.index_stats?.files_indexed ?? 0} files`
                : "Inactive",
            sublabel: status.file_watcher?.running
                ? (status.file_watcher.pending_changes ?? 0) > 0
                    ? `File Watcher \u00b7 ${status.file_watcher.pending_changes} pending`
                    : "File Watcher"
                : "File Watcher",
            detail: embeddingModel ? `Embedding: ${embeddingModel}` : undefined,
            href: "/search?tab=code",
            category: status.file_watcher?.running ? "input" : "inactive",
            active: !!status.file_watcher?.running,
        },
    ];

    // Governance node — only shown when governance is enabled
    if (governance?.enabled) {
        primary.push({
            id: "governance",
            label: governance.total > 0 ? `${governance.total} event${governance.total !== 1 ? "s" : ""}` : "Active",
            sublabel: "Governance",
            href: "/governance",
            category: "governance",
            active: true,
        });
    }

    // Relay is always last so offshoot positioning is predictable
    primary.push({
        id: "relay",
        label: status.team?.connected
            ? `${status.team.members_online} node${status.team.members_online !== 1 ? "s" : ""}`
            : status.team?.configured ? "Configured" : "Off",
        sublabel: "Team Relay",
        href: "/team",
        category: status.team?.connected ? "network" : status.team?.configured ? "network" : "inactive",
        active: !!status.team?.connected,
    });

    // Swarm offshoot of relay
    const hasSwarm = status.team?.configured || status.cloud_relay?.connected;
    const swarm: TopoNode | null = hasSwarm ? {
        id: "swarm",
        label: "Swarm",
        sublabel: swarmName || (status.cloud_relay?.connected ? "Connected" : "Not connected"),
        href: "/team",
        category: status.cloud_relay?.connected ? "swarm" : "inactive",
        active: !!status.cloud_relay?.connected,
    } : null;

    // MCP offshoot of relay — shown when team is configured
    const showMcp = !!status.team?.configured || !!status.cloud_relay?.connected;

    return { primary, swarm, showMcp };
}

/* ------------------------------------------------------------------ */
/*  Geometry helpers                                                    */
/* ------------------------------------------------------------------ */

function radialPositions(n: number, radius: number): Point[] {
    if (n === 0) return [];
    const offset = -Math.PI / 2;
    return Array.from({ length: n }, (_, i) => {
        const angle = offset + (2 * Math.PI * i) / n;
        return { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius };
    });
}

function computeLayout(nodeCount: number, offshootCount: number) {
    const orbit = Math.max(120, Math.min(175, 100 + nodeCount * 10));
    const extent = orbit + NODE_R + (offshootCount > 0 ? 72 : 32);
    return { orbit, extent };
}

/**
 * Position offshoots branching from the relay node.
 * When two offshoots exist they spread ±0.3 rad from the relay's radial.
 * When only one exists it extends straight outward (offset = 0).
 */
function offshootPositions(
    relayPos: Point,
    orbit: number,
    hasSwarm: boolean,
    hasMcp: boolean,
): { swarmPos: Point | null; mcpPos: Point | null } {
    const baseAngle = Math.atan2(relayPos.y, relayPos.x);
    const both = hasSwarm && hasMcp;
    const spread = both ? 0.3 : 0;

    const swarmPos = hasSwarm
        ? (() => {
            const angle = baseAngle + spread;
            const r = orbit + NODE_R + SWARM_R + 14;
            return { x: Math.cos(angle) * r, y: Math.sin(angle) * r };
        })()
        : null;

    const mcpPos = hasMcp
        ? (() => {
            const angle = baseAngle - spread;
            const r = orbit + NODE_R + MCP_R + 14;
            return { x: Math.cos(angle) * r, y: Math.sin(angle) * r };
        })()
        : null;

    return { swarmPos, mcpPos };
}

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
                opacity={0.2}
            />
            <polygon
                points="50,24 74,38 74,62 50,76 26,62 26,38"
                fill="currentColor"
                className="text-background"
                opacity={0.5}
            />
            <circle cx={50} cy={50} r={8} fill="currentColor" className="text-primary" />
            <line x1={50} y1={42} x2={50} y2={24} stroke="currentColor" className="text-primary" strokeWidth={2.5} />
            <line x1={57} y1={46} x2={70} y2={38} stroke="currentColor" className="text-primary" strokeWidth={2.5} />
            <line x1={57} y1={54} x2={70} y2={62} stroke="currentColor" className="text-primary" strokeWidth={2.5} />
            <line x1={50} y1={58} x2={50} y2={76} stroke="currentColor" className="text-primary" strokeWidth={2.5} />
            <line x1={43} y1={54} x2={30} y2={62} stroke="currentColor" className="text-primary" strokeWidth={2.5} />
            <line x1={43} y1={46} x2={30} y2={38} stroke="currentColor" className="text-primary" strokeWidth={2.5} />
        </g>
    );
}

/* ------------------------------------------------------------------ */
/*  Category icons                                                     */
/* ------------------------------------------------------------------ */

function CategoryIcon({ category, nodeId }: { category: Category; nodeId?: string }) {
    const color = CATEGORY_COLORS[category].fill;
    switch (category) {
        case "input":
            return (
                <g>
                    <polyline
                        points="-4,-5 3,0 -4,5"
                        fill="none"
                        stroke={color}
                        strokeWidth={2}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                    />
                </g>
            );
        case "data":
            return (
                <g>
                    <polygon points="0,-6 4,0 0,6 -4,0" fill={color} opacity={0.9} />
                    {nodeId === "plans" && (
                        <>
                            <line x1={-6} y1={-3} x2={6} y2={-3} stroke={color} strokeWidth={1} opacity={0.5} />
                            <line x1={-6} y1={0} x2={6} y2={0} stroke={color} strokeWidth={1} opacity={0.5} />
                            <line x1={-6} y1={3} x2={6} y2={3} stroke={color} strokeWidth={1} opacity={0.5} />
                        </>
                    )}
                </g>
            );
        case "storage":
            return (
                <g>
                    <ellipse cx={0} cy={-3} rx={5} ry={2.5} fill="none" stroke={color} strokeWidth={1.5} />
                    <line x1={-5} y1={-3} x2={-5} y2={4} stroke={color} strokeWidth={1.5} />
                    <line x1={5} y1={-3} x2={5} y2={4} stroke={color} strokeWidth={1.5} />
                    <ellipse cx={0} cy={4} rx={5} ry={2.5} fill="none" stroke={color} strokeWidth={1.5} />
                </g>
            );
        case "network":
            return (
                <g>
                    <circle cx={-3} cy={0} r={4} fill="none" stroke={color} strokeWidth={1.5} />
                    <circle cx={3} cy={0} r={4} fill="none" stroke={color} strokeWidth={1.5} />
                    <circle cx={0} cy={-2} r={3.5} fill="none" stroke={color} strokeWidth={1.5} />
                </g>
            );
        case "swarm":
            return (
                <g>
                    <circle cx={0} cy={-4} r={2} fill={color} />
                    <circle cx={-4} cy={3} r={2} fill={color} />
                    <circle cx={4} cy={3} r={2} fill={color} />
                    <line x1={0} y1={-4} x2={-4} y2={3} stroke={color} strokeWidth={1} opacity={0.7} />
                    <line x1={0} y1={-4} x2={4} y2={3} stroke={color} strokeWidth={1} opacity={0.7} />
                    <line x1={-4} y1={3} x2={4} y2={3} stroke={color} strokeWidth={1} opacity={0.7} />
                </g>
            );
        case "governance":
            return (
                <g>
                    {/* Shield with checkmark */}
                    <path
                        d="M0,-7 L5.5,-4 L5.5,1.5 L0,6.5 L-5.5,1.5 L-5.5,-4 Z"
                        fill="none"
                        stroke={color}
                        strokeWidth={1.5}
                        strokeLinejoin="round"
                    />
                    <path
                        d="M-2,0 L-0.5,1.5 L2.5,-1.5"
                        fill="none"
                        stroke={color}
                        strokeWidth={1.5}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                    />
                </g>
            );
        default:
            return <circle r={3} fill={color} opacity={0.5} />;
    }
}

/* ------------------------------------------------------------------ */
/*  MCP icon (plug shape, reused from swarm topology)                  */
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
/*  Sub-components                                                     */
/* ------------------------------------------------------------------ */

interface EdgeProps {
    x1: number; y1: number; x2: number; y2: number;
    active: boolean;
    category: Category;
    index: number;
    indexing: boolean;
}

function Edge({ x1, y1, x2, y2, active, category, index, indexing }: EdgeProps) {
    const color = active ? CATEGORY_COLORS[category] : CATEGORY_COLORS.inactive;
    const fast = indexing && (category === "storage" || category === "data");
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
                    values="0.12;0.55;0.12"
                    dur={fast ? `${1.5 + index * 0.2}s` : `${2.5 + index * 0.3}s`}
                    repeatCount="indefinite"
                />
            )}
        </line>
    );
}

interface SatelliteProps {
    node: TopoNode;
    pos: Point;
    radius?: number;
    onHover: (node: TopoNode | null, pos: Point | null) => void;
    onClick?: (href: string) => void;
}

function Satellite({ node, pos, radius = NODE_R, onHover, onClick }: SatelliteProps) {
    const color = node.active ? CATEGORY_COLORS[node.category] : CATEGORY_COLORS.inactive;

    return (
        <g
            transform={`translate(${pos.x},${pos.y})`}
            className="cursor-pointer"
            onMouseEnter={() => onHover(node, pos)}
            onMouseLeave={() => onHover(null, null)}
            onClick={() => { if (node.href && onClick) onClick(node.href); }}
        >
            <circle r={radius + 5} fill={color.glow} opacity={0.06}>
                {node.active && (
                    <animate
                        attributeName="r"
                        values={`${radius + 2};${radius + 8};${radius + 2}`}
                        dur="3s"
                        repeatCount="indefinite"
                    />
                )}
            </circle>
            <circle r={radius} fill="none" stroke={color.ring} strokeWidth={1.5} opacity={0.5} />
            <circle r={radius - 3} fill={color.fill} opacity={0.12} />
            <CategoryIcon category={node.active ? node.category : "inactive"} nodeId={node.id} />

            <text
                y={radius + 16}
                textAnchor="middle"
                className="fill-foreground font-medium"
                style={{ fontFamily: "inherit", fontSize: radius < NODE_R ? 10.5 : 12 }}
            >
                {truncateLabel(node.label, 16)}
            </text>
            <text
                y={radius + 29}
                textAnchor="middle"
                className="fill-muted-foreground"
                style={{ fontFamily: "inherit", fontSize: radius < NODE_R ? 8.5 : 9.5 }}
            >
                {truncateLabel(node.sublabel, 22)}
            </text>
        </g>
    );
}

/* ------------------------------------------------------------------ */
/*  MCP offshoot node                                                  */
/* ------------------------------------------------------------------ */

interface McpNodeProps {
    pos: Point;
    onHover: (hovered: boolean) => void;
    onClick?: () => void;
}

function McpNode({ pos, onHover, onClick }: McpNodeProps) {
    const color = CATEGORY_COLORS.mcp;
    return (
        <g
            transform={`translate(${pos.x},${pos.y})`}
            className="cursor-pointer"
            onMouseEnter={() => onHover(true)}
            onMouseLeave={() => onHover(false)}
            onClick={onClick}
        >
            <circle r={MCP_R + 4} fill={color.glow} opacity={0.06}>
                <animate
                    attributeName="r"
                    values={`${MCP_R + 2};${MCP_R + 7};${MCP_R + 2}`}
                    dur="3s"
                    repeatCount="indefinite"
                />
            </circle>
            <circle r={MCP_R} fill="none" stroke={color.ring} strokeWidth={1.5} opacity={0.5} />
            <circle r={MCP_R - 3} fill={color.fill} opacity={0.12} />
            <McpIcon color={color.fill} />
            <text
                y={MCP_R + 14}
                textAnchor="middle"
                className="fill-foreground font-medium"
                style={{ fontFamily: "inherit", fontSize: 11 }}
            >
                MCP Server
            </text>
            <text
                y={MCP_R + 26}
                textAnchor="middle"
                className="fill-muted-foreground"
                style={{ fontFamily: "inherit", fontSize: 9 }}
            >
                {TEAM_MCP_TOTAL_TOOLS} tools
            </text>
        </g>
    );
}

/* ------------------------------------------------------------------ */
/*  Tooltips                                                           */
/* ------------------------------------------------------------------ */

function truncateLabel(text: string, maxLen: number): string {
    if (text.length <= maxLen) return text;
    return `${text.slice(0, maxLen - 1)}\u2026`;
}

interface TooltipProps { node: TopoNode; pos: Point; extent: number }

function Tooltip({ node, pos, extent }: TooltipProps) {
    const color = node.active ? CATEGORY_COLORS[node.category] : CATEGORY_COLORS.inactive;
    const hasDetail = !!node.detail;
    const tooltipW = hasDetail ? 180 : 140;
    const tooltipH = hasDetail ? 56 : 42;
    const tx = Math.max(-extent + tooltipW / 2 + 8, Math.min(extent - tooltipW / 2 - 8, pos.x));
    const aboveY = pos.y - NODE_R - 48;
    const belowY = pos.y + NODE_R + 42;
    const ty = aboveY - tooltipH / 2 < -extent ? belowY : aboveY;

    return (
        <g transform={`translate(${tx},${ty})`} pointerEvents="none">
            <rect x={-tooltipW / 2} y={-tooltipH / 2} width={tooltipW} height={tooltipH}
                rx={6} className="fill-popover stroke-border" strokeWidth={1} />
            <text y={hasDetail ? -12 : -5} textAnchor="middle"
                className="fill-foreground font-semibold"
                style={{ fontFamily: "inherit", fontSize: 11 }}>
                {node.label.length > 22 ? `${node.label.slice(0, 20)}\u2026` : node.label}
            </text>
            <g transform={`translate(0, ${hasDetail ? 2 : 9})`}>
                <circle cx={-tooltipW / 2 + 11} cy={0} r={3} fill={color.fill} />
                <text x={-tooltipW / 2 + 18} y={3} className="fill-muted-foreground"
                    style={{ fontFamily: "inherit", fontSize: 9 }}>
                    {node.sublabel.length > 28 ? `${node.sublabel.slice(0, 26)}\u2026` : node.sublabel}
                </text>
            </g>
            {hasDetail && (
                <text y={tooltipH / 2 - 8} textAnchor="middle"
                    className="fill-muted-foreground"
                    style={{ fontFamily: "inherit", fontSize: 8.5, fontStyle: "italic" }}>
                    {node.detail!.length > 30 ? `${node.detail!.slice(0, 28)}\u2026` : node.detail}
                </text>
            )}
        </g>
    );
}

function HubTooltip() {
    const tooltipW = 120;
    const tooltipH = 30;
    const ty = -(HUB_R + 38);
    return (
        <g transform={`translate(0,${ty})`} pointerEvents="none">
            <rect x={-tooltipW / 2} y={-tooltipH / 2} width={tooltipW} height={tooltipH}
                rx={6} className="fill-popover stroke-border" strokeWidth={1} />
            <text y={4} textAnchor="middle" className="fill-foreground font-semibold"
                style={{ fontFamily: "inherit", fontSize: 11 }}>
                Configuration
            </text>
        </g>
    );
}

function McpTooltip({ pos, extent }: { pos: Point; extent: number }) {
    const tooltipW = 180;
    const tooltipH = 18 + TEAM_MCP_TOOLS.length * 13 + 14;
    const tx = Math.max(-extent + tooltipW / 2 + 8, Math.min(extent - tooltipW / 2 - 8, pos.x));
    const aboveY = pos.y - MCP_R - 40;
    const belowY = pos.y + MCP_R + 35;
    const ty = aboveY - tooltipH / 2 < -extent ? belowY : aboveY;

    return (
        <g transform={`translate(${tx},${ty})`} pointerEvents="none">
            <rect x={-tooltipW / 2} y={-tooltipH / 2} width={tooltipW} height={tooltipH}
                rx={6} className="fill-popover stroke-border" strokeWidth={1} />
            <text y={-tooltipH / 2 + 14} textAnchor="middle"
                className="fill-foreground font-semibold"
                style={{ fontFamily: "inherit", fontSize: 11 }}>
                Team MCP Tools
            </text>
            {TEAM_MCP_TOOLS.map((tool, i) => (
                <text key={tool} y={-tooltipH / 2 + 28 + i * 13}
                    textAnchor="middle" className="fill-muted-foreground"
                    style={{ fontFamily: "inherit", fontSize: 9 }}>
                    {tool}
                </text>
            ))}
            <text y={tooltipH / 2 - 6} textAnchor="middle" className="fill-muted-foreground"
                style={{ fontFamily: "inherit", fontSize: 8, fontStyle: "italic" }}>
                {TEAM_MCP_TOTAL_TOOLS} tools total
            </text>
        </g>
    );
}

function GovernanceTooltip({ pos, extent, byAction, total }: {
    pos: Point; extent: number; byAction: Record<string, number>; total: number;
}) {
    const tooltipW = 160;
    const tooltipH = 18 + GOV_ACTIONS.length * 15 + 14;
    const tx = Math.max(-extent + tooltipW / 2 + 8, Math.min(extent - tooltipW / 2 - 8, pos.x));
    const aboveY = pos.y - NODE_R - 48;
    const belowY = pos.y + NODE_R + 42;
    const ty = aboveY - tooltipH / 2 < -extent ? belowY : aboveY;

    return (
        <g transform={`translate(${tx},${ty})`} pointerEvents="none">
            <rect x={-tooltipW / 2} y={-tooltipH / 2} width={tooltipW} height={tooltipH}
                rx={6} className="fill-popover stroke-border" strokeWidth={1} />
            <text y={-tooltipH / 2 + 14} textAnchor="middle"
                className="fill-foreground font-semibold"
                style={{ fontFamily: "inherit", fontSize: 11 }}>
                Governance ({total})
            </text>
            {GOV_ACTIONS.map((action, i) => {
                const count = byAction[action] ?? 0;
                const color = GOV_ACTION_COLORS[action] ?? "#6b7280";
                return (
                    <g key={action} transform={`translate(0, ${-tooltipH / 2 + 30 + i * 15})`}>
                        <circle cx={-tooltipW / 2 + 14} cy={0} r={3.5} fill={color} opacity={0.8} />
                        <text x={-tooltipW / 2 + 24} y={3.5}
                            className="fill-muted-foreground"
                            style={{ fontFamily: "inherit", fontSize: 10 }}>
                            {action}
                        </text>
                        <text x={tooltipW / 2 - 14} y={3.5}
                            textAnchor="end"
                            className="fill-foreground font-medium"
                            style={{ fontFamily: "inherit", fontSize: 10 }}>
                            {count}
                        </text>
                    </g>
                );
            })}
        </g>
    );
}

/* ------------------------------------------------------------------ */
/*  Main component                                                     */
/* ------------------------------------------------------------------ */

interface TeamTopologyProps {
    status: DaemonStatus | undefined;
    sessions: SessionItem[];
    totalSessions: number;
    totalPlans: number;
    swarmName?: string;
    governance?: GovernanceData;
}

export function TeamTopology({ status, sessions, totalSessions, totalPlans, swarmName, governance }: TeamTopologyProps) {
    const navigate = useNavigate();
    const [hovered, setHovered] = useState<HoverState>(null);

    const handleNodeHover = useCallback(
        (node: TopoNode | null, pos: Point | null) => {
            setHovered(node && pos ? { type: "node", node, pos } : null);
        },
        [],
    );

    const handleNodeClick = useCallback(
        (href: string) => navigate(href),
        [navigate],
    );

    const topology = useMemo(
        () => buildTopology(status, sessions, totalSessions, totalPlans, swarmName, governance),
        [status, sessions, totalSessions, totalPlans, swarmName, governance],
    );

    const { primary, swarm, showMcp } = topology;
    const offshootCount = (swarm ? 1 : 0) + (showMcp ? 1 : 0);

    const { orbit, extent } = useMemo(
        () => computeLayout(primary.length, offshootCount),
        [primary.length, offshootCount],
    );

    const positions = useMemo(
        () => radialPositions(primary.length, orbit),
        [primary.length, orbit],
    );

    // Find relay index for offshoot positioning
    const relayIndex = primary.findIndex((n) => n.id === "relay");
    const relayPos = relayIndex >= 0 ? positions[relayIndex] : null;

    const { swarmPos, mcpPos } = useMemo(
        () => relayPos
            ? offshootPositions(relayPos, orbit, !!swarm, showMcp)
            : { swarmPos: null, mcpPos: null },
        [relayPos, orbit, swarm, showMcp],
    );

    const hubColor = CATEGORY_COLORS.hub;
    const isIndexing = !!status?.indexing;

    /* Orbit ring rotation animation */
    const rotationRef = useRef(0);
    const rafRef = useRef<number>(undefined);
    const orbitRingRef = useRef<SVGCircleElement>(null);

    useEffect(() => {
        if (primary.length === 0) return;
        const tick = () => {
            rotationRef.current = (rotationRef.current + 0.15) % 360;
            if (orbitRingRef.current) {
                orbitRingRef.current.setAttribute("stroke-dashoffset", String(rotationRef.current));
            }
            rafRef.current = requestAnimationFrame(tick);
        };
        rafRef.current = requestAnimationFrame(tick);
        return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
    }, [primary.length]);

    return (
        <div className="rounded-lg border bg-card text-card-foreground shadow-sm">
            <div className="px-2 pt-2 pb-2">
                {primary.length === 0 ? (
                    <EmptyState />
                ) : (
                    <svg
                        viewBox={`${-extent} ${-extent} ${extent * 2} ${extent * 2}`}
                        className="w-full"
                        style={{ minHeight: 280 }}
                    >
                        <defs>
                            <filter id="team-hub-glow" x="-50%" y="-50%" width="200%" height="200%">
                                <feGaussianBlur stdDeviation="6" result="blur" />
                                <feMerge>
                                    <feMergeNode in="blur" />
                                    <feMergeNode in="SourceGraphic" />
                                </feMerge>
                            </filter>
                        </defs>

                        {/* Orbit ring */}
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

                        {/* Edges: hub → primary nodes */}
                        {primary.map((node, i) => (
                            <Edge
                                key={node.id}
                                x1={0} y1={0}
                                x2={positions[i].x} y2={positions[i].y}
                                active={node.active}
                                category={node.category}
                                index={i}
                                indexing={isIndexing}
                            />
                        ))}

                        {/* Edge: relay → swarm offshoot */}
                        {swarm && relayPos && swarmPos && (
                            <Edge
                                x1={relayPos.x} y1={relayPos.y}
                                x2={swarmPos.x} y2={swarmPos.y}
                                active={swarm.active}
                                category={swarm.category}
                                index={primary.length}
                                indexing={false}
                            />
                        )}

                        {/* Edge: relay → MCP offshoot */}
                        {showMcp && relayPos && mcpPos && (
                            <Edge
                                x1={relayPos.x} y1={relayPos.y}
                                x2={mcpPos.x} y2={mcpPos.y}
                                active={true}
                                category="mcp"
                                index={primary.length + 1}
                                indexing={false}
                            />
                        )}

                        {/* Primary satellite nodes */}
                        {primary.map((node, i) => (
                            <Satellite
                                key={node.id}
                                node={node}
                                pos={positions[i]}
                                onHover={handleNodeHover}
                                onClick={handleNodeClick}
                            />
                        ))}

                        {/* Swarm offshoot */}
                        {swarm && swarmPos && (
                            <Satellite
                                node={swarm}
                                pos={swarmPos}
                                radius={SWARM_R}
                                onHover={handleNodeHover}
                                onClick={handleNodeClick}
                            />
                        )}

                        {/* MCP offshoot */}
                        {showMcp && mcpPos && (
                            <McpNode
                                pos={mcpPos}
                                onHover={(h) => setHovered(h ? { type: "mcp", pos: mcpPos } : null)}
                                onClick={() => navigate("/connect")}
                            />
                        )}

                        {/* Hub node (clickable → Configuration) */}
                        <g
                            filter="url(#team-hub-glow)"
                            className="cursor-pointer"
                            onMouseEnter={() => setHovered({ type: "hub" })}
                            onMouseLeave={() => setHovered(null)}
                            onClick={() => navigate("/config")}
                        >
                            <circle r={HUB_R + 10} fill={hubColor.glow} opacity={0.06}>
                                {isIndexing && (
                                    <animate
                                        attributeName="opacity"
                                        values="0.04;0.16;0.04"
                                        dur="2s"
                                        repeatCount="indefinite"
                                    />
                                )}
                            </circle>
                            <circle r={HUB_R} fill="none" stroke={hubColor.ring} strokeWidth={2.5} opacity={0.6} />
                            <circle r={HUB_R - 4} fill={hubColor.fill} opacity={0.1} />
                            <HubIcon size={HUB_R * 1.4} />
                            <text
                                y={HUB_R + 18}
                                textAnchor="middle"
                                className="fill-foreground font-semibold"
                                style={{ fontFamily: "inherit", fontSize: 13 }}
                            >
                                OAK
                            </text>
                        </g>

                        {/* Tooltips */}
                        {hovered?.type === "hub" && (
                            <HubTooltip />
                        )}
                        {hovered?.type === "mcp" && (
                            <McpTooltip pos={hovered.pos} extent={extent} />
                        )}
                        {hovered?.type === "node" && hovered.node.id === "governance" && governance && (
                            <GovernanceTooltip
                                pos={hovered.pos}
                                extent={extent}
                                byAction={governance.byAction}
                                total={governance.total}
                            />
                        )}
                        {hovered?.type === "node" && hovered.node.id !== "governance" && (
                            <Tooltip node={hovered.node} pos={hovered.pos} extent={extent} />
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
        <div className="flex flex-col items-center justify-center py-14 text-center">
            <div className="relative mb-4">
                <svg width={120} height={120} viewBox="-60 -60 120 120">
                    <circle
                        r={42} fill="none" stroke="currentColor" className="text-border"
                        strokeWidth={1} strokeDasharray="3 6" opacity={0.4}
                    />
                    <circle r={16} fill="currentColor" className="text-muted-foreground" opacity={0.06} />
                    <g opacity={0.4}><HubIcon size={24} /></g>
                </svg>
            </div>
            <p className="text-sm text-muted-foreground">Waiting for system status&hellip;</p>
        </div>
    );
}
