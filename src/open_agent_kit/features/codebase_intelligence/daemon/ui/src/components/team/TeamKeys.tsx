/**
 * Team API Keys page — server mode only.
 *
 * Displays a table of API keys with management actions.
 * Creating a key shows the plaintext once with a copy button.
 * Revoking requires confirmation.
 */

import { useState, useRef, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import {
    useTeamKeys,
    useTeamConfig,
    useCreateKey,
    useRevokeKey,
    type KeyResponse,
    type KeyCreateResponse,
} from "@/hooks/use-team";
import {
    Key,
    Plus,
    Copy,
    Check,
    Loader2,
    AlertCircle,
    ShieldAlert,
    X,
    Trash2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { formatRelativeTime, COPIED_FEEDBACK_DURATION_MS } from "@/lib/constants";

// =============================================================================
// Components
// =============================================================================

function KeyStatusBadge({ keyItem }: { keyItem: KeyResponse }) {
    if (keyItem.revoked_at) {
        return (
            <span className="flex items-center gap-1 px-2 py-0.5 text-xs rounded-full bg-red-500/10 text-red-500">
                Revoked
            </span>
        );
    }
    return (
        <span className="flex items-center gap-1 px-2 py-0.5 text-xs rounded-full bg-green-500/10 text-green-600">
            Active
        </span>
    );
}

function CreateKeyDialog({
    open,
    onOpenChange,
}: {
    open: boolean;
    onOpenChange: (open: boolean) => void;
}) {
    const [name, setName] = useState("");
    const [createdKey, setCreatedKey] = useState<KeyCreateResponse | null>(null);
    const [copied, setCopied] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const copyTimerRef = useRef<ReturnType<typeof setTimeout>>(undefined);
    const createKey = useCreateKey();

    useEffect(() => () => clearTimeout(copyTimerRef.current), []);

    // Reset state when dialog opens
    useEffect(() => {
        if (open) {
            setName("");
            setCreatedKey(null);
            setCopied(false);
            setError(null);
        }
    }, [open]);

    const handleCreate = async () => {
        if (!name.trim()) {
            setError("Key name is required.");
            return;
        }
        setError(null);
        try {
            const result = await createKey.mutateAsync(name.trim());
            setCreatedKey(result);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to create key");
        }
    };

    const handleCopy = async () => {
        if (!createdKey) return;
        try {
            await navigator.clipboard.writeText(createdKey.key);
            setCopied(true);
            clearTimeout(copyTimerRef.current);
            copyTimerRef.current = setTimeout(() => setCopied(false), COPIED_FEEDBACK_DURATION_MS);
        } catch {
            // Clipboard API may not be available
        }
    };

    if (!open) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
            <div
                className="fixed inset-0 bg-black/50 backdrop-blur-sm"
                onClick={() => !createKey.isPending && onOpenChange(false)}
            />
            <div className="relative z-50 w-full max-w-md rounded-lg border bg-background p-6 shadow-lg animate-in fade-in-0 zoom-in-95">
                {/* Header */}
                <div className="flex items-center justify-between mb-4">
                    <div>
                        <h2 className="text-lg font-semibold">
                            {createdKey ? "Key Created" : "Create API Key"}
                        </h2>
                        <p className="text-sm text-muted-foreground">
                            {createdKey
                                ? "Copy the key now. It will not be shown again."
                                : "Give the key a descriptive name for identification."}
                        </p>
                    </div>
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onOpenChange(false)}
                        disabled={createKey.isPending}
                        className="h-8 w-8 p-0"
                    >
                        <X className="h-4 w-4" />
                    </Button>
                </div>

                {createdKey ? (
                    <div className="space-y-4">
                        {/* Plaintext key display */}
                        <div className="space-y-2">
                            <label className="text-sm font-medium">API Key</label>
                            <div className="flex items-center gap-2">
                                <code className="flex-1 bg-muted px-3 py-2 rounded-md text-sm font-mono break-all border">
                                    {createdKey.key}
                                </code>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={handleCopy}
                                    className="flex-shrink-0"
                                >
                                    {copied ? (
                                        <Check className="h-4 w-4 text-green-500" />
                                    ) : (
                                        <Copy className="h-4 w-4" />
                                    )}
                                </Button>
                            </div>
                        </div>

                        <div className="flex items-start gap-2 p-3 rounded-md bg-amber-500/10 text-amber-700 text-xs">
                            <ShieldAlert className="h-4 w-4 mt-0.5 flex-shrink-0" />
                            <span>
                                This is the only time the key will be displayed.
                                Store it securely before closing this dialog.
                            </span>
                        </div>

                        <div className="flex justify-end">
                            <Button onClick={() => onOpenChange(false)}>
                                Done
                            </Button>
                        </div>
                    </div>
                ) : (
                    <div className="space-y-4">
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Key Name</label>
                            <input
                                type="text"
                                value={name}
                                onChange={(e) => {
                                    setName(e.target.value);
                                    setError(null);
                                }}
                                placeholder="e.g. CI pipeline, team-member-laptop"
                                className="w-full h-10 rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                                disabled={createKey.isPending}
                                autoFocus
                            />
                        </div>

                        {error && (
                            <div className="text-sm text-destructive bg-destructive/10 px-3 py-2 rounded">
                                {error}
                            </div>
                        )}

                        <div className="flex justify-end gap-3">
                            <Button
                                variant="outline"
                                onClick={() => onOpenChange(false)}
                                disabled={createKey.isPending}
                            >
                                Cancel
                            </Button>
                            <Button
                                onClick={handleCreate}
                                disabled={createKey.isPending || !name.trim()}
                            >
                                {createKey.isPending && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                                Create Key
                            </Button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

// =============================================================================
// Main Component
// =============================================================================

export default function TeamKeys() {
    const { data: config } = useTeamConfig();
    const { data: keys, isLoading, isError, error } = useTeamKeys();
    const revokeKey = useRevokeKey();

    const [createDialogOpen, setCreateDialogOpen] = useState(false);
    const [revokeDialogOpen, setRevokeDialogOpen] = useState(false);
    const [revokingKey, setRevokingKey] = useState<KeyResponse | null>(null);

    const isServerMode = config?.server_mode ?? false;

    // If not in server mode, show a message
    if (!isServerMode) {
        return (
            <Card>
                <CardContent className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                    <Key className="w-12 h-12 mb-4 opacity-30" />
                    <p className="text-sm">API key management is only available in server mode.</p>
                    <p className="text-xs mt-1">
                        Start the daemon with the team server environment variable to enable this feature.
                    </p>
                </CardContent>
            </Card>
        );
    }

    if (isLoading) {
        return (
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
        );
    }

    const handleRevokeClick = (keyItem: KeyResponse) => {
        setRevokingKey(keyItem);
        setRevokeDialogOpen(true);
    };

    const handleRevokeConfirm = async () => {
        if (!revokingKey) return;
        try {
            await revokeKey.mutateAsync(revokingKey.id);
            setRevokeDialogOpen(false);
            setRevokingKey(null);
        } catch {
            // Error handled by mutation
        }
    };

    const keysList = keys ?? [];

    return (
        <div className="space-y-4">
            {/* Error banner */}
            {isError && (
                <div className="flex items-center gap-2 p-3 rounded-md bg-red-500/10 text-red-600 text-sm">
                    <AlertCircle className="h-4 w-4 flex-shrink-0" />
                    <span>{error instanceof Error ? error.message : "Failed to fetch keys"}</span>
                </div>
            )}

            {/* Header */}
            <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">
                    {keysList.length} {keysList.length === 1 ? "key" : "keys"}
                </span>
                <Button
                    variant="default"
                    size="sm"
                    onClick={() => setCreateDialogOpen(true)}
                >
                    <Plus className="w-4 h-4 mr-1" />
                    Create Key
                </Button>
            </div>

            {/* Keys list */}
            {keysList.length === 0 ? (
                <Card>
                    <CardContent className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                        <Key className="w-12 h-12 mb-4 opacity-30" />
                        <p className="text-sm">No API keys yet.</p>
                        <p className="text-xs mt-1 mb-4">
                            Create a key to allow team members to authenticate.
                        </p>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setCreateDialogOpen(true)}
                        >
                            <Plus className="w-4 h-4 mr-1" />
                            Create Key
                        </Button>
                    </CardContent>
                </Card>
            ) : (
                <Card>
                    <CardHeader className="pb-3">
                        <CardTitle className="flex items-center gap-2 text-base">
                            <Key className="h-4 w-4" />
                            API Keys
                        </CardTitle>
                        <CardDescription>
                            Manage API keys for team member authentication.
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="p-0">
                        <div className="border-t divide-y">
                            {/* Table header */}
                            <div className="grid grid-cols-5 gap-4 px-6 py-3 text-xs font-medium text-muted-foreground bg-muted/30">
                                <div>Name</div>
                                <div>Machine ID</div>
                                <div>Created</div>
                                <div>Last Used</div>
                                <div className="text-right">Actions</div>
                            </div>

                            {/* Table rows */}
                            {keysList.map((keyItem) => (
                                <div
                                    key={keyItem.id}
                                    className={cn(
                                        "grid grid-cols-5 gap-4 px-6 py-3 items-center",
                                        keyItem.revoked_at && "opacity-60"
                                    )}
                                >
                                    <div className="flex items-center gap-2 min-w-0">
                                        <Key className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                                        <span className="text-sm font-medium truncate">
                                            {keyItem.name}
                                        </span>
                                        <KeyStatusBadge keyItem={keyItem} />
                                    </div>
                                    <div>
                                        {keyItem.machine_id ? (
                                            <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                                                {keyItem.machine_id}
                                            </code>
                                        ) : (
                                            <span className="text-xs text-muted-foreground">-</span>
                                        )}
                                    </div>
                                    <div className="text-sm text-muted-foreground">
                                        {formatRelativeTime(keyItem.created_at)}
                                    </div>
                                    <div className="text-sm text-muted-foreground">
                                        {keyItem.last_used_at
                                            ? formatRelativeTime(keyItem.last_used_at)
                                            : "Never"}
                                    </div>
                                    <div className="text-right">
                                        {!keyItem.revoked_at && (
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                onClick={() => handleRevokeClick(keyItem)}
                                                className="text-destructive hover:text-destructive h-7 px-2"
                                                title="Revoke key"
                                            >
                                                <Trash2 className="w-3 h-3" />
                                            </Button>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Create Key Dialog */}
            <CreateKeyDialog
                open={createDialogOpen}
                onOpenChange={setCreateDialogOpen}
            />

            {/* Revoke Confirmation Dialog */}
            <ConfirmDialog
                open={revokeDialogOpen}
                onOpenChange={(open) => {
                    setRevokeDialogOpen(open);
                    if (!open) setRevokingKey(null);
                }}
                title="Revoke API Key"
                description={`Are you sure you want to revoke the key "${revokingKey?.name}"? This action cannot be undone. Any client using this key will lose access.`}
                confirmLabel="Revoke"
                cancelLabel="Cancel"
                onConfirm={handleRevokeConfirm}
                isLoading={revokeKey.isPending}
                variant="destructive"
                loadingLabel="Revoking..."
            />
        </div>
    );
}
