/**
 * Schedules component for viewing and managing agent cron schedules.
 *
 * Features:
 * - List all scheduled agent tasks
 * - Create new schedules with cron expression picker
 * - Edit schedule cron/description
 * - Delete schedules with confirmation
 * - Enable/disable schedules
 * - Manually trigger scheduled runs
 * - Clean up orphaned schedules
 */

import { useState, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import {
    useSchedules,
    useCreateSchedule,
    useUpdateSchedule,
    useDeleteSchedule,
    useRunSchedule,
    useSyncSchedules,
    type ScheduleStatus,
} from "@/hooks/use-schedules";
import { useAgents } from "@/hooks/use-agents";
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
    Plus,
    Pencil,
    Trash2,
    X,
    MessageSquarePlus,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { formatRelativeTime } from "@/lib/constants";

// =============================================================================
// Cron Presets
// =============================================================================

const CRON_PRESETS = [
    { label: "Every hour", value: "0 * * * *" },
    { label: "Every 6 hours", value: "0 */6 * * *" },
    { label: "Daily at midnight", value: "0 0 * * *" },
    { label: "Daily at 9 AM", value: "0 9 * * *" },
    { label: "Weekly (Monday)", value: "0 0 * * MON" },
    { label: "Weekly (Sunday)", value: "0 0 * * SUN" },
    { label: "Monthly (1st)", value: "0 0 1 * *" },
    { label: "Custom", value: "custom" },
] as const;

// =============================================================================
// Helper Components
// =============================================================================

function ScheduleStatusBadge({ schedule }: { schedule: ScheduleStatus }) {
    if (!schedule.has_task) {
        return (
            <span className="flex items-center gap-1 px-2 py-0.5 text-xs rounded-full bg-red-500/10 text-red-500">
                <AlertCircle className="w-3 h-3" />
                Missing Task
            </span>
        );
    }

    if (!schedule.has_definition) {
        return (
            <span className="flex items-center gap-1 px-2 py-0.5 text-xs rounded-full bg-gray-500/10 text-gray-500">
                <AlertCircle className="w-3 h-3" />
                No Cron
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
    onEdit,
    onDelete,
    isToggling,
    isRunning,
}: {
    schedule: ScheduleStatus;
    onToggle: (taskName: string, enabled: boolean) => void;
    onRun: (taskName: string) => void;
    onEdit: (schedule: ScheduleStatus) => void;
    onDelete: (schedule: ScheduleStatus) => void;
    isToggling: boolean;
    isRunning: boolean;
}) {
    const canRun = schedule.has_task && schedule.has_db_record;
    const canToggle = schedule.has_db_record;

    return (
        <div className="border rounded-md p-4 space-y-3">
            {/* Header row */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <Calendar className="w-5 h-5 text-muted-foreground" />
                    <div>
                        <div className="flex items-center gap-2">
                            <span className="font-medium">{schedule.task_name}</span>
                            <ScheduleStatusBadge schedule={schedule} />
                            {schedule.additional_prompt && (
                                <span
                                    className="flex items-center gap-1 px-1.5 py-0.5 text-xs rounded-full bg-blue-500/10 text-blue-600"
                                    title={`Assignment: ${schedule.additional_prompt.slice(0, 100)}${schedule.additional_prompt.length > 100 ? "..." : ""}`}
                                >
                                    <MessageSquarePlus className="w-3 h-3" />
                                    Assignment
                                </span>
                            )}
                        </div>
                        {schedule.description && (
                            <p className="text-sm text-muted-foreground mt-0.5">
                                {schedule.description}
                            </p>
                        )}
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    {/* Edit Button */}
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onEdit(schedule)}
                        title="Edit schedule"
                    >
                        <Pencil className="w-4 h-4" />
                    </Button>

                    {/* Delete Button */}
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onDelete(schedule)}
                        className="text-destructive hover:text-destructive"
                        title="Delete schedule"
                    >
                        <Trash2 className="w-4 h-4" />
                    </Button>

                    {/* Enable/Disable Toggle */}
                    {canToggle && (
                        <Button
                            variant={schedule.enabled ? "outline" : "ghost"}
                            size="sm"
                            onClick={() => onToggle(schedule.task_name, !schedule.enabled)}
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
                            onClick={() => onRun(schedule.task_name)}
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
            {!schedule.has_task && schedule.has_db_record && (
                <div className="text-xs text-red-600 bg-red-500/10 px-2 py-1 rounded">
                    This schedule references an agent task that no longer exists.
                    Click "Clean Up" to remove orphaned schedules.
                </div>
            )}
        </div>
    );
}

// =============================================================================
// Schedule Form Dialog (for Create/Edit)
// =============================================================================

interface ScheduleFormDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    mode: "create" | "edit";
    schedule?: ScheduleStatus | null;
    availableTasks?: { name: string; display_name: string }[];
    existingScheduledTasks?: Set<string>;
}

function ScheduleFormDialog({
    open,
    onOpenChange,
    mode,
    schedule,
    availableTasks = [],
    existingScheduledTasks = new Set(),
}: ScheduleFormDialogProps) {
    const [taskName, setTaskName] = useState("");
    const [cronPreset, setCronPreset] = useState("");
    const [cronExpression, setCronExpression] = useState("");
    const [description, setDescription] = useState("");
    const [additionalPrompt, setAdditionalPrompt] = useState("");
    const [error, setError] = useState<string | null>(null);

    const createSchedule = useCreateSchedule();
    const updateSchedule = useUpdateSchedule();

    const isLoading = createSchedule.isPending || updateSchedule.isPending;

    // Filter out tasks that already have schedules (for create mode)
    const unscheduledTasks = availableTasks.filter(
        (task) => !existingScheduledTasks.has(task.name)
    );

    // Initialize form when opening
    useEffect(() => {
        if (open) {
            if (mode === "edit" && schedule) {
                const matchingPreset = CRON_PRESETS.find((p) => p.value === schedule.cron);
                setCronPreset(matchingPreset ? schedule.cron || "" : "custom");
                setCronExpression(schedule.cron || "");
                setDescription(schedule.description || "");
                setAdditionalPrompt(schedule.additional_prompt || "");
                setTaskName(schedule.task_name);
            } else {
                setCronPreset("");
                setCronExpression("");
                setDescription("");
                setAdditionalPrompt("");
                setTaskName("");
            }
            setError(null);
        }
    }, [open, mode, schedule]);

    const handlePresetChange = (value: string) => {
        setCronPreset(value);
        if (value !== "custom") {
            setCronExpression(value);
        }
    };

    const handleSubmit = async () => {
        if (mode === "create" && !taskName) {
            setError("Please select an agent task");
            return;
        }

        setError(null);
        try {
            if (mode === "create") {
                await createSchedule.mutateAsync({
                    task_name: taskName,
                    cron_expression: cronExpression || undefined,
                    description: description || undefined,
                    additional_prompt: additionalPrompt.trim() || undefined,
                });
            } else if (schedule) {
                await updateSchedule.mutateAsync({
                    taskName: schedule.task_name,
                    cron_expression: cronExpression || undefined,
                    description: description || undefined,
                    additional_prompt: additionalPrompt.trim() || "",
                });
            }
            onOpenChange(false);
        } catch (err) {
            setError(err instanceof Error ? err.message : `Failed to ${mode} schedule`);
        }
    };

    if (!open) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
            {/* Backdrop */}
            <div
                className="fixed inset-0 bg-black/50 backdrop-blur-sm"
                onClick={() => !isLoading && onOpenChange(false)}
            />

            {/* Dialog */}
            <div className="relative z-50 w-full max-w-md rounded-lg border bg-background p-6 shadow-lg animate-in fade-in-0 zoom-in-95">
                {/* Header */}
                <div className="flex items-center justify-between mb-4">
                    <div>
                        <h2 className="text-lg font-semibold">
                            {mode === "create" ? "Create Schedule" : "Edit Schedule"}
                        </h2>
                        <p className="text-sm text-muted-foreground">
                            {mode === "create"
                                ? "Create a new schedule to run an agent automatically."
                                : `Update the schedule for ${schedule?.task_name}`}
                        </p>
                    </div>
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onOpenChange(false)}
                        disabled={isLoading}
                        className="h-8 w-8 p-0"
                    >
                        <X className="h-4 w-4" />
                    </Button>
                </div>

                <div className="space-y-4">
                    {/* Task Picker (Create mode only) */}
                    {mode === "create" && (
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Agent Task</label>
                            <select
                                value={taskName}
                                onChange={(e) => setTaskName(e.target.value)}
                                className="w-full px-3 py-2 rounded-md border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                                disabled={isLoading}
                            >
                                <option value="">Select an agent task</option>
                                {unscheduledTasks.length === 0 ? (
                                    <option value="" disabled>
                                        All tasks already have schedules
                                    </option>
                                ) : (
                                    unscheduledTasks.map((task) => (
                                        <option key={task.name} value={task.name}>
                                            {task.display_name || task.name}
                                        </option>
                                    ))
                                )}
                            </select>
                        </div>
                    )}

                    {/* Cron Preset */}
                    <div className="space-y-2">
                        <label className="text-sm font-medium">Schedule Frequency</label>
                        <select
                            value={cronPreset}
                            onChange={(e) => handlePresetChange(e.target.value)}
                            className="w-full px-3 py-2 rounded-md border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                            disabled={isLoading}
                        >
                            <option value="">Select a schedule</option>
                            {CRON_PRESETS.map((preset) => (
                                <option key={preset.value} value={preset.value}>
                                    {preset.label}
                                </option>
                            ))}
                        </select>
                    </div>

                    {/* Custom Cron Expression */}
                    {cronPreset === "custom" && (
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Cron Expression</label>
                            <input
                                type="text"
                                value={cronExpression}
                                onChange={(e) => setCronExpression(e.target.value)}
                                placeholder="0 0 * * *"
                                className="w-full px-3 py-2 rounded-md border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                                disabled={isLoading}
                            />
                            <p className="text-xs text-muted-foreground">
                                Format: minute hour day-of-month month day-of-week
                            </p>
                        </div>
                    )}

                    {/* Description */}
                    <div className="space-y-2">
                        <label className="text-sm font-medium">
                            Description {mode === "create" && "(optional)"}
                        </label>
                        <input
                            type="text"
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                            placeholder="Run weekly documentation updates"
                            className="w-full px-3 py-2 rounded-md border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                            disabled={isLoading}
                        />
                    </div>

                    {/* Assignment (additional_prompt) */}
                    <div className="space-y-2">
                        <label className="text-sm font-medium flex items-center gap-1.5">
                            <MessageSquarePlus className="w-4 h-4" />
                            Assignment (optional)
                        </label>
                        <textarea
                            value={additionalPrompt}
                            onChange={(e) => setAdditionalPrompt(e.target.value)}
                            placeholder="Tell the agent what to focus on each run..."
                            rows={4}
                            maxLength={10000}
                            className="w-full px-3 py-2 rounded-md border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring resize-y"
                            disabled={isLoading}
                        />
                        <p className="text-xs text-muted-foreground">
                            Prepended to the task prompt as an assignment on every run.
                        </p>
                    </div>

                    {/* Error */}
                    {error && (
                        <div className="text-sm text-destructive bg-destructive/10 px-3 py-2 rounded">
                            {error}
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="flex justify-end gap-3 mt-6">
                    <Button
                        variant="outline"
                        onClick={() => onOpenChange(false)}
                        disabled={isLoading}
                    >
                        Cancel
                    </Button>
                    <Button
                        onClick={handleSubmit}
                        disabled={isLoading || (mode === "create" && !taskName)}
                    >
                        {isLoading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                        {mode === "create" ? "Create Schedule" : "Save Changes"}
                    </Button>
                </div>
            </div>
        </div>
    );
}

// =============================================================================
// Main Component
// =============================================================================

export default function Schedules() {
    const [runningTask, setRunningTask] = useState<string | null>(null);
    const [togglingTask, setTogglingTask] = useState<string | null>(null);
    const [formMode, setFormMode] = useState<"create" | "edit">("create");
    const [formOpen, setFormOpen] = useState(false);
    const [editingSchedule, setEditingSchedule] = useState<ScheduleStatus | null>(null);
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
    const [deletingSchedule, setDeletingSchedule] = useState<ScheduleStatus | null>(null);

    const { data, isLoading, isFetching, refetch } = useSchedules();
    const { data: agentsData } = useAgents();
    const updateSchedule = useUpdateSchedule();
    const deleteSchedule = useDeleteSchedule();
    const runSchedule = useRunSchedule();
    const syncSchedules = useSyncSchedules();

    const schedules = data?.schedules ?? [];
    const schedulerRunning = data?.scheduler_running ?? false;

    // Get available tasks for creating new schedules
    const availableTasks = agentsData?.tasks ?? [];
    const existingScheduledTasks = new Set(schedules.map((s) => s.task_name));

    const handleToggle = async (taskName: string, enabled: boolean) => {
        setTogglingTask(taskName);
        try {
            await updateSchedule.mutateAsync({ taskName, enabled });
        } finally {
            setTogglingTask(null);
        }
    };

    const handleRun = async (taskName: string) => {
        setRunningTask(taskName);
        try {
            await runSchedule.mutateAsync(taskName);
        } finally {
            setRunningTask(null);
        }
    };

    const handleSync = async () => {
        await syncSchedules.mutateAsync();
    };

    const handleCreate = () => {
        setFormMode("create");
        setEditingSchedule(null);
        setFormOpen(true);
    };

    const handleEdit = (schedule: ScheduleStatus) => {
        setFormMode("edit");
        setEditingSchedule(schedule);
        setFormOpen(true);
    };

    const handleDeleteClick = (schedule: ScheduleStatus) => {
        setDeletingSchedule(schedule);
        setDeleteDialogOpen(true);
    };

    const handleDeleteConfirm = async () => {
        if (!deletingSchedule) return;
        try {
            await deleteSchedule.mutateAsync(deletingSchedule.task_name);
            setDeleteDialogOpen(false);
            setDeletingSchedule(null);
        } catch {
            // Error handled by mutation
        }
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
                        variant="default"
                        size="sm"
                        onClick={handleCreate}
                    >
                        <Plus className="w-4 h-4 mr-1" />
                        Create Schedule
                    </Button>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={handleSync}
                        disabled={syncSchedules.isPending}
                        title="Remove schedules for agent tasks that no longer exist"
                    >
                        {syncSchedules.isPending ? (
                            <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                        ) : (
                            <RefreshCw className="w-4 h-4 mr-1" />
                        )}
                        Clean Up
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
                    Clean up complete: {syncSchedules.data.removed} orphaned{" "}
                    {syncSchedules.data.removed === 1 ? "schedule" : "schedules"} removed
                    ({syncSchedules.data.total} total remaining)
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
                        <p className="text-xs mt-1 mb-4">
                            Create a schedule to run agents automatically on a cron schedule.
                        </p>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={handleCreate}
                        >
                            <Plus className="w-4 h-4 mr-1" />
                            Create Schedule
                        </Button>
                    </CardContent>
                </Card>
            ) : (
                <div className="space-y-2">
                    {schedules.map((schedule) => (
                        <ScheduleRow
                            key={schedule.task_name}
                            schedule={schedule}
                            onToggle={handleToggle}
                            onRun={handleRun}
                            onEdit={handleEdit}
                            onDelete={handleDeleteClick}
                            isToggling={togglingTask === schedule.task_name}
                            isRunning={runningTask === schedule.task_name}
                        />
                    ))}
                </div>
            )}

            {/* Create/Edit Form Dialog */}
            <ScheduleFormDialog
                open={formOpen}
                onOpenChange={setFormOpen}
                mode={formMode}
                schedule={editingSchedule}
                availableTasks={availableTasks}
                existingScheduledTasks={existingScheduledTasks}
            />

            {/* Delete Confirmation Dialog */}
            <ConfirmDialog
                open={deleteDialogOpen}
                onOpenChange={(open) => {
                    setDeleteDialogOpen(open);
                    if (!open) setDeletingSchedule(null);
                }}
                title="Delete Schedule"
                description={`Are you sure you want to delete the schedule for "${deletingSchedule?.task_name}"? This action cannot be undone.`}
                confirmLabel="Delete"
                cancelLabel="Cancel"
                onConfirm={handleDeleteConfirm}
                isLoading={deleteSchedule.isPending}
                variant="destructive"
            />
        </div>
    );
}
