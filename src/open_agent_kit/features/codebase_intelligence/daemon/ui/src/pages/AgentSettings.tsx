/**
 * Agent Settings page for configuring execution provider.
 *
 * Allows users to configure whether agents use Claude Code (default)
 * or a local provider (Ollama, LM Studio) for execution.
 */

import { useState, useEffect, useCallback } from "react";
import {
    useAgentSettings,
    useUpdateAgentSettings,
    listAgentProviderModels,
    testAgentProvider,
    type ProviderModelsResponse,
    type TestProviderResponse,
} from "@/hooks/use-agent-settings";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import {
    AlertCircle,
    Save,
    Loader2,
    CheckCircle2,
    Cloud,
    Server,
    Info,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
    Label,
    StepHeader,
    TestResult,
    UrlInputWithRefresh,
    ModelSelect,
    TestButton,
    ReadyBadge,
} from "@/components/ui/config-components";
import {
    AGENT_PROVIDER_TYPES,
    AGENT_PROVIDER_OPTIONS,
    AGENT_PROVIDER_DEFAULT_URLS,
    AGENT_PROVIDER_RECOMMENDED_MODELS,
    type AgentProviderType,
} from "@/lib/constants";

// =============================================================================
// Type Definitions
// =============================================================================

interface FormData {
    provider_type: string;
    provider_base_url: string;
    provider_model: string;
}

interface ModelOption {
    name: string;
    id?: string;
    display_name?: string;
}

// =============================================================================
// Main Component
// =============================================================================

