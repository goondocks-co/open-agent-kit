/**
 * Governance audit event feed with filters.
 *
 * Features:
 * - Paginated list of governance audit events
 * - Filters by action (allow/deny/warn/observe), agent, tool, time range
 * - Decision badges with color coding
 * - Summary stats panel at the top
 */

import { useState } from "react";
import { Link } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
    useGovernanceAudit,
    useGovernanceAuditSummary,
    type AuditEvent,
    type AuditQueryParams,
} from "@/hooks/use-governance";
import {
    Shield,
    ShieldAlert,
    ShieldCheck,
    Eye,
    AlertTriangle,
    RefreshCw,
    ChevronLeft,
    ChevronRight,
    Filter,
    X,
} from "lucide-react";
import { cn } from "@/lib/utils";

// =============================================================================
// Constants
// =============================================================================

const ACTION_CONFIG: Record<string, { label: string; color: string; bgColor: string; icon: typeof Shield }> = {
    allow: { label: "Allow", color: "text-green-600", bgColor: "bg-green-500/10", icon: ShieldCheck },
    deny: { label: "Deny", color: "text-red-500", bgColor: "bg-red-500/10", icon: ShieldAlert },
    warn: { label: "Warn", color: "text-amber-500", bgColor: "bg-amber-500/10", icon: AlertTriangle },
    observe: { label: "Observe", color: "text-blue-500", bgColor: "bg-blue-500/10", icon: Eye },
};

const CATEGORY_COLORS: Record<string, string> = {
    filesystem: "bg-violet-500/10 text-violet-600",
    shell: "bg-orange-500/10 text-orange-600",
    network: "bg-cyan-500/10 text-cyan-600",
    agent: "bg-pink-500/10 text-pink-600",
    other: "bg-gray-500/10 text-gray-500",
};

const PAGE_SIZE = 25;

const TIME_RANGES = [
    { label: "Last hour", seconds: 3600 },
    { label: "Last 24h", seconds: 86400 },
    { label: "Last 7d", seconds: 604800 },
    { label: "Last 30d", seconds: 2592000 },
    { label: "All time", seconds: 0 },
] as const;

// =============================================================================
// Helper Components
// =============================================================================

function ActionBadge({ action }: { action: string }) {
    const config = ACTION_CONFIG[action] ?? ACTION_CONFIG.observe;
    const Icon = config.icon;

    return (
        <span className={cn("flex items-center gap-1 px-2 py-0.5 text-xs rounded-full font-medium", config.bgColor, config.color)}>
            <Icon className="w-3 h-3" />
            {config.label}
        </span>
    );
}

function CategoryChip({ category }: { category: string | null }) {
    if (!category) return null;
    const colorClass = CATEGORY_COLORS[category] ?? CATEGORY_COLORS.other;

    return (
        <span className={cn("px-1.5 py-0.5 text-xs rounded", colorClass)}>
            {category}
        </span>
    );
}

function SummaryCard({ label, value, color }: { label: string; value: number; color?: string }) {
    return (
        <div className="flex flex-col items-center p-3 rounded-md border bg-card">
            <span className={cn("text-2xl font-bold tabular-nums", color)}>{value.toLocaleString()}</span>
            <span className="text-xs text-muted-foreground">{label}</span>
        </div>
    );
}

function formatEpochRelative(epoch: number): string {
    const now = Math.floor(Date.now() / 1000);
    const diff = now - epoch;
    if (diff < 60) return "just now";
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    if (diff < 172800) return "yesterday";
    return `${Math.floor(diff / 86400)}d ago`;
}

