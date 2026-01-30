/**
 * Saved tasks component for managing reusable agent task templates.
 *
 * Features:
 * - List saved tasks with filtering
 * - Create new saved tasks
 * - Edit existing tasks
 * - Run saved tasks on-demand
 * - Delete tasks
 */

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
    useSavedTasks,
    useCreateSavedTask,
    useUpdateSavedTask,
    useDeleteSavedTask,
    useRunSavedTask,
    type SavedTask,
    type CreateSavedTaskRequest,
} from "@/hooks/use-saved-tasks";
import { useAgents } from "@/hooks/use-agents";
import {
    Play,
    Plus,
    Trash2,
    Edit2,
    Clock,
    Loader2,
    Bookmark,
    RefreshCw,
    X,
    Calendar,
    CheckCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { formatRelativeTime } from "@/lib/constants";

// =============================================================================
// Create/Edit Dialog
// =============================================================================

interface TaskFormProps {
    task?: SavedTask | null;
    agentNames: string[];
    onSave: (data: CreateSavedTaskRequest & { id?: string }) => void;
    onCancel: () => void;
    isSaving: boolean;
}

function TaskForm({ task, agentNames, onSave, onCancel, isSaving }: TaskFormProps) {
    const [name, setName] = useState(task?.name || "");
    const [description, setDescription] = useState(task?.description || "");
    const [agentName, setAgentName] = useState(task?.agent_name || agentNames[0] || "");
    const [taskText, setTaskText] = useState(task?.task || "");
    const [scheduleCron, setScheduleCron] = useState(task?.schedule_cron || "");

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        onSave({
            id: task?.id,
            name: name.trim(),
            agent_name: agentName,
            task: taskText.trim(),
            description: description.trim() || undefined,
            schedule_cron: scheduleCron.trim() || undefined,
        });
    };

    const isValid = name.trim() && agentName && taskText.trim();

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
            <div className="bg-background rounded-lg shadow-lg w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
                <div className="flex items-center justify-between p-4 border-b">
                    <h2 className="text-lg font-semibold">
                        {task ? "Edit Saved Task" : "Create Saved Task"}
                    </h2>
                    <button onClick={onCancel} className="p-1 rounded hover:bg-muted">
                        <X className="w-5 h-5" />
                    </button>
                </div>

                <form onSubmit={handleSubmit} className="p-4 space-y-4">
                    {/* Name */}
                    <div className="space-y-1">
                        <label className="text-sm font-medium">Name</label>
                        <input
                            type="text"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            placeholder="e.g., Weekly Documentation Update"
                            className="w-full px-3 py-2 text-sm rounded-md border bg-background focus:outline-none focus:ring-2 focus:ring-primary/50"
                        />
                    </div>

                    {/* Description */}
                    <div className="space-y-1">
                        <label className="text-sm font-medium">Description (optional)</label>
                        <input
                            type="text"
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                            placeholder="Brief description of what this task does"
                            className="w-full px-3 py-2 text-sm rounded-md border bg-background focus:outline-none focus:ring-2 focus:ring-primary/50"
                        />
                    </div>

                    {/* Agent */}
                    <div className="space-y-1">
                        <label className="text-sm font-medium">Agent</label>
                        <select
                            value={agentName}
                            onChange={(e) => setAgentName(e.target.value)}
                            className="w-full px-3 py-2 text-sm rounded-md border bg-background focus:outline-none focus:ring-2 focus:ring-primary/50"
                            disabled={!!task}
                        >
                            {agentNames.map((name) => (
                                <option key={name} value={name}>
                                    {name}
                                </option>
                            ))}
                        </select>
                        {task && (
                            <p className="text-xs text-muted-foreground">
                                Agent cannot be changed after creation
                            </p>
                        )}
                    </div>

                    {/* Task */}
                    <div className="space-y-1">
                        <label className="text-sm font-medium">Task</label>
                        <textarea
                            value={taskText}
                            onChange={(e) => setTaskText(e.target.value)}
                            placeholder="Describe what the agent should do..."
                            rows={4}
                            className="w-full px-3 py-2 text-sm rounded-md border bg-background focus:outline-none focus:ring-2 focus:ring-primary/50 resize-none"
                        />
                    </div>

                    {/* Schedule (cron) */}
                    <div className="space-y-1">
                        <label className="text-sm font-medium">Schedule (optional)</label>
                        <input
                            type="text"
                            value={scheduleCron}
                            onChange={(e) => setScheduleCron(e.target.value)}
                            placeholder="e.g., 0 9 * * 1 (Monday at 9am)"
                            className="w-full px-3 py-2 text-sm rounded-md border bg-background focus:outline-none focus:ring-2 focus:ring-primary/50"
                        />
                        <p className="text-xs text-muted-foreground">
                            Cron expression for automatic scheduling (coming soon)
                        </p>
                    </div>

                    {/* Actions */}
                    <div className="flex justify-end gap-2 pt-2">
                        <Button type="button" variant="outline" onClick={onCancel}>
                            Cancel
                        </Button>
                        <Button type="submit" disabled={!isValid || isSaving}>
                            {isSaving ? (
                                <Loader2 className="w-4 h-4 animate-spin mr-1" />
                            ) : (
                                <CheckCircle className="w-4 h-4 mr-1" />
                            )}
                            {task ? "Save Changes" : "Create Task"}
                        </Button>
                    </div>
                </form>
            </div>
        </div>
    );
}

