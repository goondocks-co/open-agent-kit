/**
 * Governance rules editor.
 *
 * Features:
 * - View current governance config (enabled, enforcement mode)
 * - Toggle governance on/off
 * - Toggle enforcement mode (observe/enforce)
 * - List rules with enable/disable toggles
 * - Add/edit/delete rules via dialog
 * - Test a tool call against current policy
 */

import { useState, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import {
    useGovernanceConfig,
    useSaveGovernanceConfig,
    useTestGovernanceRule,
    usePruneAuditEvents,
    type GovernanceConfig,
    type GovernanceRule,
} from "@/hooks/use-governance";
import {
    Shield,
    ShieldCheck,
    ShieldAlert,
    Plus,
    Pencil,
    Trash2,
    Loader2,
    Power,
    PowerOff,
    Eye,
    ShieldBan,
    FlaskConical,
    Save,
    X,
    CheckCircle,
    AlertTriangle,
    Clock,
} from "lucide-react";
import { cn } from "@/lib/utils";

// =============================================================================
// Constants
// =============================================================================

const ACTION_OPTIONS = [
    { value: "deny", label: "Deny", description: "Block the tool call (enforce mode only)" },
    { value: "warn", label: "Warn", description: "Allow but warn the agent (enforce mode only)" },
    { value: "observe", label: "Observe", description: "Log only, never block" },
] as const;

const EMPTY_RULE: GovernanceRule = {
    id: "",
    description: "",
    enabled: true,
    tool: "*",
    pattern: "",
    path_pattern: "",
    action: "observe",
    message: "",
};

// =============================================================================
// Helper Components
// =============================================================================

function RuleActionBadge({ action }: { action: string }) {
    const config: Record<string, { label: string; className: string }> = {
        deny: { label: "Deny", className: "bg-red-500/10 text-red-500" },
        warn: { label: "Warn", className: "bg-amber-500/10 text-amber-500" },
        observe: { label: "Observe", className: "bg-blue-500/10 text-blue-500" },
        allow: { label: "Allow", className: "bg-green-500/10 text-green-600" },
    };
    const c = config[action] ?? config.observe;

    return (
        <span className={cn("px-2 py-0.5 text-xs rounded-full font-medium", c.className)}>
            {c.label}
        </span>
    );
}

function RuleRow({
    rule,
    onToggle,
    onEdit,
    onDelete,
}: {
    rule: GovernanceRule;
    onToggle: (id: string, enabled: boolean) => void;
    onEdit: (rule: GovernanceRule) => void;
    onDelete: (rule: GovernanceRule) => void;
}) {
    return (
        <div className={cn("border rounded-md p-4 space-y-2", !rule.enabled && "opacity-60")}>
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <code className="text-sm font-semibold">{rule.id}</code>
                    <RuleActionBadge action={rule.action} />
                    {!rule.enabled && (
                        <span className="text-xs text-muted-foreground">(disabled)</span>
                    )}
                </div>

                <div className="flex items-center gap-1">
                    <Button variant="ghost" size="sm" onClick={() => onEdit(rule)} title="Edit rule">
                        <Pencil className="w-4 h-4" />
                    </Button>
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onDelete(rule)}
                        className="text-destructive hover:text-destructive"
                        title="Delete rule"
                    >
                        <Trash2 className="w-4 h-4" />
                    </Button>
                    <Button
                        variant={rule.enabled ? "outline" : "ghost"}
                        size="sm"
                        onClick={() => onToggle(rule.id, !rule.enabled)}
                        className={rule.enabled ? "text-green-600" : "text-muted-foreground"}
                    >
                        {rule.enabled ? <Power className="w-4 h-4" /> : <PowerOff className="w-4 h-4" />}
                    </Button>
                </div>
            </div>

            {rule.description && (
                <p className="text-sm text-muted-foreground">{rule.description}</p>
            )}

            <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                <div>
                    <span className="font-medium">Tool:</span>{" "}
                    <code className="bg-muted px-1 rounded">{rule.tool}</code>
                </div>
                {rule.pattern && (
                    <div>
                        <span className="font-medium">Pattern:</span>{" "}
                        <code className="bg-muted px-1 rounded">{rule.pattern}</code>
                    </div>
                )}
                {rule.path_pattern && (
                    <div>
                        <span className="font-medium">Path:</span>{" "}
                        <code className="bg-muted px-1 rounded">{rule.path_pattern}</code>
                    </div>
                )}
                {rule.message && (
                    <div>
                        <span className="font-medium">Message:</span>{" "}
                        <span className="italic">{rule.message}</span>
                    </div>
                )}
            </div>
        </div>
    );
}

