/**
 * Schedules component for viewing and managing agent cron schedules.
 *
 * Features:
 * - List all scheduled agent instances
 * - Show schedule status (cron, next run, last run)
 * - Enable/disable schedules
 * - Manually trigger scheduled runs
 * - Sync schedules from YAML definitions
 */

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
    useSchedules,
    useUpdateSchedule,
    useRunSchedule,
    useSyncSchedules,
    type ScheduleStatus,
} from "@/hooks/use-schedules";
import {
    Calendar,
    Clock,
    Play,
    RefreshCw,
    Loader2,
    CheckCircle,
    XCircle,
    AlertCircle,
    Power,
    PowerOff,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { formatRelativeTime } from "@/lib/constants";

// =============================================================================
// Helper Components
// =============================================================================

function ScheduleStatusBadge({ schedule }: { schedule: ScheduleStatus }) {
    if (!schedule.has_definition) {
        return (
            <span className="flex items-center gap-1 px-2 py-0.5 text-xs rounded-full bg-gray-500/10 text-gray-500">
                <AlertCircle className="w-3 h-3" />
                Orphaned
            </span>
        );
    }

    if (!schedule.enabled) {
        return (
            <span className="flex items-center gap-1 px-2 py-0.5 text-xs rounded-full bg-gray-500/10 text-gray-500">
                <XCircle className="w-3 h-3" />
                Disabled
            </span>
        );
    }

    return (
        <span className="flex items-center gap-1 px-2 py-0.5 text-xs rounded-full bg-green-500/10 text-green-600">
            <CheckCircle className="w-3 h-3" />
            Active
        </span>
    );
}

function ScheduleRow({
    schedule,
    onToggle,
    onRun,
    isToggling,
    isRunning,
}: {
    schedule: ScheduleStatus;
    onToggle: (instanceName: string, enabled: boolean) => void;
    onRun: (instanceName: string) => void;
    isToggling: boolean;
    isRunning: boolean;
}) {
    const canRun = schedule.has_definition && schedule.has_db_record;
    const canToggle = schedule.has_db_record;

    return (
        <div className="border rounded-md p-4 space-y-3">
            {/* Header row */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <Calendar className="w-5 h-5 text-muted-foreground" />
                    <div>
                        <div className="flex items-center gap-2">
                            <span className="font-medium">{schedule.instance_name}</span>
                            <ScheduleStatusBadge schedule={schedule} />
                        </div>
                        {schedule.description && (
                            <p className="text-sm text-muted-foreground mt-0.5">
                                {schedule.description}
                            </p>
                        )}
                    </div>
                </div>

                <div className="flex items-center gap-3">
                    {/* Enable/Disable Toggle */}
                    {canToggle && (
                        <Button
                            variant={schedule.enabled ? "outline" : "ghost"}
                            size="sm"
                            onClick={() => onToggle(schedule.instance_name, !schedule.enabled)}
                            disabled={isToggling}
                            className={schedule.enabled ? "text-green-600" : "text-muted-foreground"}
                        >
                            {isToggling ? (
                                <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                            ) : schedule.enabled ? (
                                <Power className="w-4 h-4 mr-1" />
                            ) : (
                                <PowerOff className="w-4 h-4 mr-1" />
                            )}
                            {schedule.enabled ? "Enabled" : "Disabled"}
                        </Button>
                    )}

                    {/* Run Now Button */}
                    {canRun && (
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => onRun(schedule.instance_name)}
                            disabled={isRunning || !schedule.enabled}
                        >
                            {isRunning ? (
                                <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                            ) : (
                                <Play className="w-4 h-4 mr-1" />
                            )}
                            Run Now
                        </Button>
                    )}
                </div>
            </div>

            {/* Schedule details */}
            <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
                {schedule.cron && (
                    <div className="flex items-center gap-1">
                        <Clock className="w-4 h-4" />
                        <code className="bg-muted px-1 rounded text-xs">{schedule.cron}</code>
                    </div>
                )}

                {schedule.next_run_at && schedule.enabled && (
                    <div>
                        <span className="text-xs font-medium">Next:</span>{" "}
                        <span className="text-xs">{formatRelativeTime(schedule.next_run_at)}</span>
                    </div>
                )}

                {schedule.last_run_at && (
                    <div>
                        <span className="text-xs font-medium">Last:</span>{" "}
                        <span className="text-xs">{formatRelativeTime(schedule.last_run_at)}</span>
                    </div>
                )}

                {schedule.last_run_id && (
                    <div>
                        <span className="text-xs font-medium">Run ID:</span>{" "}
                        <code className="bg-muted px-1 rounded text-xs">{schedule.last_run_id.slice(0, 8)}</code>
                    </div>
                )}
            </div>

            {/* Warning for orphaned schedules */}
            {!schedule.has_definition && schedule.has_db_record && (
                <div className="text-xs text-amber-600 bg-amber-500/10 px-2 py-1 rounded">
                    This schedule exists in the database but its YAML definition was removed.
                    Run "Sync Schedules" to clean up.
                </div>
            )}
        </div>
    );
}

// =============================================================================
// Main Component
// =============================================================================

export default function Schedules() {
    const [runningInstance, setRunningInstance] = useState<string | null>(null);
    const [togglingInstance, setTogglingInstance] = useState<string | null>(null);

    const { data, isLoading, isFetching, refetch } = useSchedules();
    const updateSchedule = useUpdateSchedule();
    const runSchedule = useRunSchedule();
    const syncSchedules = useSyncSchedules();

    const schedules = data?.schedules ?? [];
    const schedulerRunning = data?.scheduler_running ?? false;

    const handleToggle = async (instanceName: string, enabled: boolean) => {
        setTogglingInstance(instanceName);
        try {
            await updateSchedule.mutateAsync({ instanceName, enabled });
        } finally {
            setTogglingInstance(null);
        }
    };

    const handleRun = async (instanceName: string) => {
        setRunningInstance(instanceName);
        try {
            await runSchedule.mutateAsync(instanceName);
        } finally {
            setRunningInstance(null);
        }
    };

    const handleSync = async () => {
        await syncSchedules.mutateAsync();
    };

    return (
        <div className="space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    {schedulerRunning ? (
                        <span className="flex items-center gap-1 text-xs text-green-600 bg-green-500/10 px-2 py-0.5 rounded-full">
                            <CheckCircle className="w-3 h-3" />
                            Scheduler Running
                        </span>
                    ) : (
                        <span className="flex items-center gap-1 text-xs text-amber-600 bg-amber-500/10 px-2 py-0.5 rounded-full">
                            <AlertCircle className="w-3 h-3" />
                            Scheduler Stopped
                        </span>
                    )}
                    {!isLoading && (
                        <span className="text-sm text-muted-foreground">
                            {schedules.length} {schedules.length === 1 ? "schedule" : "schedules"}
                        </span>
                    )}
                </div>

                <div className="flex items-center gap-2">
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={handleSync}
                        disabled={syncSchedules.isPending}
                    >
                        {syncSchedules.isPending ? (
                            <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                        ) : (
                            <RefreshCw className="w-4 h-4 mr-1" />
                        )}
                        Sync Schedules
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

            {/* Sync result message */}
            {syncSchedules.data && (
                <div className="text-sm text-muted-foreground bg-muted/50 px-3 py-2 rounded">
                    Sync complete: {syncSchedules.data.created} created, {syncSchedules.data.updated} updated,{" "}
                    {syncSchedules.data.removed} removed ({syncSchedules.data.total} total)
                </div>
            )}

            {/* Schedules list */}
            {isLoading ? (
                <div className="space-y-2">
                    {[1, 2, 3].map((i) => (
                        <div key={i} className="border rounded-md p-4 animate-pulse">
                            <div className="flex items-center gap-3">
                                <div className="w-5 h-5 bg-muted rounded" />
                                <div className="flex-1">
                                    <div className="h-4 bg-muted rounded w-1/4 mb-2" />
                                    <div className="h-3 bg-muted rounded w-1/2" />
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            ) : schedules.length === 0 ? (
                <Card>
                    <CardContent className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                        <Calendar className="w-12 h-12 mb-4 opacity-30" />
                        <p className="text-sm">No scheduled agents</p>
                        <p className="text-xs mt-1">
                            Add a <code className="bg-muted px-1 rounded">schedule</code> section to your agent
                            instance YAML files to enable cron-based execution.
                        </p>
                    </CardContent>
                </Card>
            ) : (
                <div className="space-y-2">
                    {schedules.map((schedule) => (
                        <ScheduleRow
                            key={schedule.instance_name}
                            schedule={schedule}
                            onToggle={handleToggle}
                            onRun={handleRun}
                            isToggling={togglingInstance === schedule.instance_name}
                            isRunning={runningInstance === schedule.instance_name}
                        />
                    ))}
                </div>
            )}
        </div>
    );
}