// =============================================================================
// Task Row Component
// =============================================================================

interface TaskRowProps {
    task: SavedTask;
    onRun: (taskId: string) => void;
    onEdit: (task: SavedTask) => void;
    onDelete: (taskId: string) => void;
    isRunning: boolean;
    isDeleting: boolean;
}

function TaskRow({ task, onRun, onEdit, onDelete, isRunning, isDeleting }: TaskRowProps) {
    const [showConfirmDelete, setShowConfirmDelete] = useState(false);

    return (
        <div className="border rounded-md overflow-hidden">
            <div className="flex items-center gap-3 p-3 hover:bg-accent/5">
                <div className="p-2 rounded-md bg-primary/10">
                    <Bookmark className="w-4 h-4 text-primary" />
                </div>

                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                        <span className="font-medium text-sm">{task.name}</span>
                        <span className="px-2 py-0.5 text-xs rounded-full bg-muted text-muted-foreground">
                            {task.agent_name}
                        </span>
                        {task.schedule_cron && (
                            <span
                                className={cn(
                                    "px-2 py-0.5 text-xs rounded-full flex items-center gap-1",
                                    task.schedule_enabled
                                        ? "bg-green-500/10 text-green-600"
                                        : "bg-muted text-muted-foreground"
                                )}
                            >
                                <Calendar className="w-3 h-3" />
                                {task.schedule_enabled ? "Scheduled" : "Disabled"}
                            </span>
                        )}
                    </div>
                    <p className="text-xs text-muted-foreground truncate mt-0.5">{task.task}</p>
                    {task.description && (
                        <p className="text-xs text-muted-foreground/70 mt-0.5">{task.description}</p>
                    )}
                </div>

                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    {task.total_runs > 0 && (
                        <span className="flex items-center gap-1">
                            <RefreshCw className="w-3 h-3" />
                            {task.total_runs} runs
                        </span>
                    )}
                    {task.last_run_at && (
                        <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {formatRelativeTime(task.last_run_at)}
                        </span>
                    )}
                </div>

                <div className="flex items-center gap-1">
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onRun(task.id)}
                        disabled={isRunning}
                        className="h-8 px-2"
                        title="Run this task now"
                    >
                        {isRunning ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                            <Play className="w-4 h-4" />
                        )}
                    </Button>
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onEdit(task)}
                        className="h-8 px-2"
                        title="Edit task"
                    >
                        <Edit2 className="w-4 h-4" />
                    </Button>
                    {showConfirmDelete ? (
                        <div className="flex items-center gap-1">
                            <Button
                                variant="destructive"
                                size="sm"
                                onClick={() => {
                                    onDelete(task.id);
                                    setShowConfirmDelete(false);
                                }}
                                disabled={isDeleting}
                                className="h-8 px-2"
                            >
                                {isDeleting ? (
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                ) : (
                                    "Delete"
                                )}
                            </Button>
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setShowConfirmDelete(false)}
                                className="h-8 px-2"
                            >
                                <X className="w-4 h-4" />
                            </Button>
                        </div>
                    ) : (
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setShowConfirmDelete(true)}
                            className="h-8 px-2 text-destructive hover:text-destructive"
                            title="Delete task"
                        >
                            <Trash2 className="w-4 h-4" />
                        </Button>
                    )}
                </div>
            </div>
        </div>
    );
}

// =============================================================================
// Main Component
// =============================================================================

