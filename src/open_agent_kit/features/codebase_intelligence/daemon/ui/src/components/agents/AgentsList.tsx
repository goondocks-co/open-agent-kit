/**
 * Agent list component showing instances and templates.
 *
 * UI Flow:
 * - Instances section: Shows runnable instances with Run button (no task input)
 * - Templates section: Shows available templates with Create Instance button
 *
 * Architecture:
 * - Templates define capabilities (tools, permissions, system prompt)
 * - Instances define tasks (default_task, maintained_files, ci_queries)
 * - Only instances can be run directly - templates create instances
 */

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Label } from "@/components/ui/label";
import {
    useAgents,
    useRunInstance,
    useCreateInstance,
    useReloadAgents,
    type AgentTemplate,
    type AgentInstance,
} from "@/hooks/use-agents";
import {
    Bot,
    Play,
    Clock,
    RefreshCw,
    Loader2,
    ChevronDown,
    ChevronUp,
    Timer,
    Plus,
    FileCode,
    Layers,
    X,
    Settings2,
} from "lucide-react";
import { FALLBACK_MESSAGES } from "@/lib/constants";

// =============================================================================
// Instance Card Component
// =============================================================================

function InstanceCard({
    instance,
    onRun,
    isRunning,
    instancesDir,
}: {
    instance: AgentInstance;
    onRun: (instanceName: string) => void;
    isRunning: boolean;
    instancesDir: string;
}) {
    const [expanded, setExpanded] = useState(false);

    return (
        <Card>
            <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                        <div className="p-2 rounded-md bg-green-500/10">
                            <Bot className="w-5 h-5 text-green-600" />
                        </div>
                        <div>
                            <CardTitle className="text-lg">{instance.display_name}</CardTitle>
                            <CardDescription className="mt-1">
                                {instance.description || `Based on: ${instance.agent_type}`}
                            </CardDescription>
                        </div>
                    </div>
                    <button
                        onClick={() => setExpanded(!expanded)}
                        className="p-1 rounded hover:bg-muted transition-colors"
                        title={expanded ? "Collapse" : "Show details"}
                    >
                        {expanded ? (
                            <ChevronUp className="w-4 h-4 text-muted-foreground" />
                        ) : (
                            <ChevronDown className="w-4 h-4 text-muted-foreground" />
                        )}
                    </button>
                </div>
            </CardHeader>

            {expanded && (
                <CardContent className="pt-0 pb-3 space-y-4">
                    {/* Execution limits */}
                    <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1">
                            <Timer className="w-3 h-3" />
                            Max {instance.max_turns} turns
                        </span>
                        <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {Math.floor(instance.timeout_seconds / 60)}m timeout
                        </span>
                        <span className="flex items-center gap-1">
                            <Layers className="w-3 h-3" />
                            Template: {instance.agent_type}
                        </span>
                        {instance.has_execution_override && (
                            <span className="flex items-center gap-1 text-amber-600" title="Instance has custom execution limits (overrides template defaults)">
                                <Settings2 className="w-3 h-3" />
                                Custom limits
                            </span>
                        )}
                    </div>

                    {/* Default task preview */}
                    <div className="space-y-2">
                        <div className="text-xs font-medium">Configured Task:</div>
                        <pre className="p-3 rounded-md bg-muted/50 text-xs overflow-x-auto max-h-32 overflow-y-auto whitespace-pre-wrap">
                            {instance.default_task}
                        </pre>
                    </div>

                    <p className="text-xs text-muted-foreground flex items-center gap-1">
                        <FileCode className="w-3 h-3" />
                        Edit: <code className="bg-muted px-1.5 py-0.5 rounded">{instancesDir}/{instance.name}.yaml</code>
                    </p>
                </CardContent>
            )}

            <CardFooter className="pt-0">
                <Button
                    onClick={() => onRun(instance.name)}
                    disabled={isRunning}
                    className="w-full"
                    title="Run this instance with its configured task"
                >
                    {isRunning ? (
                        <Loader2 className="w-4 h-4 animate-spin mr-2" />
                    ) : (
                        <Play className="w-4 h-4 mr-2" />
                    )}
                    Run
                </Button>
            </CardFooter>
        </Card>
    );
}