function AuditEventRow({ event }: { event: AuditEvent }) {
    const [expanded, setExpanded] = useState(false);

    return (
        <div
            className="border rounded-md p-3 hover:bg-muted/30 transition-colors cursor-pointer"
            onClick={() => setExpanded(!expanded)}
        >
            {/* Main row */}
            <div className="flex items-center gap-3">
                <ActionBadge action={event.action} />
                <code className="text-sm font-medium">{event.tool_name}</code>
                <CategoryChip category={event.tool_category} />
                {event.rule_id && (
                    <span className="text-xs text-muted-foreground">
                        rule: <code className="bg-muted px-1 rounded">{event.rule_id}</code>
                    </span>
                )}
                <span className="ml-auto text-xs text-muted-foreground whitespace-nowrap">
                    {formatEpochRelative(event.created_at_epoch)}
                </span>
            </div>

            {/* Expanded details */}
            {expanded && (
                <div className="mt-3 pt-3 border-t space-y-2 text-sm">
                    <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                        <div><span className="font-medium text-muted-foreground">Agent:</span> {event.agent}</div>
                        <div className="col-span-2">
                            <span className="font-medium text-muted-foreground">Session:</span>{" "}
                            <Link
                                to={`/activity/sessions/${event.session_id}`}
                                onClick={(e) => e.stopPropagation()}
                                className="text-primary hover:underline"
                            >
                                {event.session_title || `Session ${event.session_id.slice(0, 8)}…`}
                            </Link>
                        </div>
                        <div><span className="font-medium text-muted-foreground">Mode:</span> {event.enforcement_mode}</div>
                        {event.evaluation_ms !== null && (
                            <div><span className="font-medium text-muted-foreground">Eval time:</span> {event.evaluation_ms}ms</div>
                        )}
                    </div>
                    {event.reason && (
                        <div className="text-xs">
                            <span className="font-medium text-muted-foreground">Reason:</span>{" "}
                            <span>{event.reason}</span>
                        </div>
                    )}
                    {event.matched_pattern && (
                        <div className="text-xs">
                            <span className="font-medium text-muted-foreground">Pattern:</span>{" "}
                            <code className="bg-muted px-1 rounded">{event.matched_pattern}</code>
                        </div>
                    )}
                    {event.tool_input_summary && (
                        <div className="text-xs">
                            <span className="font-medium text-muted-foreground">Input:</span>{" "}
                            <code className="bg-muted px-1 rounded text-xs break-all">{event.tool_input_summary.slice(0, 200)}</code>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

// =============================================================================
// Main Component
// =============================================================================

export default function GovernanceAudit() {
    const [actionFilter, setActionFilter] = useState<string>("");
    const [toolFilter, setToolFilter] = useState<string>("");
    const [timeRange, setTimeRange] = useState<number>(604800); // Default: last 7 days
    const [offset, setOffset] = useState(0);
    const [showFilters, setShowFilters] = useState(false);

    const params: AuditQueryParams = {
        limit: PAGE_SIZE,
        offset,
        ...(actionFilter && { action: actionFilter }),
        ...(toolFilter && { tool: toolFilter }),
        ...(timeRange > 0 && { since: Math.floor(Date.now() / 1000) - timeRange }),
    };

    const { data, isLoading, isFetching, refetch } = useGovernanceAudit(params);
    const { data: summary } = useGovernanceAuditSummary(7);

    const events = data?.events ?? [];
    const total = data?.total ?? 0;
    const hasNextPage = offset + PAGE_SIZE < total;
    const hasPrevPage = offset > 0;

    const clearFilters = () => {
        setActionFilter("");
        setToolFilter("");
        setTimeRange(604800);
        setOffset(0);
    };

    const hasActiveFilters = actionFilter || toolFilter || timeRange !== 604800;

    return (
        <div className="space-y-4">
            {/* Summary Cards */}
            {summary && summary.total > 0 && (
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                    <SummaryCard label="Total (7d)" value={summary.total} />
                    <SummaryCard label="Allow" value={summary.by_action.allow ?? 0} color="text-green-600" />
                    <SummaryCard label="Observe" value={summary.by_action.observe ?? 0} color="text-blue-500" />
                    <SummaryCard label="Warn" value={summary.by_action.warn ?? 0} color="text-amber-500" />
                    <SummaryCard label="Deny" value={summary.by_action.deny ?? 0} color="text-red-500" />
                </div>
            )}

            {/* Header + Controls */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <span className="text-sm text-muted-foreground">
                        {total.toLocaleString()} {total === 1 ? "event" : "events"}
                    </span>
                </div>

                <div className="flex items-center gap-2">
                    <Button
                        variant={showFilters ? "default" : "outline"}
                        size="sm"
                        onClick={() => setShowFilters(!showFilters)}
                    >
                        <Filter className="w-4 h-4 mr-1" />
                        Filters
                        {hasActiveFilters && (
                            <span className="ml-1 w-2 h-2 bg-primary-foreground rounded-full" />
                        )}
                    </Button>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => refetch()}
                        disabled={isFetching}
                    >
                        <RefreshCw className={cn("w-4 h-4 mr-1", isFetching && "animate-spin")} />
                        Refresh
                    </Button>
                </div>
            </div>

            {/* Filters Panel */}
            {showFilters && (
                <div className="border rounded-md p-4 space-y-3 bg-card">
                    <div className="flex items-center justify-between">
                        <span className="text-sm font-medium">Filters</span>
                        {hasActiveFilters && (
                            <Button variant="ghost" size="sm" onClick={clearFilters}>
                                <X className="w-3 h-3 mr-1" />
                                Clear all
                            </Button>
                        )}
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                        {/* Action filter */}
                        <div className="space-y-1">
                            <label className="text-xs font-medium text-muted-foreground">Decision</label>
                            <select
                                value={actionFilter}
                                onChange={(e) => { setActionFilter(e.target.value); setOffset(0); }}
                                className="w-full px-3 py-1.5 rounded-md border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                            >
                                <option value="">All decisions</option>
                                <option value="allow">Allow</option>
                                <option value="deny">Deny</option>
                                <option value="warn">Warn</option>
                                <option value="observe">Observe</option>
                            </select>
                        </div>

                        {/* Tool filter */}
                        <div className="space-y-1">
                            <label className="text-xs font-medium text-muted-foreground">Tool</label>
                            <input
                                type="text"
                                value={toolFilter}
                                onChange={(e) => { setToolFilter(e.target.value); setOffset(0); }}
                                placeholder="e.g. Bash, Write..."
                                className="w-full px-3 py-1.5 rounded-md border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                            />
                        </div>

                        {/* Time range */}
                        <div className="space-y-1">
                            <label className="text-xs font-medium text-muted-foreground">Time range</label>
                            <select
                                value={timeRange}
                                onChange={(e) => { setTimeRange(Number(e.target.value)); setOffset(0); }}
                                className="w-full px-3 py-1.5 rounded-md border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                            >
                                {TIME_RANGES.map((range) => (
                                    <option key={range.seconds} value={range.seconds}>
                                        {range.label}
                                    </option>
                                ))}
                            </select>
                        </div>
                    </div>
                </div>
            )}

            {/* Event List */}
            {isLoading ? (
                <div className="space-y-2">
                    {[1, 2, 3, 4, 5].map((i) => (
                        <div key={i} className="border rounded-md p-3 animate-pulse">
                            <div className="flex items-center gap-3">
                                <div className="w-16 h-5 bg-muted rounded-full" />
                                <div className="w-20 h-4 bg-muted rounded" />
                                <div className="w-14 h-4 bg-muted rounded" />
                                <div className="ml-auto w-12 h-3 bg-muted rounded" />
                            </div>
                        </div>
                    ))}
                </div>
            ) : events.length === 0 ? (
                <Card>
                    <CardContent className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                        <Shield className="w-12 h-12 mb-4 opacity-30" />
                        <p className="text-sm">No audit events found</p>
                        <p className="text-xs mt-1">
                            {hasActiveFilters
                                ? "Try adjusting your filters."
                                : "Events will appear here when governance evaluates tool calls."}
                        </p>
                    </CardContent>
                </Card>
            ) : (
                <div className="space-y-2">
                    {events.map((event) => (
                        <AuditEventRow key={event.id} event={event} />
                    ))}
                </div>
            )}

            {/* Pagination */}
            {total > PAGE_SIZE && (
                <div className="flex items-center justify-between pt-2">
                    <span className="text-xs text-muted-foreground">
                        Showing {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total.toLocaleString()}
                    </span>
                    <div className="flex items-center gap-2">
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                            disabled={!hasPrevPage}
                        >
                            <ChevronLeft className="w-4 h-4" />
                        </Button>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setOffset(offset + PAGE_SIZE)}
                            disabled={!hasNextPage}
                        >
                            <ChevronRight className="w-4 h-4" />
                        </Button>
                    </div>
                </div>
            )}
        </div>
    );
}