export default function SavedTasks() {
    const { data: tasksData, isLoading } = useSavedTasks();
    const { data: agentsData } = useAgents();
    const createTask = useCreateSavedTask();
    const updateTask = useUpdateSavedTask();
    const deleteTask = useDeleteSavedTask();
    const runTask = useRunSavedTask();

    const [showForm, setShowForm] = useState(false);
    const [editingTask, setEditingTask] = useState<SavedTask | null>(null);
    const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

    const tasks = tasksData?.tasks || [];
    const agentNames = agentsData?.agents?.map((a) => a.name) || [];

    const handleCreate = () => {
        setEditingTask(null);
        setShowForm(true);
    };

    const handleEdit = (task: SavedTask) => {
        setEditingTask(task);
        setShowForm(true);
    };

    const handleSave = async (data: CreateSavedTaskRequest & { id?: string }) => {
        setMessage(null);
        try {
            if (data.id) {
                await updateTask.mutateAsync({
                    taskId: data.id,
                    name: data.name,
                    description: data.description,
                    task: data.task,
                    schedule_cron: data.schedule_cron,
                });
                setMessage({ type: "success", text: "Task updated" });
            } else {
                await createTask.mutateAsync(data);
                setMessage({ type: "success", text: "Task created" });
            }
            setShowForm(false);
            setEditingTask(null);
        } catch (error) {
            setMessage({
                type: "error",
                text: error instanceof Error ? error.message : "Failed to save task",
            });
        }
    };

    const handleDelete = async (taskId: string) => {
        setMessage(null);
        try {
            await deleteTask.mutateAsync(taskId);
            setMessage({ type: "success", text: "Task deleted" });
        } catch (error) {
            setMessage({
                type: "error",
                text: error instanceof Error ? error.message : "Failed to delete task",
            });
        }
    };

    const handleRun = async (taskId: string) => {
        setMessage(null);
        try {
            const result = await runTask.mutateAsync(taskId);
            setMessage({ type: "success", text: result.message });
        } catch (error) {
            setMessage({
                type: "error",
                text: error instanceof Error ? error.message : "Failed to run task",
            });
        }
    };

    return (
        <div className="space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                    Save frequently used tasks for quick re-use
                </p>
                <Button size="sm" onClick={handleCreate} disabled={agentNames.length === 0}>
                    <Plus className="w-4 h-4 mr-1" />
                    New Task
                </Button>
            </div>

            {/* Messages */}
            {message && (
                <Alert variant={message.type === "error" ? "destructive" : "default"}>
                    <AlertDescription>{message.text}</AlertDescription>
                </Alert>
            )}

            {/* Task list */}
            {isLoading ? (
                <div className="space-y-2">
                    {[1, 2, 3].map((i) => (
                        <div key={i} className="border rounded-md p-3 animate-pulse">
                            <div className="flex items-center gap-3">
                                <div className="w-8 h-8 bg-muted rounded-md" />
                                <div className="flex-1">
                                    <div className="h-4 bg-muted rounded w-1/4 mb-2" />
                                    <div className="h-3 bg-muted rounded w-3/4" />
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            ) : tasks.length === 0 ? (
                <Card>
                    <CardContent className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                        <Bookmark className="w-12 h-12 mb-4 opacity-30" />
                        <p className="text-sm">No saved tasks yet</p>
                        <p className="text-xs mt-1">
                            Create a saved task to quickly re-run common agent operations
                        </p>
                        {agentNames.length > 0 && (
                            <Button size="sm" className="mt-4" onClick={handleCreate}>
                                <Plus className="w-4 h-4 mr-1" />
                                Create Your First Task
                            </Button>
                        )}
                    </CardContent>
                </Card>
            ) : (
                <div className="space-y-2">
                    {tasks.map((task) => (
                        <TaskRow
                            key={task.id}
                            task={task}
                            onRun={handleRun}
                            onEdit={handleEdit}
                            onDelete={handleDelete}
                            isRunning={runTask.isPending}
                            isDeleting={deleteTask.isPending}
                        />
                    ))}
                </div>
            )}

            {/* Create/Edit Form */}
            {showForm && (
                <TaskForm
                    task={editingTask}
                    agentNames={agentNames}
                    onSave={handleSave}
                    onCancel={() => {
                        setShowForm(false);
                        setEditingTask(null);
                    }}
                    isSaving={createTask.isPending || updateTask.isPending}
                />
            )}
        </div>
    );
}