// =============================================================================
// Template Card Component
// =============================================================================

function TemplateCard({
    template,
    onCreateInstance,
}: {
    template: AgentTemplate;
    onCreateInstance: (templateName: string) => void;
}) {
    const [expanded, setExpanded] = useState(false);

    return (
        <Card className="border-dashed">
            <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                        <div className="p-2 rounded-md bg-muted">
                            <Layers className="w-5 h-5 text-muted-foreground" />
                        </div>
                        <div>
                            <CardTitle className="text-lg text-muted-foreground">{template.display_name}</CardTitle>
                            <CardDescription className="mt-1">{template.description}</CardDescription>
                        </div>
                    </div>
                    <button
                        onClick={() => setExpanded(!expanded)}
                        className="p-1 rounded hover:bg-muted transition-colors"
                        title={expanded ? "Collapse" : "Show details"}
                    >
                        {expanded ? (
                            <ChevronUp className="w-4 h-4 text-muted-foreground" />
                        ) : (
                            <ChevronDown className="w-4 h-4 text-muted-foreground" />
                        )}
                    </button>
                </div>
            </CardHeader>

            {expanded && (
                <CardContent className="pt-0 pb-3">
                    <div className="flex gap-4 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1">
                            <Timer className="w-3 h-3" />
                            Max {template.max_turns} turns
                        </span>
                        <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {Math.floor(template.timeout_seconds / 60)}m timeout
                        </span>
                    </div>
                </CardContent>
            )}

            <CardFooter className="pt-0">
                <Button
                    variant="outline"
                    onClick={() => onCreateInstance(template.name)}
                    className="w-full"
                    title="Create a new instance from this template"
                >
                    <Plus className="w-4 h-4 mr-2" />
                    Create Instance
                </Button>
            </CardFooter>
        </Card>
    );
}

// =============================================================================
// Create Instance Modal
// =============================================================================