export default function AgentSettings() {
    const { data: settings, isLoading } = useAgentSettings();
    const updateSettings = useUpdateAgentSettings();

    const [formData, setFormData] = useState<FormData | null>(null);
    const [isDirty, setIsDirty] = useState(false);
    const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

    // Discovery State
    const [models, setModels] = useState<ModelOption[]>([]);
    const [isDiscovering, setIsDiscovering] = useState(false);
    const [isTesting, setIsTesting] = useState(false);
    const [testResult, setTestResult] = useState<TestProviderResponse | null>(null);

    // Initialize form data from settings (nested provider object)
    useEffect(() => {
        if (settings && !isDirty) {
            const provider = settings.provider;
            setFormData({
                provider_type: provider?.type || AGENT_PROVIDER_TYPES.CLOUD,
                provider_base_url: provider?.base_url || "",
                provider_model: provider?.model || "",
            });
        }
    }, [settings, isDirty]);

    // Auto-discover models on initial load if provider is configured
    useEffect(() => {
        if (settings?.provider && settings.provider.type !== AGENT_PROVIDER_TYPES.CLOUD && settings.provider.base_url) {
            handleDiscoverModels(settings.provider.type, settings.provider.base_url);
        }
        // Only run on initial settings load
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [settings?.provider?.type]);

    const isCloudProvider = formData?.provider_type === AGENT_PROVIDER_TYPES.CLOUD;

    const handleProviderChange = useCallback((provider: string) => {
        const defaultUrl = AGENT_PROVIDER_DEFAULT_URLS[provider as AgentProviderType] || "";
        setFormData((prev) => {
            if (!prev) return prev;
            return {
                ...prev,
                provider_type: provider,
                provider_base_url: defaultUrl,
                provider_model: "",
            };
        });
        setIsDirty(true);
        setMessage(null);
        setModels([]);
        setTestResult(null);
    }, []);

    const handleChange = useCallback((field: keyof FormData, value: string) => {
        setFormData((prev) => {
            if (!prev) return prev;
            return { ...prev, [field]: value };
        });
        setIsDirty(true);
        setMessage(null);
        if (field === "provider_base_url") {
            setTestResult(null);
            setModels([]);
        }
    }, []);

    const handleDiscoverModels = async (provider?: string, baseUrl?: string) => {
        const providerType = provider || formData?.provider_type;
        const url = baseUrl || formData?.provider_base_url;
        if (!providerType || providerType === AGENT_PROVIDER_TYPES.CLOUD || !url) return;

        setIsDiscovering(true);
        setTestResult(null);
        try {
            const res: ProviderModelsResponse = await listAgentProviderModels(providerType, url);
            if (res.success && res.models) {
                setModels(res.models.map((m) => ({ name: m.name, display_name: m.name })));
                if (res.models.length === 0) {
                    setTestResult({ success: false, error: "No models found. Pull a model first." });
                }
            } else {
                setTestResult({ success: false, error: res.error || "Discovery failed" });
            }
        } catch (e: unknown) {
            const errorMessage = e instanceof Error ? e.message : "Unknown error";
            setTestResult({ success: false, error: errorMessage });
        } finally {
            setIsDiscovering(false);
        }
    };

    const handleModelSelect = useCallback((modelName: string) => {
        setFormData((prev) => {
            if (!prev) return prev;
            return { ...prev, provider_model: modelName };
        });
        setIsDirty(true);
        setTestResult(null);
    }, []);

    const handleTest = async () => {
        if (!formData || formData.provider_type === AGENT_PROVIDER_TYPES.CLOUD) return;

        setIsTesting(true);
        try {
            const res = await testAgentProvider({
                provider: formData.provider_type,
                base_url: formData.provider_base_url,
                model: formData.provider_model || undefined,
            });
            setTestResult(res);
        } catch (e: unknown) {
            const errorMessage = e instanceof Error ? e.message : "Unknown error";
            setTestResult({ success: false, error: errorMessage });
        } finally {
            setIsTesting(false);
        }
    };

    const handleSave = async () => {
        if (!formData) return;
        try {
            // Send nested provider object matching backend API
            const payload = {
                provider: {
                    type: formData.provider_type,
                    base_url: formData.provider_type === AGENT_PROVIDER_TYPES.CLOUD
                        ? null
                        : formData.provider_base_url || null,
                    model: formData.provider_type === AGENT_PROVIDER_TYPES.CLOUD
                        ? null
                        : formData.provider_model || null,
                },
            };
            await updateSettings.mutateAsync(payload);
            setMessage({ type: "success", text: "Agent settings saved successfully." });
            setIsDirty(false);
            setTestResult(null);
        } catch (err: unknown) {
            const errorMessage = err instanceof Error ? err.message : "Failed to save settings.";
            setMessage({ type: "error", text: errorMessage });
        }
    };

    // Validation
    const isValid = formData?.provider_type === AGENT_PROVIDER_TYPES.CLOUD ||
        (formData?.provider_base_url && formData?.provider_model);

    if (isLoading || !formData) {
        return (
            <div className="p-8 flex items-center justify-center">
                <Loader2 className="animate-spin mr-2" /> Loading settings...
            </div>
        );
    }

    return (
        <div className="space-y-6 max-w-3xl">
            {message && (
                <div
                    className={cn(
                        "p-4 rounded-md flex items-center gap-2",
                        message.type === "success"
                            ? "bg-green-500/10 text-green-600"
                            : "bg-red-500/10 text-red-600"
                    )}
                >
                    {message.type === "error" && <AlertCircle className="w-4 h-4" />}
                    {message.type === "success" && <CheckCircle2 className="w-4 h-4" />}
                    {message.text}
                </div>
            )}

            {/* Provider Selection Card */}
            <Card>
                <CardHeader>
                    <div className="flex items-center justify-between">
                        <div>
                            <CardTitle>Agent Execution Provider</CardTitle>
                            <CardDescription>
                                Configure how agents execute. By default, agents use your Claude Code
                                subscription. Alternatively, use a local provider for offline execution.
                            </CardDescription>
                        </div>
                        <ReadyBadge show={Boolean(isValid)} />
                    </div>
                </CardHeader>
                <CardContent className="space-y-6">
                    {/* Provider Type Selection */}
                    <div className="space-y-3">
                        <Label>Provider</Label>
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                            {AGENT_PROVIDER_OPTIONS.map((opt) => (
                                <button
                                    key={opt.value}
                                    type="button"
                                    onClick={() => handleProviderChange(opt.value)}
                                    className={cn(
                                        "flex items-center gap-3 p-4 rounded-lg border-2 transition-all text-left",
                                        formData.provider_type === opt.value
                                            ? "border-primary bg-primary/5"
                                            : "border-border hover:border-primary/50 hover:bg-muted/50"
                                    )}
                                >
                                    {opt.value === AGENT_PROVIDER_TYPES.CLOUD ? (
                                        <Cloud className="w-5 h-5 flex-shrink-0" />
                                    ) : (
                                        <Server className="w-5 h-5 flex-shrink-0" />
                                    )}
                                    <div>
                                        <div className="font-medium text-sm">{opt.label}</div>
                                        {opt.value === AGENT_PROVIDER_TYPES.CLOUD && (
                                            <div className="text-xs text-muted-foreground">Recommended</div>
                                        )}
                                    </div>
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Cloud Provider Info */}
                    {isCloudProvider && (
                        <div className="flex items-start gap-3 p-4 bg-muted/30 rounded-lg">
                            <Info className="w-5 h-5 text-blue-500 flex-shrink-0 mt-0.5" />
                            <div className="text-sm">
                                <p className="font-medium">Using Claude Code</p>
                                <p className="text-muted-foreground mt-1">
                                    Agents will use your logged-in Claude Code account and subscription.
                                    No additional configuration needed.
                                </p>
                            </div>
                        </div>
                    )}

                    {/* Local Provider Configuration */}
                    {!isCloudProvider && (
                        <>
                            {/* Step 1: Connect */}
                            <div className="space-y-3">
                                <StepHeader
                                    step={1}
                                    title="Connect to Provider"
                                    isComplete={Boolean(formData.provider_base_url)}
                                />
                                <div className="pl-7">
                                    <Label>Base URL</Label>
                                    <UrlInputWithRefresh
                                        value={formData.provider_base_url}
                                        onChange={(url) => handleChange("provider_base_url", url)}
                                        onRefresh={() => handleDiscoverModels()}
                                        isRefreshing={isDiscovering}
                                        placeholder={AGENT_PROVIDER_DEFAULT_URLS[formData.provider_type as AgentProviderType]}
                                    />
                                </div>
                            </div>

                            {/* Step 2: Select Model */}
                            <div className="space-y-3">
                                <StepHeader
                                    step={2}
                                    title="Select Model"
                                    isComplete={Boolean(formData.provider_model)}
                                />
                                <div className="pl-7">
                                    <ModelSelect
                                        value={formData.provider_model}
                                        models={models}
                                        onChange={(modelId) => handleModelSelect(modelId)}
                                        placeholder="e.g. qwen3:32b"
                                        helpText={
                                            models.length === 0
                                                ? "Click the refresh button to load available models"
                                                : "Select a model with 64k+ context window recommended"
                                        }
                                    />
                                    {/* Recommended models hint */}
                                    {AGENT_PROVIDER_RECOMMENDED_MODELS[formData.provider_type as AgentProviderType]?.length > 0 && (
                                        <div className="mt-2 text-xs text-muted-foreground">
                                            Recommended:{" "}
                                            {AGENT_PROVIDER_RECOMMENDED_MODELS[formData.provider_type as AgentProviderType].join(", ")}
                                        </div>
                                    )}
                                </div>
                            </div>

                            {/* Step 3: Test Connection */}
                            <div className="space-y-3">
                                <StepHeader
                                    step={3}
                                    title="Test Connection"
                                    isComplete={Boolean(testResult?.success)}
                                />
                                <div className="pl-7 bg-muted/30 p-4 rounded-md border border-dashed">
                                    <TestButton
                                        onClick={handleTest}
                                        isTesting={isTesting}
                                        disabled={!formData.provider_base_url}
                                        label="Test Provider"
                                    />
                                    <TestResult result={testResult} className="mt-3" />
                                </div>
                            </div>

                            {/* Important Notes */}
                            <div className="flex items-start gap-3 p-4 bg-amber-500/10 rounded-lg">
                                <AlertCircle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                                <div className="text-sm">
                                    <p className="font-medium text-amber-600">Important Notes</p>
                                    <ul className="text-muted-foreground mt-1 list-disc list-inside space-y-1">
                                        <li>Local providers require 64k+ context window models</li>
                                        <li>Ollama requires v0.14.0+ for Anthropic API compatibility</li>
                                        <li>32GB RAM recommended for usable local model experience</li>
                                        <li>First request may be slow while model loads</li>
                                    </ul>
                                </div>
                            </div>
                        </>
                    )}
                </CardContent>
                <CardFooter className="bg-muted/30 py-4 flex justify-end border-t">
                    <Button
                        onClick={handleSave}
                        disabled={!isDirty || !isValid || updateSettings.isPending}
                        size="lg"
                        className="shadow-lg"
                    >
                        {updateSettings.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        <Save className="mr-2 h-4 w-4" /> Save Settings
                    </Button>
                </CardFooter>
            </Card>
        </div>
    );
}