// =============================================================================
// Rule Form Dialog
// =============================================================================

interface RuleFormDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    mode: "create" | "edit";
    rule: GovernanceRule;
    existingIds: Set<string>;
    onSave: (rule: GovernanceRule) => void;
}

function RuleFormDialog({ open, onOpenChange, mode, rule, existingIds, onSave }: RuleFormDialogProps) {
    const [form, setForm] = useState<GovernanceRule>(rule);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (open) {
            setForm(rule);
            setError(null);
        }
    }, [open, rule]);

    const handleSave = () => {
        if (!form.id.trim()) {
            setError("Rule ID is required");
            return;
        }
        if (!/^[a-z0-9-]+$/.test(form.id)) {
            setError("Rule ID must be lowercase alphanumeric with dashes only");
            return;
        }
        if (mode === "create" && existingIds.has(form.id)) {
            setError(`Rule "${form.id}" already exists`);
            return;
        }
        onSave(form);
        onOpenChange(false);
    };

    if (!open) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
            <div className="fixed inset-0 bg-black/50 backdrop-blur-sm" onClick={() => onOpenChange(false)} />
            <div className="relative z-50 w-full max-w-lg rounded-lg border bg-background p-6 shadow-lg animate-in fade-in-0 zoom-in-95 max-h-[90vh] overflow-y-auto">
                <div className="flex items-center justify-between mb-4">
                    <h2 className="text-lg font-semibold">{mode === "create" ? "Add Rule" : "Edit Rule"}</h2>
                    <Button variant="ghost" size="sm" onClick={() => onOpenChange(false)} className="h-8 w-8 p-0">
                        <X className="h-4 w-4" />
                    </Button>
                </div>

                <div className="space-y-4">
                    {/* Rule ID */}
                    <div className="space-y-1">
                        <label className="text-sm font-medium">Rule ID</label>
                        <input
                            type="text"
                            value={form.id}
                            onChange={(e) => setForm({ ...form, id: e.target.value })}
                            placeholder="no-env-writes"
                            className="w-full px-3 py-2 rounded-md border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                            disabled={mode === "edit"}
                        />
                        <p className="text-xs text-muted-foreground">Lowercase with dashes. Cannot be changed after creation.</p>
                    </div>

                    {/* Description */}
                    <div className="space-y-1">
                        <label className="text-sm font-medium">Description</label>
                        <input
                            type="text"
                            value={form.description}
                            onChange={(e) => setForm({ ...form, description: e.target.value })}
                            placeholder="Block writes to .env files"
                            className="w-full px-3 py-2 rounded-md border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                        />
                    </div>

                    {/* Action */}
                    <div className="space-y-1">
                        <label className="text-sm font-medium">Action</label>
                        <select
                            value={form.action}
                            onChange={(e) => setForm({ ...form, action: e.target.value })}
                            className="w-full px-3 py-2 rounded-md border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                        >
                            {ACTION_OPTIONS.map((opt) => (
                                <option key={opt.value} value={opt.value}>
                                    {opt.label} — {opt.description}
                                </option>
                            ))}
                        </select>
                    </div>

                    {/* Tool */}
                    <div className="space-y-1">
                        <label className="text-sm font-medium">Tool name</label>
                        <input
                            type="text"
                            value={form.tool}
                            onChange={(e) => setForm({ ...form, tool: e.target.value })}
                            placeholder="* (all tools)"
                            className="w-full px-3 py-2 rounded-md border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                        />
                        <p className="text-xs text-muted-foreground">Tool name or glob pattern (e.g. "Bash", "Write", "*").</p>
                    </div>

                    {/* Pattern (regex) */}
                    <div className="space-y-1">
                        <label className="text-sm font-medium">Input pattern (regex, optional)</label>
                        <input
                            type="text"
                            value={form.pattern}
                            onChange={(e) => setForm({ ...form, pattern: e.target.value })}
                            placeholder="rm\s+-rf|DROP\s+TABLE"
                            className="w-full px-3 py-2 rounded-md border bg-background text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring"
                        />
                        <p className="text-xs text-muted-foreground">Regex matched against the serialized tool input.</p>
                    </div>

                    {/* Path pattern */}
                    <div className="space-y-1">
                        <label className="text-sm font-medium">Path pattern (fnmatch, optional)</label>
                        <input
                            type="text"
                            value={form.path_pattern}
                            onChange={(e) => setForm({ ...form, path_pattern: e.target.value })}
                            placeholder="*.env"
                            className="w-full px-3 py-2 rounded-md border bg-background text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring"
                        />
                        <p className="text-xs text-muted-foreground">Matched against file_path from tool input.</p>
                    </div>

                    {/* Message */}
                    <div className="space-y-1">
                        <label className="text-sm font-medium">Agent message (optional)</label>
                        <textarea
                            value={form.message}
                            onChange={(e) => setForm({ ...form, message: e.target.value })}
                            placeholder="This action is not allowed by governance policy."
                            rows={2}
                            className="w-full px-3 py-2 rounded-md border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring resize-y"
                        />
                        <p className="text-xs text-muted-foreground">Shown to the agent when the rule triggers.</p>
                    </div>

                    {error && (
                        <div className="text-sm text-destructive bg-destructive/10 px-3 py-2 rounded">{error}</div>
                    )}
                </div>

                <div className="flex justify-end gap-3 mt-6">
                    <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
                    <Button onClick={handleSave}>
                        <Save className="w-4 h-4 mr-1" />
                        {mode === "create" ? "Add Rule" : "Save Changes"}
                    </Button>
                </div>
            </div>
        </div>
    );
}