function CreateInstanceModal({
    open,
    onOpenChange,
    templateName,
    onSubmit,
    isPending,
    instancesDir,
}: {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    templateName: string;
    onSubmit: (data: { name: string; display_name: string; description: string; default_task: string }) => void;
    isPending: boolean;
    instancesDir: string;
}) {
    const [name, setName] = useState("");
    const [displayName, setDisplayName] = useState("");
    const [description, setDescription] = useState("");
    const [defaultTask, setDefaultTask] = useState("");

    const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        onSubmit({
            name: name.toLowerCase().replace(/\s+/g, "-"),
            display_name: displayName,
            description,
            default_task: defaultTask,
        });
    };

    const isValid = name.trim() && displayName.trim() && defaultTask.trim();

    if (!open) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
            {/* Backdrop */}
            <div
                className="fixed inset-0 bg-black/50 backdrop-blur-sm"
                onClick={() => !isPending && onOpenChange(false)}
            />

            {/* Dialog */}
            <div className="relative z-50 w-full max-w-md rounded-lg border bg-background p-6 shadow-lg animate-in fade-in-0 zoom-in-95">
                {/* Close button */}
                <button
                    onClick={() => onOpenChange(false)}
                    className="absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none"
                    disabled={isPending}
                >
                    <X className="h-4 w-4" />
                    <span className="sr-only">Close</span>
                </button>

                {/* Header */}
                <div className="mb-4">
                    <h2 className="text-lg font-semibold">Create Instance from "{templateName}"</h2>
                    <p className="mt-1 text-sm text-muted-foreground">
                        Create a new agent instance with a specific task. The instance will be saved
                        to <code className="bg-muted px-1 rounded">{instancesDir}/</code> and can be customized later.
                    </p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div className="space-y-2">
                        <Label htmlFor="name">Instance Name</Label>
                        <input
                            id="name"
                            type="text"
                            value={name}
                            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setName(e.target.value)}
                            placeholder="my-docs-agent"
                            pattern="[a-z0-9][a-z0-9-]*[a-z0-9]|[a-z0-9]"
                            required
                            className="w-full px-3 py-2 text-sm rounded-md border bg-background focus:outline-none focus:ring-2 focus:ring-primary/50"
                        />
                        <p className="text-xs text-muted-foreground">
                            Lowercase letters, numbers, and hyphens only. Becomes the filename.
                        </p>
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="displayName">Display Name</Label>
                        <input
                            id="displayName"
                            type="text"
                            value={displayName}
                            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setDisplayName(e.target.value)}
                            placeholder="My Documentation Agent"
                            required
                            className="w-full px-3 py-2 text-sm rounded-md border bg-background focus:outline-none focus:ring-2 focus:ring-primary/50"
                        />
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="description">Description (optional)</Label>
                        <input
                            id="description"
                            type="text"
                            value={description}
                            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setDescription(e.target.value)}
                            placeholder="Updates API documentation for the backend service"
                            className="w-full px-3 py-2 text-sm rounded-md border bg-background focus:outline-none focus:ring-2 focus:ring-primary/50"
                        />
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="defaultTask">Default Task</Label>
                        <textarea
                            id="defaultTask"
                            value={defaultTask}
                            onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setDefaultTask(e.target.value)}
                            placeholder="Review the codebase and update docs/api/*.md with current API endpoints..."
                            rows={4}
                            required
                            className="w-full px-3 py-2 text-sm rounded-md border bg-background focus:outline-none focus:ring-2 focus:ring-primary/50 resize-none"
                        />
                        <p className="text-xs text-muted-foreground">
                            This task will be executed when you click Run. Be specific about what you want done.
                        </p>
                    </div>

                    <div className="flex justify-end gap-3 pt-2">
                        <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={isPending}>
                            Cancel
                        </Button>
                        <Button type="submit" disabled={!isValid || isPending}>
                            {isPending ? (
                                <Loader2 className="w-4 h-4 animate-spin mr-2" />
                            ) : (
                                <Plus className="w-4 h-4 mr-2" />
                            )}
                            Create Instance
                        </Button>
                    </div>
                </form>
            </div>
        </div>
    );
}

// =============================================================================
// Main Component
// =============================================================================

