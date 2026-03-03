/**
 * Team Sync Policy — controls what data is synchronized with the team.
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
    RefreshCw,
    Save,
    Loader2,
    AlertCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";

export default function TeamPolicy() {
    const { data: policy, isLoading } = useTeamPolicy();
    const updatePolicy = useUpdateTeamPolicy();

    const [syncObservations, setSyncObservations] = useState(true);
    const [federatedTools, setFederatedTools] = useState(true);
    const [isDirty, setIsDirty] = useState(false);
    const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

    useEffect(() => {
        if (policy && !isDirty) {
            setSyncObservations(policy.sync_observations);
            setFederatedTools(policy.federated_tools);
        }
    }, [policy, isDirty]);

    const handleSyncObsChange = (value: boolean) => {
        setSyncObservations(value);
        setIsDirty(true);
        setMessage(null);
    };

    const handleFederatedToolsChange = (value: boolean) => {
        setFederatedTools(value);
        setIsDirty(true);
        setMessage(null);
    };

    const handleSave = async () => {
        setMessage(null);
        try {
            await updatePolicy.mutateAsync({
                sync_observations: syncObservations,
                federated_tools: federatedTools,
            } as PolicyUpdate);
            setMessage({ type: "success", text: "Sync policy saved." });
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
                <div className="flex items-center gap-3">
                    <div className="w-4 h-4 bg-muted rounded" />
                    <div className="h-4 bg-muted rounded flex-1" />
                </div>
            </div>
        );
    }

    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    <RefreshCw className="h-5 w-5" />
                    Sync Policy
                </CardTitle>
                <CardDescription>
                    Control what data is synchronized with the team via the cloud relay.
                </CardDescription>
            </CardHeader>
            <CardContent>
                {message && (
                    <div className={cn(
                        "p-3 rounded-md text-sm flex items-center gap-2 mb-4",
                        message.type === "success" ? "bg-green-500/10 text-green-600" : "bg-red-500/10 text-red-600"
                    )}>
                        {message.type === "error" && <AlertCircle className="h-4 w-4" />}
                        {message.text}
                    </div>
                )}

                <div className="space-y-4">
                    <div className="flex items-start gap-3">
                        <input
                            type="checkbox"
                            id="policy_sync_observations"
                            checked={syncObservations}
                            onChange={(e) => handleSyncObsChange(e.target.checked)}
                            disabled={updatePolicy.isPending}
                            className="h-4 w-4 mt-0.5 rounded border-gray-300 text-primary focus:ring-primary"
                        />
                        <label htmlFor="policy_sync_observations" className="flex-1">
                            <span className="text-sm font-medium">Sync observations</span>
                            <p className="text-xs text-muted-foreground mt-0.5">
                                Share codebase observations and plans with the team. Includes activity-based and agent-based observations.
                            </p>
                        </label>
                    </div>
                    <div className="flex items-start gap-3">
                        <input
                            type="checkbox"
                            id="policy_federated_tools"
                            checked={federatedTools}
                            onChange={(e) => handleFederatedToolsChange(e.target.checked)}
                            disabled={updatePolicy.isPending}
                            className="h-4 w-4 mt-0.5 rounded border-gray-300 text-primary focus:ring-primary"
                        />
                        <label htmlFor="policy_federated_tools" className="flex-1">
                            <span className="text-sm font-medium">Federated tools</span>
                            <p className="text-xs text-muted-foreground mt-0.5">
                                Allow your node to participate in cross-team tool calls and search.
                                Other team members can query your memories, sessions, and context.
                            </p>
                        </label>
                    </div>
                </div>
            </CardContent>
            <CardFooter className="bg-muted/30 py-3 border-t flex items-center justify-between">
                <p className="text-xs text-muted-foreground">
                    Changes take effect immediately after save.
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