// =============================================================================
// Test Panel
// =============================================================================

function TestPanel() {
    const [toolName, setToolName] = useState("");
    const [toolInput, setToolInput] = useState("");
    const testRule = useTestGovernanceRule();

    const handleTest = () => {
        let parsed: Record<string, unknown> = {};
        if (toolInput.trim()) {
            try {
                parsed = JSON.parse(toolInput);
            } catch {
                parsed = { raw: toolInput };
            }
        }
        testRule.mutate({ tool_name: toolName, tool_input: parsed });
    };

    return (
        <div className="border rounded-md p-4 space-y-3 bg-card">
            <div className="flex items-center gap-2">
                <FlaskConical className="w-4 h-4 text-muted-foreground" />
                <span className="text-sm font-medium">Test Policy</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1">
                    <label className="text-xs font-medium text-muted-foreground">Tool name</label>
                    <input
                        type="text"
                        value={toolName}
                        onChange={(e) => setToolName(e.target.value)}
                        placeholder="Bash"
                        className="w-full px-3 py-1.5 rounded-md border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                    />
                </div>
                <div className="space-y-1">
                    <label className="text-xs font-medium text-muted-foreground">Tool input (JSON)</label>
                    <input
                        type="text"
                        value={toolInput}
                        onChange={(e) => setToolInput(e.target.value)}
                        placeholder='{"command": "rm -rf /"}'
                        className="w-full px-3 py-1.5 rounded-md border bg-background text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring"
                    />
                </div>
            </div>

            <div className="flex items-center gap-3">
                <Button size="sm" onClick={handleTest} disabled={!toolName || testRule.isPending}>
                    {testRule.isPending ? (
                        <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                    ) : (
                        <FlaskConical className="w-4 h-4 mr-1" />
                    )}
                    Test
                </Button>

                {testRule.data && (
                    <div className="flex items-center gap-2 text-sm">
                        <RuleActionBadge action={testRule.data.action} />
                        {testRule.data.rule_id && (
                            <span className="text-xs text-muted-foreground">
                                rule: <code className="bg-muted px-1 rounded">{testRule.data.rule_id}</code>
                            </span>
                        )}
                        {testRule.data.reason && (
                            <span className="text-xs text-muted-foreground">{testRule.data.reason}</span>
                        )}
                    </div>
                )}

                {testRule.error && (
                    <span className="text-xs text-destructive">{testRule.error.message}</span>
                )}
            </div>
        </div>
    );
}

// =============================================================================
// Main Component
// =============================================================================