export default function AgentsList() {
    const { data: agentsData, isLoading, isError } = useAgents();
    const runInstance = useRunInstance();
    const createInstance = useCreateInstance();
    const reloadAgents = useReloadAgents();

    const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
    const [createModalOpen, setCreateModalOpen] = useState(false);
    const [selectedTemplate, setSelectedTemplate] = useState<string>("");

    const templates = agentsData?.templates || [];
    const instances = agentsData?.instances || [];
    const instancesDir = agentsData?.instances_dir || "oak/ci/agents";

    const handleRunInstance = async (instanceName: string) => {
        setMessage(null);
        try {
            const result = await runInstance.mutateAsync(instanceName);
            setMessage({ type: "success", text: result.message });
        } catch (error) {
            setMessage({
                type: "error",
                text: error instanceof Error ? error.message : "Failed to start instance",
            });
        }
    };

    const handleCreateInstance = (templateName: string) => {
        setSelectedTemplate(templateName);
        setCreateModalOpen(true);
    };

    const handleCreateInstanceSubmit = async (data: { name: string; display_name: string; description: string; default_task: string }) => {
        setMessage(null);
        try {
            const result = await createInstance.mutateAsync({
                templateName: selectedTemplate,
                ...data,
            });
            setMessage({ type: "success", text: result.message });
            setCreateModalOpen(false);
        } catch (error) {
            setMessage({
                type: "error",
                text: error instanceof Error ? error.message : "Failed to create instance",
            });
        }
    };

    const handleReload = async () => {
        try {
            const result = await reloadAgents.mutateAsync();
            setMessage({ type: "success", text: result.message });
        } catch (error) {
            setMessage({
                type: "error",
                text: error instanceof Error ? error.message : "Failed to reload agents",
            });
        }
    };

    return (
        <div className="space-y-6">
            {/* Actions bar */}
            <div className="flex justify-end">
                <Button
                    variant="outline"
                    size="sm"
                    onClick={handleReload}
                    disabled={reloadAgents.isPending}
                >
                    {reloadAgents.isPending ? (
                        <Loader2 className="w-4 h-4 animate-spin mr-1" />
                    ) : (
                        <RefreshCw className="w-4 h-4 mr-1" />
                    )}
                    Reload Agents
                </Button>
            </div>

            {/* Messages */}
            {message && (
                <Alert variant={message.type === "error" ? "destructive" : "default"}>
                    <AlertDescription>{message.text}</AlertDescription>
                </Alert>
            )}

            {/* Error state */}
            {isError && (
                <div className="p-4 rounded-md bg-destructive/10 text-destructive border border-destructive/20">
                    Failed to load agents. Make sure the daemon is running and agents are enabled in config.
                </div>
            )}

            {/* Loading state */}
            {isLoading ? (
                <div className="flex items-center justify-center h-32 text-muted-foreground">
                    <Loader2 className="w-5 h-5 animate-spin mr-2" />
                    {FALLBACK_MESSAGES.LOADING}
                </div>
            ) : (
                <>
                    {/* Instances Section */}
                    <section className="space-y-4">
                        <div className="flex items-center gap-2">
                            <Bot className="w-5 h-5 text-green-600" />
                            <h2 className="text-lg font-semibold">Agent Instances</h2>
                            <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded">
                                {instancesDir}/
                            </span>
                        </div>

                        {instances.length === 0 ? (
                            <Card className="border-dashed">
                                <CardContent className="flex flex-col items-center justify-center py-8 text-muted-foreground">
                                    <Bot className="w-10 h-10 mb-3 opacity-30" />
                                    <p className="text-sm font-medium">No instances configured</p>
                                    <p className="text-xs mt-1">
                                        Create an instance from a template below to get started
                                    </p>
                                </CardContent>
                            </Card>
                        ) : (
                            <div className="grid gap-4 md:grid-cols-2">
                                {instances.map((instance) => (
                                    <InstanceCard
                                        key={instance.name}
                                        instance={instance}
                                        onRun={handleRunInstance}
                                        isRunning={runInstance.isPending}
                                        instancesDir={instancesDir}
                                    />
                                ))}
                            </div>
                        )}
                    </section>

                    {/* Divider */}
                    <hr className="border-dashed" />

                    {/* Templates Section */}
                    <section className="space-y-4">
                        <div className="flex items-center gap-2">
                            <Layers className="w-5 h-5 text-muted-foreground" />
                            <h2 className="text-lg font-semibold text-muted-foreground">Available Templates</h2>
                        </div>

                        {templates.length === 0 ? (
                            <Card>
                                <CardContent className="flex flex-col items-center justify-center py-8 text-muted-foreground">
                                    <Layers className="w-10 h-10 mb-3 opacity-30" />
                                    <p className="text-sm">No templates available</p>
                                    <p className="text-xs mt-1">
                                        Add agent definitions to agents/definitions/
                                    </p>
                                </CardContent>
                            </Card>
                        ) : (
                            <div className="grid gap-4 md:grid-cols-2">
                                {templates.map((template) => (
                                    <TemplateCard
                                        key={template.name}
                                        template={template}
                                        onCreateInstance={handleCreateInstance}
                                    />
                                ))}
                            </div>
                        )}
                    </section>
                </>
            )}

            {/* Create Instance Modal */}
            <CreateInstanceModal
                open={createModalOpen}
                onOpenChange={setCreateModalOpen}
                templateName={selectedTemplate}
                onSubmit={handleCreateInstanceSubmit}
                isPending={createInstance.isPending}
                instancesDir={instancesDir}
            />
        </div>
    );
}
