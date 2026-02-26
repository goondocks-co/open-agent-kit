/**
 * Team Policy page — data collection policy toggles.
 *
 * Grouped into sections: Local Collection, Team Sync, and Server Processing.
 * Each toggle has a description explaining what it controls.
 */

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
    useTeamPolicy,
    useUpdateTeamPolicy,
    type PolicyUpdate,
} from "@/hooks/use-team";
import {
    Shield,
    Save,
    Loader2,
    AlertCircle,
    Database,
    RefreshCw,
    Server,
} from "lucide-react";
import { cn } from "@/lib/utils";

// =============================================================================
// Policy Toggle Definitions
// =============================================================================

interface PolicyToggle {
    key: keyof PolicyUpdate;
    label: string;
    description: string;
}

const LOCAL_COLLECTION_TOGGLES: PolicyToggle[] = [
    {
        key: "collect_activities",
        label: "Collect activities",
        description: "Record file changes, tool calls, and other activities from coding sessions.",
    },
    {
        key: "collect_prompts",
        label: "Collect prompts",
        description: "Record user prompts and agent responses during sessions.",
    },
];

const TEAM_SYNC_TOGGLES: PolicyToggle[] = [
    {
        key: "sync_observations",
        label: "Sync observations",
        description: "Share session summaries and observations with the team server.",
    },
    {
        key: "sync_activities",
        label: "Sync activities",
        description: "Share detailed activity data (file changes, tool calls) with the team server.",
    },
    {
        key: "sync_prompts",
        label: "Sync prompts",
        description: "Share user prompts and agent responses with the team server.",
    },
];

const SERVER_PROCESSING_TOGGLES: PolicyToggle[] = [
    {
        key: "allow_server_llm",
        label: "Allow server LLM processing",
        description: "Allow the team server to process your data with its own LLM for summarization and analysis.",
    },
];

// =============================================================================
// Components
// =============================================================================

function PolicySection({
    title,
    description,
    icon: Icon,
    toggles,
    values,
    onChange,
    disabled,
}: {
    title: string;
    description: string;
    icon: React.ComponentType<{ className?: string }>;
    toggles: PolicyToggle[];
    values: Record<string, boolean>;
    onChange: (key: string, value: boolean) => void;
    disabled: boolean;
}) {
    return (
        <div className="space-y-3">
            <div className="flex items-center gap-2">
                <Icon className="w-4 h-4 text-muted-foreground" />
                <div>
                    <h3 className="text-sm font-medium">{title}</h3>
                    <p className="text-xs text-muted-foreground">{description}</p>
                </div>
            </div>
            <div className="space-y-3 pl-6">
                {toggles.map((toggle) => (
                    <div key={toggle.key} className="flex items-start gap-3">
                        <input
                            type="checkbox"
                            id={`policy_${toggle.key}`}
                            checked={values[toggle.key] ?? false}
                            onChange={(e) => onChange(toggle.key, e.target.checked)}
                            disabled={disabled}
                            className="h-4 w-4 mt-0.5 rounded border-gray-300 text-primary focus:ring-primary"
                        />
                        <label htmlFor={`policy_${toggle.key}`} className="flex-1">
                            <span className="text-sm font-medium">{toggle.label}</span>
                            <p className="text-xs text-muted-foreground mt-0.5">
                                {toggle.description}
                            </p>
                        </label>
                    </div>
                ))}
            </div>
        </div>
    );
}

// =============================================================================
// Main Component
// =============================================================================

export default function TeamPolicy() {
    const { data: policy, isLoading } = useTeamPolicy();
    const updatePolicy = useUpdateTeamPolicy();

    const [form, setForm] = useState<Record<string, boolean>>({});
    const [isDirty, setIsDirty] = useState(false);
    const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

    // Sync form with server data on load
    useEffect(() => {
        if (policy && !isDirty) {
            setForm({
                collect_activities: policy.collect_activities,
                collect_prompts: policy.collect_prompts,
                sync_observations: policy.sync_observations,
                sync_activities: policy.sync_activities,
                sync_prompts: policy.sync_prompts,
                allow_server_llm: policy.allow_server_llm,
            });
        }
    }, [policy, isDirty]);

    const handleChange = (key: string, value: boolean) => {
        setForm((prev) => ({ ...prev, [key]: value }));
        setIsDirty(true);
        setMessage(null);
    };

    const handleSave = async () => {
        setMessage(null);
        try {
            await updatePolicy.mutateAsync(form as PolicyUpdate);
            setMessage({ type: "success", text: "Policy settings saved." });
            setIsDirty(false);
        } catch (err) {
            const text = err instanceof Error ? err.message : "Failed to save policy.";
            setMessage({ type: "error", text });
        }
    };

    if (isLoading) {
        return (
            <div className="border rounded-lg p-6 animate-pulse">
                <div className="h-5 bg-muted rounded w-1/3 mb-3" />
                <div className="space-y-4">
                    {[1, 2, 3, 4, 5, 6].map((i) => (
                        <div key={i} className="flex items-center gap-3">
                            <div className="w-4 h-4 bg-muted rounded" />
                            <div className="h-4 bg-muted rounded flex-1" />
                        </div>
                    ))}
                </div>
            </div>
        );
    }

    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    <Shield className="h-5 w-5" />
                    Data Collection Policy
                </CardTitle>
                <CardDescription>
                    Control what data is collected locally and shared with the team server.
                    These settings apply to this machine only.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
                {message && (
                    <div className={cn(
                        "p-3 rounded-md text-sm flex items-center gap-2",
                        message.type === "success" ? "bg-green-500/10 text-green-600" : "bg-red-500/10 text-red-600"
                    )}>
                        {message.type === "error" && <AlertCircle className="h-4 w-4" />}
                        {message.text}
                    </div>
                )}

                <PolicySection
                    title="Local Collection"
                    description="What data is recorded on this machine."
                    icon={Database}
                    toggles={LOCAL_COLLECTION_TOGGLES}
                    values={form}
                    onChange={handleChange}
                    disabled={updatePolicy.isPending}
                />

                <div className="border-t" />

                <PolicySection
                    title="Team Sync"
                    description="What data is synchronized with the team server."
                    icon={RefreshCw}
                    toggles={TEAM_SYNC_TOGGLES}
                    values={form}
                    onChange={handleChange}
                    disabled={updatePolicy.isPending}
                />

                <div className="border-t" />

                <PolicySection
                    title="Server Processing"
                    description="What the team server is allowed to do with your data."
                    icon={Server}
                    toggles={SERVER_PROCESSING_TOGGLES}
                    values={form}
                    onChange={handleChange}
                    disabled={updatePolicy.isPending}
                />
            </CardContent>
            <CardFooter className="bg-muted/30 py-3 border-t flex items-center justify-between">
                <p className="text-xs text-muted-foreground">
                    Policy changes take effect immediately after save.
                </p>
                <Button
                    onClick={handleSave}
                    disabled={!isDirty || updatePolicy.isPending}
                    size="sm"
                >
                    {updatePolicy.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    <Save className="mr-2 h-4 w-4" /> Save
                </Button>
            </CardFooter>
        </Card>
    );
}