export default function GovernanceRules() {
    const { data: config, isLoading } = useGovernanceConfig();
    const saveConfig = useSaveGovernanceConfig();
    const pruneAudit = usePruneAuditEvents();

    const [localConfig, setLocalConfig] = useState<GovernanceConfig | null>(null);
    const [isDirty, setIsDirty] = useState(false);
    const [formOpen, setFormOpen] = useState(false);
    const [formMode, setFormMode] = useState<"create" | "edit">("create");
    const [editingRule, setEditingRule] = useState<GovernanceRule>(EMPTY_RULE);
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
    const [deletingRule, setDeletingRule] = useState<GovernanceRule | null>(null);
    const [saveSuccess, setSaveSuccess] = useState(false);

    // Sync server config to local state
    useEffect(() => {
        if (config && !isDirty) {
            setLocalConfig(config);
        }
    }, [config, isDirty]);

    const updateLocal = (patch: Partial<GovernanceConfig>) => {
        if (!localConfig) return;
        setLocalConfig({ ...localConfig, ...patch });
        setIsDirty(true);
        setSaveSuccess(false);
    };

    const handleSave = async () => {
        if (!localConfig) return;
        try {
            await saveConfig.mutateAsync(localConfig);
            setIsDirty(false);
            setSaveSuccess(true);
            setTimeout(() => setSaveSuccess(false), 3000);
        } catch {
            // Error handled by mutation
        }
    };

    const handleDiscard = () => {
        if (config) {
            setLocalConfig(config);
            setIsDirty(false);
        }
    };

    // Rule CRUD
    const handleAddRule = () => {
        setFormMode("create");
        setEditingRule({ ...EMPTY_RULE });
        setFormOpen(true);
    };

    const handleEditRule = (rule: GovernanceRule) => {
        setFormMode("edit");
        setEditingRule({ ...rule });
        setFormOpen(true);
    };

    const handleDeleteClick = (rule: GovernanceRule) => {
        setDeletingRule(rule);
        setDeleteDialogOpen(true);
    };

    const handleDeleteConfirm = () => {
        if (!localConfig || !deletingRule) return;
        updateLocal({
            rules: localConfig.rules.filter((r) => r.id !== deletingRule.id),
        });
        setDeleteDialogOpen(false);
        setDeletingRule(null);
    };

    const handleToggleRule = (id: string, enabled: boolean) => {
        if (!localConfig) return;
        updateLocal({
            rules: localConfig.rules.map((r) => (r.id === id ? { ...r, enabled } : r)),
        });
    };

    const handleRuleSave = (rule: GovernanceRule) => {
        if (!localConfig) return;
        if (formMode === "create") {
            updateLocal({ rules: [...localConfig.rules, rule] });
        } else {
            updateLocal({
                rules: localConfig.rules.map((r) => (r.id === rule.id ? rule : r)),
            });
        }
    };

    if (isLoading || !localConfig) {
        return (
            <div className="space-y-4">
                {[1, 2, 3].map((i) => (
                    <div key={i} className="border rounded-md p-4 animate-pulse">
                        <div className="h-6 bg-muted rounded w-1/3 mb-2" />
                        <div className="h-4 bg-muted rounded w-2/3" />
                    </div>
                ))}
            </div>
        );
    }

    const existingIds = new Set(localConfig.rules.map((r) => r.id));

    return (
        <div className="space-y-6">
            {/* Global Controls */}
            <div className="border rounded-md p-4 space-y-4 bg-card">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <Shield className="w-5 h-5 text-muted-foreground" />
                        <span className="font-medium">Governance Policy</span>
                    </div>

                    <div className="flex items-center gap-2">
                        {isDirty && (
                            <>
                                <Button variant="ghost" size="sm" onClick={handleDiscard}>
                                    Discard
                                </Button>
                                <Button size="sm" onClick={handleSave} disabled={saveConfig.isPending}>
                                    {saveConfig.isPending ? (
                                        <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                                    ) : (
                                        <Save className="w-4 h-4 mr-1" />
                                    )}
                                    Save
                                </Button>
                            </>
                        )}
                        {saveSuccess && (
                            <span className="flex items-center gap-1 text-xs text-green-600">
                                <CheckCircle className="w-3 h-3" />
                                Saved
                            </span>
                        )}
                    </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    {/* Enabled toggle */}
                    <div className="flex items-center justify-between border rounded-md p-3">
                        <div>
                            <div className="text-sm font-medium">Governance</div>
                            <div className="text-xs text-muted-foreground">
                                {localConfig.enabled ? "Evaluating tool calls against rules" : "Not active — no evaluation"}
                            </div>
                        </div>
                        <Button
                            variant={localConfig.enabled ? "outline" : "ghost"}
                            size="sm"
                            onClick={() => updateLocal({ enabled: !localConfig.enabled })}
                            className={localConfig.enabled ? "text-green-600" : "text-muted-foreground"}
                        >
                            {localConfig.enabled ? (
                                <><ShieldCheck className="w-4 h-4 mr-1" /> Enabled</>
                            ) : (
                                <><PowerOff className="w-4 h-4 mr-1" /> Disabled</>
                            )}
                        </Button>
                    </div>

                    {/* Enforcement mode */}
                    <div className="flex items-center justify-between border rounded-md p-3">
                        <div>
                            <div className="text-sm font-medium">Enforcement</div>
                            <div className="text-xs text-muted-foreground">
                                {localConfig.enforcement_mode === "enforce"
                                    ? "Deny rules will block tool calls"
                                    : "Observe only — deny rules downgraded to observe"}
                            </div>
                        </div>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => updateLocal({
                                enforcement_mode: localConfig.enforcement_mode === "enforce" ? "observe" : "enforce",
                            })}
                            className={localConfig.enforcement_mode === "enforce" ? "text-red-500" : "text-blue-500"}
                        >
                            {localConfig.enforcement_mode === "enforce" ? (
                                <><ShieldAlert className="w-4 h-4 mr-1" /> Enforce</>
                            ) : (
                                <><Eye className="w-4 h-4 mr-1" /> Observe</>
                            )}
                        </Button>
                    </div>

                    {/* Audit retention */}
                    <div className="flex items-center justify-between border rounded-md p-3">
                        <div className="flex-1 mr-3">
                            <div className="text-sm font-medium">Audit Retention</div>
                            <div className="text-xs text-muted-foreground">
                                Keep audit events for{" "}
                                <input
                                    type="number"
                                    min={1}
                                    max={365}
                                    value={localConfig.retention_days ?? 30}
                                    onChange={(e) => {
                                        const v = parseInt(e.target.value, 10);
                                        if (!isNaN(v)) updateLocal({ retention_days: Math.max(1, Math.min(365, v)) });
                                    }}
                                    className="w-14 px-1.5 py-0.5 rounded border bg-background text-sm text-center inline-block"
                                />{" "}
                                days
                            </div>
                        </div>
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => pruneAudit.mutate()}
                            disabled={pruneAudit.isPending}
                            title="Prune old events now"
                            className="text-muted-foreground"
                        >
                            {pruneAudit.isPending ? (
                                <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                            ) : (
                                <Clock className="w-4 h-4 mr-1" />
                            )}
                            Prune
                        </Button>
                    </div>
                </div>

                {localConfig.enforcement_mode === "enforce" && (
                    <div className="flex items-center gap-2 text-xs text-amber-600 bg-amber-500/10 px-3 py-2 rounded">
                        <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                        <span>Enforce mode is active. Deny rules will block agent tool calls in real time.</span>
                    </div>
                )}

                {saveConfig.error && (
                    <div className="text-sm text-destructive bg-destructive/10 px-3 py-2 rounded">
                        Failed to save: {saveConfig.error.message}
                    </div>
                )}
            </div>

            {/* Test Panel */}
            {localConfig.enabled && <TestPanel />}

            {/* Rules List */}
            <div className="space-y-3">
                <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">
                        Rules ({localConfig.rules.length})
                    </span>
                    <Button size="sm" onClick={handleAddRule}>
                        <Plus className="w-4 h-4 mr-1" />
                        Add Rule
                    </Button>
                </div>

                {localConfig.rules.length === 0 ? (
                    <Card>
                        <CardContent className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                            <ShieldBan className="w-12 h-12 mb-4 opacity-30" />
                            <p className="text-sm">No rules configured</p>
                            <p className="text-xs mt-1 mb-4">
                                Add rules to control what your agents can do.
                            </p>
                            <Button variant="outline" size="sm" onClick={handleAddRule}>
                                <Plus className="w-4 h-4 mr-1" />
                                Add Rule
                            </Button>
                        </CardContent>
                    </Card>
                ) : (
                    <div className="space-y-2">
                        {localConfig.rules.map((rule) => (
                            <RuleRow
                                key={rule.id}
                                rule={rule}
                                onToggle={handleToggleRule}
                                onEdit={handleEditRule}
                                onDelete={handleDeleteClick}
                            />
                        ))}
                    </div>
                )}
            </div>

            {/* Rule Form Dialog */}
            <RuleFormDialog
                open={formOpen}
                onOpenChange={setFormOpen}
                mode={formMode}
                rule={editingRule}
                existingIds={existingIds}
                onSave={handleRuleSave}
            />

            {/* Delete Confirmation */}
            <ConfirmDialog
                open={deleteDialogOpen}
                onOpenChange={(open) => {
                    setDeleteDialogOpen(open);
                    if (!open) setDeletingRule(null);
                }}
                title="Delete Rule"
                description={`Remove rule "${deletingRule?.id}"? This change takes effect when you save.`}
                confirmLabel="Remove"
                cancelLabel="Cancel"
                onConfirm={handleDeleteConfirm}
                variant="destructive"
            />
        </div>
    );
}
