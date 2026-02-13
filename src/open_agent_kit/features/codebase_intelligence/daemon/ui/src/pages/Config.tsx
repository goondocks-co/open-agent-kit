import { useState, useEffect, useMemo, useCallback } from "react";
import { Link } from "react-router-dom";
import { useConfig, useUpdateConfig, useExclusions, useUpdateExclusions, resetExclusions, restartDaemon, listProviderModels, listSummarizationModels, testEmbeddingConfig, testSummarizationConfig, type RestartResponse } from "@/hooks/use-config";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { AlertCircle, Save, Loader2, CheckCircle2, Plus, X, RotateCcw, FolderX, AlertTriangle, ArrowRight, BookOpen } from "lucide-react";
import { cn } from "@/lib/utils";
import { useQueryClient } from "@tanstack/react-query";
import {
    Label,
    Input,
    StepHeader,
    TestResult,
    ProviderSelect,
    UrlInputWithRefresh,
    ModelSelect,
    TestButton,
    ReadyBadge,
    ContextWindowInput,
    EMBEDDING_CONTEXT_PRESETS,
    LLM_CONTEXT_PRESETS,
} from "@/components/ui/config-components";
import {
    CONFIG_SECTIONS,
    CHUNK_SIZE_WARNING_THRESHOLD,
    DEFAULT_EMBEDDING_MODEL_PLACEHOLDER,
    DEFAULT_SUMMARIZATION_MODEL_PLACEHOLDER,
    DEFAULT_CONTEXT_WINDOW_PLACEHOLDER,
    DEFAULT_CHUNK_SIZE_PLACEHOLDER,
    DEFAULT_DIMENSIONS_PLACEHOLDER,
    LARGE_CONTEXT_WINDOW_PLACEHOLDER,
    LOG_ROTATION_DEFAULTS,
    LOG_ROTATION_LIMITS,
    SESSION_QUALITY_DEFAULTS,
    SESSION_QUALITY_LIMITS,
    calculateMaxLogDiskUsage,
    formatStaleTimeout,
    getDefaultProviderUrl,
    calculateChunkSize,
    toApiNumber,
} from "@/lib/constants";
import { ORIGIN_BADGE_CLASSES, ORIGIN_BADGE_LABELS } from "@/lib/constants/ui";

// =============================================================================
// Type Definitions
// =============================================================================

/** Model option from provider discovery API */
interface ModelOption {
    name?: string;
    id?: string;
    display_name?: string;
    dimensions?: number;
    context_window?: number;
    provider?: string;
}

/** Test result from Test & Detect API */
interface TestResultData {
    success: boolean;
    error?: string;
    message?: string;
    dimensions?: number;
    context_window?: number;
    pending_load?: boolean;
}

/** Form data structure (UI field names) */
interface EmbeddingFormData {
    provider: string;
    model: string;
    base_url: string;
    dimensions: number | string;
    max_tokens: number | string;  // UI name for context_tokens
    chunk_size: number | string;  // UI name for max_chunk_chars
}

interface SummarizationFormData {
    enabled: boolean;
    provider: string;
    model: string;
    base_url: string;
    max_tokens: number | string;  // UI name for context_tokens
}

interface LogRotationFormData {
    enabled: boolean;
    max_size_mb: number;
    backup_count: number;
}

interface SessionQualityFormData {
    min_activities: number;
    stale_timeout_seconds: number;
}

interface FormData {
    embedding: EmbeddingFormData;
    summarization: SummarizationFormData;
    log_rotation: LogRotationFormData;
    session_quality: SessionQualityFormData;
}

/** Validation result structure */
interface ValidationResult {
    isValid: boolean;
    errors: string[];
    warnings: string[];
    isEnabled?: boolean;
}

/** Model discovery response from API */
interface ModelDiscoveryResponse {
    success: boolean;
    models?: ModelOption[];
    error?: string;
}

/** Exclusions update response from API */
interface ExclusionsUpdateResponse {
    added?: string[];
    removed?: string[];
    already_exists?: string[];
    message?: string;
}

/** Config origin type from API */
type ConfigOrigin = "user" | "project" | "default";

/** Origin badge component for config section headers */
function OriginBadge({ origin }: { origin?: ConfigOrigin }) {
    if (!origin) return null;
    return (
        <span className={cn("text-xs px-2 py-0.5 rounded-full", ORIGIN_BADGE_CLASSES[origin])}>
            {ORIGIN_BADGE_LABELS[origin]}
        </span>
    );
}

export default function Config() {
    const { data: config, isLoading } = useConfig();
    const updateConfig = useUpdateConfig();

    const [formData, setFormData] = useState<FormData | null>(null);
    const [isDirty, setIsDirty] = useState(false);
    const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);

    // Discovery State
    const [embeddingModels, setEmbeddingModels] = useState<ModelOption[]>([]);
    const [isDiscoveringEmbedding, setIsDiscoveringEmbedding] = useState(false);
    const [isTestingEmbedding, setIsTestingEmbedding] = useState(false);
    const [embeddingTestResult, setEmbeddingTestResult] = useState<TestResultData | null>(null);

    const [summarizationModels, setSummarizationModels] = useState<ModelOption[]>([]);
    const [isDiscoveringSum, setIsDiscoveringSum] = useState(false);
    const [isTestingSum, setIsTestingSum] = useState(false);
    const [sumTestResult, setSumTestResult] = useState<TestResultData | null>(null);

    // =============================================================================
    // Validation Logic for Guided Flow (memoized for performance)
    // =============================================================================

    // Check if embedding config is valid and complete
    const embeddingValidation = useMemo((): ValidationResult => {
        const errors: string[] = [];
        const emb = formData?.embedding;
        if (!emb) return { isValid: false, errors: ["Loading..."], warnings: [] };

        // Required fields
        if (!emb.provider) errors.push("Select a provider");
        if (!emb.base_url) errors.push("Enter a base URL");
        if (!emb.model) errors.push("Select a model");
        if (!emb.dimensions) errors.push("Dimensions required (click Test & Detect or enter manually)");
        if (!emb.max_tokens) errors.push("Context window required (click Test & Detect or enter manually)");
        if (!emb.chunk_size) errors.push("Chunk size required (auto-calculated from context window)");

        // Validation rules
        const warnings: string[] = [];
        if (emb.chunk_size && emb.max_tokens) {
            const chunk = Number(emb.chunk_size);
            const context = Number(emb.max_tokens);
            if (chunk >= context) {
                errors.push("Chunk size must be smaller than context window");
            } else if (chunk > context * CHUNK_SIZE_WARNING_THRESHOLD) {
                warnings.push("Chunk size is close to context limit - consider reducing");
            }
        }

        // Test & Detect is recommended but not required if values are manually entered
        if (!embeddingTestResult?.success) {
            warnings.push("Run Test & Detect to verify configuration");
        }

        return { isValid: errors.length === 0, errors, warnings };
    }, [formData?.embedding, embeddingTestResult?.success]);

    // Check if summarization config is valid (only if enabled)
    const summarizationValidation = useMemo((): ValidationResult => {
        const errors: string[] = [];
        const warnings: string[] = [];
        const sum = formData?.summarization;
        if (!sum) return { isValid: true, errors: [], warnings: [], isEnabled: false };

        // If disabled, skip validation
        if (!sum.enabled) {
            return { isValid: true, errors: [], warnings: [], isEnabled: false };
        }

        // Required fields when enabled
        if (!sum.provider) errors.push("Select a provider");
        if (!sum.base_url) errors.push("Enter a base URL");
        if (!sum.model) errors.push("Select a model");
        if (!sum.max_tokens) errors.push("Context window required (click Test & Detect or enter manually)");

        // Test & Detect is recommended but not required if values are manually entered
        if (!sumTestResult?.success) {
            warnings.push("Run Test & Detect to verify configuration");
        }

        return { isValid: errors.length === 0, errors, warnings, isEnabled: true };
    }, [formData?.summarization, sumTestResult?.success]);

    // Combined validation for save button
    const canSave = useMemo(
        () => isDirty && embeddingValidation.isValid && summarizationValidation.isValid,
        [isDirty, embeddingValidation.isValid, summarizationValidation.isValid]
    );

    // Track if we've done initial model discovery
    const [initialLoadComplete, setInitialLoadComplete] = useState(false);
    // Track if the initial embedding discovery attempt has completed (to avoid flashing warning)
    const [embeddingDiscoveryComplete, setEmbeddingDiscoveryComplete] = useState(false);

    useEffect(() => {
        // Don't overwrite user's pending changes if they have unsaved edits
        if (config && !isDirty) {
            // Map API response keys to UI state keys
            const mappedData = JSON.parse(JSON.stringify(config));

            // Embedding mapping - always initialize to prevent undefined values
            // These use UI field names (max_tokens, chunk_size) mapped from API names (context_tokens, max_chunk_chars)
            mappedData.embedding.max_tokens = config.embedding.context_tokens ?? "";
            mappedData.embedding.chunk_size = config.embedding.max_chunk_chars ?? "";

            // Summarization mapping - always initialize
            mappedData.summarization.max_tokens = config.summarization.context_tokens ?? "";

            // Log rotation mapping - use defaults if not present
            mappedData.log_rotation = config.log_rotation ?? {
                enabled: LOG_ROTATION_DEFAULTS.ENABLED,
                max_size_mb: LOG_ROTATION_DEFAULTS.MAX_SIZE_MB,
                backup_count: LOG_ROTATION_DEFAULTS.BACKUP_COUNT,
            };

            // Session quality mapping - use defaults if not present
            mappedData.session_quality = config.session_quality ?? {
                min_activities: SESSION_QUALITY_DEFAULTS.MIN_ACTIVITIES,
                stale_timeout_seconds: SESSION_QUALITY_DEFAULTS.STALE_TIMEOUT_SECONDS,
            };

            setFormData(mappedData);
        }
    }, [config, isDirty]);

    // Auto-refresh model lists on initial load if config already has provider/URL configured
    useEffect(() => {
        if (config && !initialLoadComplete) {
            setInitialLoadComplete(true);

            // Auto-discover embedding models if provider and URL are configured
            if (config.embedding?.provider && config.embedding?.base_url) {
                listProviderModels(config.embedding.provider, config.embedding.base_url)
                    .then((res) => {
                        const response = res as ModelDiscoveryResponse;
                        if (response.success && response.models) {
                            setEmbeddingModels(response.models);
                        }
                    })
                    .catch(() => { /* silently fail - user can manually refresh */ })
                    .finally(() => setEmbeddingDiscoveryComplete(true));
            } else {
                // No provider configured, mark discovery as complete immediately
                setEmbeddingDiscoveryComplete(true);
            }

            // Auto-discover summarization models if enabled and provider/URL are configured
            if (config.summarization?.enabled && config.summarization?.provider && config.summarization?.base_url) {
                listSummarizationModels(config.summarization.provider, config.summarization.base_url)
                    .then((res) => {
                        const response = res as ModelDiscoveryResponse;
                        if (response.success && response.models) {
                            setSummarizationModels(response.models);
                        }
                    })
                    .catch(() => { /* silently fail - user can manually refresh */ });
            }
        }
    }, [config, initialLoadComplete]);

    const handleChange = useCallback((section: string, field: string, value: string | number | boolean) => {
        // Auto-update base URL when provider changes (embedding or summarization)
        const updates: Record<string, string | number | boolean> = { [field]: value };
        if (field === 'provider' && typeof value === 'string') {
            updates.base_url = getDefaultProviderUrl(value);
            // Clear model when provider changes
            updates.model = '';
        }

        // Auto-calculate chunk_size when context window (max_tokens) is manually entered for embedding
        if (section === CONFIG_SECTIONS.EMBEDDING && field === 'max_tokens' && value) {
            const contextWindow = Number(value);
            if (!isNaN(contextWindow) && contextWindow > 0) {
                updates.chunk_size = calculateChunkSize(contextWindow);
            }
        }

        setFormData((prev) => {
            if (!prev) return prev;
            return {
                ...prev,
                [section]: {
                    ...prev[section as keyof FormData],
                    ...updates
                }
            } as FormData;
        });
        setIsDirty(true);
        setMessage(null);
        // Clear test results if key fields change
        if (section === CONFIG_SECTIONS.EMBEDDING && (field === 'provider' || field === 'base_url' || field === 'model')) {
            setEmbeddingTestResult(null);
            setEmbeddingModels([]);
        }
        if (section === CONFIG_SECTIONS.SUMMARIZATION && (field === 'provider' || field === 'base_url' || field === 'model')) {
            setSumTestResult(null);
            setSummarizationModels([]);
        }
    }, []);

    const handleDiscoverEmbedding = async () => {
        if (!formData) return;
        setIsDiscoveringEmbedding(true);
        setEmbeddingTestResult(null);
        try {
            const res = await listProviderModels(
                formData.embedding.provider,
                formData.embedding.base_url
            ) as { success: boolean; models?: ModelOption[]; error?: string };
            if (res.success && res.models) {
                setEmbeddingModels(res.models);
                if (res.models.length === 0) {
                    setEmbeddingTestResult({ success: false, error: "No models found. Pull a model first." });
                }
            } else {
                setEmbeddingTestResult({ success: false, error: res.error || 'Discovery failed' });
            }
        } catch (e: unknown) {
            const message = e instanceof Error ? e.message : 'Unknown error';
            setEmbeddingTestResult({ success: false, error: message });
        } finally {
            setIsDiscoveringEmbedding(false);
        }
    };

    const handleModelSelect = useCallback((modelName: string) => {
        const model = embeddingModels.find(m => m.name === modelName);
        // Only use values from API if available - don't guess with heuristics
        // User should click Test & Detect to get accurate values
        const dimensions = model?.dimensions || "";
        const context = model?.context_window || "";
        // Only calculate chunk_size if we have a real context value
        const chunkSize = context ? calculateChunkSize(Number(context)) : "";

        setFormData((prev) => {
            if (!prev) return prev;
            return {
                ...prev,
                [CONFIG_SECTIONS.EMBEDDING]: {
                    ...prev.embedding,
                    model: modelName,
                    dimensions: dimensions,
                    max_tokens: context,
                    chunk_size: chunkSize
                }
            };
        });
        setIsDirty(true);
        // Clear previous test result since model changed
        setEmbeddingTestResult(null);
    }, [embeddingModels]);

    const handleTestEmbedding = async () => {
        if (!formData) return;
        setIsTestingEmbedding(true);
        try {
            const res = await testEmbeddingConfig(formData.embedding) as TestResultData;
            setEmbeddingTestResult(res);
            if (res.success) {
                // Only update values that come back from the API
                const updates: Partial<EmbeddingFormData> = {};
                if (res.dimensions) {
                    updates.dimensions = res.dimensions;
                }
                if (res.context_window) {
                    updates.max_tokens = res.context_window;
                    // Auto-calculate chunk_size using standard percentage
                    updates.chunk_size = calculateChunkSize(res.context_window);
                }

                if (Object.keys(updates).length > 0) {
                    setFormData((prev) => {
                        if (!prev) return prev;
                        return {
                            ...prev,
                            [CONFIG_SECTIONS.EMBEDDING]: {
                                ...prev.embedding,
                                ...updates
                            }
                        };
                    });
                    setIsDirty(true);
                }
            }
        } catch (e: unknown) {
            const message = e instanceof Error ? e.message : 'Unknown error';
            setEmbeddingTestResult({ success: false, error: message });
        } finally {
            setIsTestingEmbedding(false);
        }
    };

    const handleDiscoverSum = async () => {
        if (!formData) return;
        setIsDiscoveringSum(true);
        setSumTestResult(null);
        try {
            const res = await listSummarizationModels(
                formData.summarization.provider,
                formData.summarization.base_url
            ) as { success: boolean; models?: ModelOption[]; error?: string };
            if (res.success && res.models) {
                setSummarizationModels(res.models);
            } else {
                setSumTestResult({ success: false, error: res.error || 'Discovery failed' });
            }
        } catch (e: unknown) {
            const message = e instanceof Error ? e.message : 'Unknown error';
            setSumTestResult({ success: false, error: message });
        } finally {
            setIsDiscoveringSum(false);
        }
    };

    const handleSumModelSelect = useCallback((modelName: string) => {
        const model = summarizationModels.find(m => m.id === modelName);
        // Only use context_window from API if available - don't guess with heuristics
        // User should click Test & Detect to get accurate values
        const context = model?.context_window || "";

        setFormData((prev) => {
            if (!prev) return prev;
            return {
                ...prev,
                [CONFIG_SECTIONS.SUMMARIZATION]: {
                    ...prev.summarization,
                    model: modelName,
                    max_tokens: context
                }
            };
        });
        setIsDirty(true);
        // Clear previous test result since model changed
        setSumTestResult(null);
    }, [summarizationModels]);

    const handleTestSum = async () => {
        if (!formData) return;
        setIsTestingSum(true);
        try {
            const res = await testSummarizationConfig(formData.summarization) as TestResultData;
            setSumTestResult(res);

            // Only populate context window from API - no heuristics
            if (res.success) {
                let detectedContext: number | null = null;

                // First check if the test API returned context_window
                if (res.context_window) {
                    detectedContext = res.context_window;
                }

                // Then check if the discovered model has context_window
                if (!detectedContext) {
                    const model = summarizationModels.find(m => m.id === formData.summarization.model);
                    if (model?.context_window) {
                        detectedContext = model.context_window;
                    }
                }

                // Only update if we got a real value from API
                if (detectedContext) {
                    setFormData((prev) => {
                        if (!prev) return prev;
                        return {
                            ...prev,
                            [CONFIG_SECTIONS.SUMMARIZATION]: {
                                ...prev.summarization,
                                max_tokens: detectedContext
                            }
                        };
                    });
                    setIsDirty(true);
                }
            }

        } catch (e: unknown) {
            const message = e instanceof Error ? e.message : 'Unknown error';
            setSumTestResult({ success: false, error: message });
        } finally {
            setIsTestingSum(false);
        }
    };

    const handleSave = async () => {
        if (!formData) return;
        try {
            const emb = formData.embedding;
            const sum = formData.summarization;
            const rot = formData.log_rotation;
            const sq = formData.session_quality;

            // Transform UI field names back to API field names
            const apiPayload = {
                [CONFIG_SECTIONS.EMBEDDING]: {
                    provider: emb.provider,
                    model: emb.model,
                    base_url: emb.base_url,
                    dimensions: toApiNumber(emb.dimensions),
                    // UI uses max_tokens/chunk_size, API expects context_tokens/max_chunk_chars
                    context_tokens: toApiNumber(emb.max_tokens),
                    max_chunk_chars: toApiNumber(emb.chunk_size),
                },
                [CONFIG_SECTIONS.SUMMARIZATION]: {
                    enabled: sum.enabled,
                    provider: sum.provider,
                    model: sum.model,
                    base_url: sum.base_url,
                    // UI uses max_tokens, API expects context_tokens
                    context_tokens: toApiNumber(sum.max_tokens),
                },
                log_rotation: {
                    enabled: rot.enabled,
                    max_size_mb: rot.max_size_mb,
                    backup_count: rot.backup_count,
                },
                session_quality: {
                    min_activities: sq.min_activities,
                    stale_timeout_seconds: sq.stale_timeout_seconds,
                },
            };
            const result = await updateConfig.mutateAsync(apiPayload) as { message?: string };
            setMessage({ type: 'success', text: result.message || "Configuration saved." });
            setIsDirty(false);
            setEmbeddingTestResult(null); // Clear transient test states
            setSumTestResult(null);
        } catch (err: unknown) {
            const message = err instanceof Error ? err.message : "Failed to save configuration.";
            setMessage({ type: 'error', text: message });
        }
    };

    if (isLoading || !formData) return <div className="p-8 flex items-center justify-center"><Loader2 className="animate-spin mr-2" /> Loading config...</div>;

    return (
        <div className="space-y-6 max-w-4xl mx-auto pb-12">
            <div className="flex flex-col gap-2">
                <h1 className="text-3xl font-bold tracking-tight">Configuration</h1>
                <p className="text-muted-foreground">Manage embedding providers, summarization, and system settings.</p>
            </div>

            {message && (
                <div className={cn("p-4 rounded-md flex items-center gap-2", message.type === 'success' ? "bg-green-500/10 text-green-600" : "bg-red-500/10 text-red-600")}>
                    {message.type === 'error' && <AlertCircle className="w-4 h-4" />}
                    {message.text}
                </div>
            )}

            {/* Setup Guidance Banner - Show only after discovery completes with no models found */}
            {embeddingDiscoveryComplete && embeddingModels.length === 0 && !embeddingTestResult?.success && (
                <Card className="border-yellow-500/50 bg-yellow-500/5">
                    <CardContent className="py-4">
                        <div className="flex items-start gap-4">
                            <AlertTriangle className="w-5 h-5 text-yellow-500 flex-shrink-0 mt-0.5" />
                            <div className="flex-1 space-y-2">
                                <div className="font-medium text-yellow-500">No embedding models detected</div>
                                <p className="text-sm text-muted-foreground">
                                    Codebase Intelligence requires an embedding model to index your code. Set up Ollama or LM Studio to get started.
                                </p>
                                <Link to="/help">
                                    <Button variant="outline" size="sm" className="gap-2 mt-2">
                                        View Setup Guide
                                        <ArrowRight className="w-4 h-4" />
                                    </Button>
                                </Link>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Embedding Section */}
            <Card>
                <CardHeader>
                    <div className="flex items-center justify-between">
                        <div>
                            <div className="flex items-center gap-2">
                                <CardTitle>Embedding Settings</CardTitle>
                                <OriginBadge origin={config?.origins?.embedding} />
                            </div>
                            <CardDescription>
                                Configure the model used for semantic search code indexing.
                                {" "}<Link to="/help" className="inline-flex items-center gap-1 text-primary hover:underline"><BookOpen className="h-3 w-3" />Setup Guide</Link>
                            </CardDescription>
                        </div>
                        <ReadyBadge show={embeddingValidation.isValid} />
                    </div>
                </CardHeader>
                <CardContent className="space-y-6">
                    {/* Step 1: Provider & Connect */}
                    <div className="space-y-3">
                        <StepHeader
                            step={1}
                            title="Connect to Provider"
                            isComplete={Boolean(formData[CONFIG_SECTIONS.EMBEDDING].provider && formData[CONFIG_SECTIONS.EMBEDDING].base_url)}
                        />
                        <div className="grid grid-cols-2 gap-4 pl-7">
                            <div className="space-y-2">
                                <Label>Provider</Label>
                                <ProviderSelect
                                    value={formData[CONFIG_SECTIONS.EMBEDDING].provider}
                                    onChange={(provider) => {
                                        handleChange(CONFIG_SECTIONS.EMBEDDING, "provider", provider);
                                    }}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>Base URL</Label>
                                <UrlInputWithRefresh
                                    value={formData[CONFIG_SECTIONS.EMBEDDING].base_url}
                                    onChange={(url) => handleChange(CONFIG_SECTIONS.EMBEDDING, "base_url", url)}
                                    onRefresh={handleDiscoverEmbedding}
                                    isRefreshing={isDiscoveringEmbedding}
                                />
                            </div>
                        </div>
                    </div>

                    {/* Step 2: Select Model */}
                    <div className="space-y-3">
                        <StepHeader
                            step={2}
                            title="Select Model"
                            isComplete={Boolean(formData[CONFIG_SECTIONS.EMBEDDING].model)}
                        />
                        <div className="pl-7">
                            <ModelSelect
                                value={formData[CONFIG_SECTIONS.EMBEDDING].model}
                                models={embeddingModels}
                                onChange={(modelId) => handleModelSelect(modelId)}
                                placeholder={DEFAULT_EMBEDDING_MODEL_PLACEHOLDER}
                                showDimensions
                                helpText={embeddingModels.length === 0
                                    ? "Models will auto-load. Click refresh if discovery fails."
                                    : "Select a model from the dropdown."}
                            />
                        </div>
                    </div>

                    {/* Step 3: Test & Configure */}
                    <div className="space-y-3">
                        <StepHeader
                            step={3}
                            title="Test & Configure"
                            isComplete={Boolean(embeddingTestResult?.success)}
                        />
                        <div className="pl-7 grid grid-cols-2 gap-4 bg-muted/30 p-4 rounded-md border border-dashed">
                            <div className="space-y-2">
                                <Label>Dimensions</Label>
                                <Input
                                    type="number"
                                    value={formData[CONFIG_SECTIONS.EMBEDDING].dimensions || ''}
                                    onChange={(e) => {
                                        const val = e.target.value;
                                        handleChange(CONFIG_SECTIONS.EMBEDDING, "dimensions", val === '' ? '' : parseInt(val, 10) || '');
                                    }}
                                    placeholder={DEFAULT_DIMENSIONS_PLACEHOLDER}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>Chunk Size</Label>
                                <Input
                                    type="number"
                                    value={formData[CONFIG_SECTIONS.EMBEDDING].chunk_size || ''}
                                    onChange={(e) => {
                                        const val = e.target.value;
                                        handleChange(CONFIG_SECTIONS.EMBEDDING, "chunk_size", val === '' ? '' : parseInt(val, 10) || '');
                                    }}
                                    placeholder={DEFAULT_CHUNK_SIZE_PLACEHOLDER}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>Context Window</Label>
                                <ContextWindowInput
                                    value={formData[CONFIG_SECTIONS.EMBEDDING].max_tokens || ''}
                                    onChange={(value) => handleChange(CONFIG_SECTIONS.EMBEDDING, "max_tokens", value)}
                                    placeholder={DEFAULT_CONTEXT_WINDOW_PLACEHOLDER}
                                    presets={EMBEDDING_CONTEXT_PRESETS}
                                />
                            </div>
                            <div className="space-y-2">
                                <div className="h-full flex items-end">
                                    <TestButton
                                        onClick={handleTestEmbedding}
                                        isTesting={isTestingEmbedding}
                                        disabled={!formData[CONFIG_SECTIONS.EMBEDDING].model}
                                    />
                                </div>
                            </div>
                            <p className="col-span-2 text-xs text-muted-foreground">
                                Click Test & Detect to auto-fill dimensions. Select a common context window or enter manually.
                            </p>
                            <TestResult result={embeddingTestResult} />
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Summarization Section */}
            <Card>
                <CardHeader>
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <input
                                type="checkbox"
                                id="sum_enabled"
                                checked={formData[CONFIG_SECTIONS.SUMMARIZATION].enabled}
                                onChange={(e) => handleChange(CONFIG_SECTIONS.SUMMARIZATION, "enabled", e.target.checked)}
                                className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                            />
                            <div>
                                <div className="flex items-center gap-2">
                                    <CardTitle>Summarization</CardTitle>
                                    <OriginBadge origin={config?.origins?.summarization} />
                                </div>
                                <CardDescription>
                                    Enable LLM-powered activity summarization.
                                    {" "}<Link to="/help" className="inline-flex items-center gap-1 text-primary hover:underline"><BookOpen className="h-3 w-3" />Model recommendations</Link>
                                </CardDescription>
                            </div>
                        </div>
                        <ReadyBadge show={formData[CONFIG_SECTIONS.SUMMARIZATION].enabled && summarizationValidation.isValid} />
                    </div>
                </CardHeader>
                <CardContent className={cn("space-y-6 transition-all", !formData[CONFIG_SECTIONS.SUMMARIZATION].enabled && "opacity-50 pointer-events-none")}>
                    {/* Step 1: Provider & Connect */}
                    <div className="space-y-3">
                        <StepHeader
                            step={1}
                            title="Connect to Provider"
                            isComplete={Boolean(formData[CONFIG_SECTIONS.SUMMARIZATION].provider && formData[CONFIG_SECTIONS.SUMMARIZATION].base_url)}
                        />
                        <div className="grid grid-cols-2 gap-4 pl-7">
                            <div className="space-y-2">
                                <Label>Provider</Label>
                                <ProviderSelect
                                    value={formData[CONFIG_SECTIONS.SUMMARIZATION].provider}
                                    onChange={(provider) => {
                                        handleChange(CONFIG_SECTIONS.SUMMARIZATION, "provider", provider);
                                    }}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>Base URL</Label>
                                <UrlInputWithRefresh
                                    value={formData[CONFIG_SECTIONS.SUMMARIZATION].base_url}
                                    onChange={(url) => handleChange(CONFIG_SECTIONS.SUMMARIZATION, "base_url", url)}
                                    onRefresh={handleDiscoverSum}
                                    isRefreshing={isDiscoveringSum}
                                />
                            </div>
                        </div>
                    </div>

                    {/* Step 2: Select Model */}
                    <div className="space-y-3">
                        <StepHeader
                            step={2}
                            title="Select Model"
                            isComplete={Boolean(formData[CONFIG_SECTIONS.SUMMARIZATION].model)}
                        />
                        <div className="pl-7">
                            <ModelSelect
                                value={formData[CONFIG_SECTIONS.SUMMARIZATION].model}
                                models={summarizationModels}
                                onChange={(modelId) => handleSumModelSelect(modelId)}
                                placeholder={DEFAULT_SUMMARIZATION_MODEL_PLACEHOLDER}
                                helpText={summarizationModels.length === 0
                                    ? "Models will auto-load. Click refresh if discovery fails."
                                    : "Select a model from the dropdown."}
                            />
                        </div>
                    </div>

                    {/* Step 3: Test & Configure */}
                    <div className="space-y-3">
                        <StepHeader
                            step={3}
                            title="Test & Configure"
                            isComplete={Boolean(sumTestResult?.success)}
                        />
                        <div className="pl-7 grid grid-cols-2 gap-4 bg-muted/30 p-4 rounded-md border border-dashed">
                            <div className="space-y-2">
                                <Label>Context Window</Label>
                                <ContextWindowInput
                                    value={formData[CONFIG_SECTIONS.SUMMARIZATION].max_tokens || ''}
                                    onChange={(value) => handleChange(CONFIG_SECTIONS.SUMMARIZATION, "max_tokens", value)}
                                    placeholder={LARGE_CONTEXT_WINDOW_PLACEHOLDER}
                                    presets={LLM_CONTEXT_PRESETS}
                                />
                            </div>
                            <div className="space-y-2">
                                <div className="h-full flex items-end">
                                    <TestButton
                                        onClick={handleTestSum}
                                        isTesting={isTestingSum}
                                        disabled={!formData[CONFIG_SECTIONS.SUMMARIZATION].model}
                                    />
                                </div>
                            </div>
                            <p className="col-span-2 text-xs text-muted-foreground">
                                Click Test & Detect to verify connection. Select a common context window or enter manually.
                            </p>
                            <TestResult result={sumTestResult} />
                        </div>
                    </div>
                </CardContent>
                <CardFooter className="bg-muted/30 py-4 flex flex-col gap-3 border-t">
                    {/* Validation Status - show errors and warnings */}
                    {isDirty && (
                        !embeddingValidation.isValid ||
                        !summarizationValidation.isValid ||
                        embeddingValidation.warnings.length > 0 ||
                        summarizationValidation.warnings.length > 0
                    ) && (
                        <div className="w-full text-sm space-y-1">
                            {embeddingValidation.errors.length > 0 && (
                                <div className="text-amber-600 flex items-start gap-2">
                                    <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                                    <span><strong>Embedding:</strong> {embeddingValidation.errors[0]}</span>
                                </div>
                            )}
                            {embeddingValidation.warnings.length > 0 && embeddingValidation.isValid && (
                                <div className="text-yellow-600 flex items-start gap-2">
                                    <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                                    <span><strong>Embedding:</strong> {embeddingValidation.warnings[0]}</span>
                                </div>
                            )}
                            {summarizationValidation.isEnabled && summarizationValidation.errors.length > 0 && (
                                <div className="text-amber-600 flex items-start gap-2">
                                    <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                                    <span><strong>Summarization:</strong> {summarizationValidation.errors[0]}</span>
                                </div>
                            )}
                            {summarizationValidation.isEnabled && summarizationValidation.warnings.length > 0 && summarizationValidation.isValid && (
                                <div className="text-yellow-600 flex items-start gap-2">
                                    <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                                    <span><strong>Summarization:</strong> {summarizationValidation.warnings[0]}</span>
                                </div>
                            )}
                        </div>
                    )}
                    <div className="w-full flex justify-end">
                        <Button onClick={handleSave} disabled={!canSave || updateConfig.isPending} size="lg" className="shadow-lg">
                            {updateConfig.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                            <Save className="mr-2 h-4 w-4" /> Save Configuration
                        </Button>
                    </div>
                </CardFooter>
            </Card>

            {/* Session Quality Section */}
            <Card>
                <CardHeader>
                    <div className="flex items-center gap-2">
                        <CardTitle>Session Quality</CardTitle>
                        <OriginBadge origin={config?.origins?.session_quality} />
                    </div>
                    <CardDescription>Configure thresholds for session quality and cleanup behavior.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <Label>Minimum Activities</Label>
                            <Input
                                type="number"
                                min={SESSION_QUALITY_LIMITS.MIN_ACTIVITY_THRESHOLD}
                                max={SESSION_QUALITY_LIMITS.MAX_ACTIVITY_THRESHOLD}
                                value={formData.session_quality?.min_activities ?? SESSION_QUALITY_DEFAULTS.MIN_ACTIVITIES}
                                onChange={(e) => {
                                    const value = parseInt(e.target.value, 10) || SESSION_QUALITY_DEFAULTS.MIN_ACTIVITIES;
                                    setFormData((prev) => {
                                        if (!prev) return prev;
                                        return {
                                            ...prev,
                                            session_quality: {
                                                ...prev.session_quality,
                                                min_activities: Math.min(Math.max(value, SESSION_QUALITY_LIMITS.MIN_ACTIVITY_THRESHOLD), SESSION_QUALITY_LIMITS.MAX_ACTIVITY_THRESHOLD),
                                            },
                                        };
                                    });
                                    setIsDirty(true);
                                }}
                            />
                            <p className="text-xs text-muted-foreground">
                                Sessions with fewer tool calls are not titled, summarized, or embedded.
                                Range: {SESSION_QUALITY_LIMITS.MIN_ACTIVITY_THRESHOLD}-{SESSION_QUALITY_LIMITS.MAX_ACTIVITY_THRESHOLD}
                            </p>
                        </div>
                        <div className="space-y-2">
                            <Label>Stale Timeout (seconds)</Label>
                            <Input
                                type="number"
                                min={SESSION_QUALITY_LIMITS.MIN_STALE_TIMEOUT}
                                max={SESSION_QUALITY_LIMITS.MAX_STALE_TIMEOUT}
                                value={formData.session_quality?.stale_timeout_seconds ?? SESSION_QUALITY_DEFAULTS.STALE_TIMEOUT_SECONDS}
                                onChange={(e) => {
                                    const value = parseInt(e.target.value, 10) || SESSION_QUALITY_DEFAULTS.STALE_TIMEOUT_SECONDS;
                                    setFormData((prev) => {
                                        if (!prev) return prev;
                                        return {
                                            ...prev,
                                            session_quality: {
                                                ...prev.session_quality,
                                                stale_timeout_seconds: Math.min(Math.max(value, SESSION_QUALITY_LIMITS.MIN_STALE_TIMEOUT), SESSION_QUALITY_LIMITS.MAX_STALE_TIMEOUT),
                                            },
                                        };
                                    });
                                    setIsDirty(true);
                                }}
                            />
                            <p className="text-xs text-muted-foreground">
                                Sessions inactive longer than this are auto-completed or deleted.
                                Currently: {formatStaleTimeout(formData.session_quality?.stale_timeout_seconds ?? SESSION_QUALITY_DEFAULTS.STALE_TIMEOUT_SECONDS)}
                            </p>
                        </div>
                    </div>

                    <div className="flex items-center gap-2 text-sm text-muted-foreground bg-muted/30 p-3 rounded-md">
                        <AlertCircle className="h-4 w-4" />
                        <span>
                            Sessions below the quality threshold are deleted during stale recovery.
                            Quality sessions are marked completed for summarization.
                        </span>
                    </div>
                </CardContent>
                <CardFooter className="bg-muted/30 py-3 border-t flex items-center justify-between">
                    <p className="text-xs text-muted-foreground">
                        Changes take effect immediately for new sessions.
                    </p>
                    <Button onClick={handleSave} disabled={!isDirty || updateConfig.isPending} size="sm">
                        {updateConfig.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        <Save className="mr-2 h-4 w-4" /> Save
                    </Button>
                </CardFooter>
            </Card>

            {/* Logging Section */}
            <Card>
                <CardHeader>
                    <div className="flex items-center gap-2">
                        <CardTitle>Logging</CardTitle>
                        <OriginBadge origin={config?.origins?.log_rotation} />
                    </div>
                    <CardDescription>Configure log file rotation to prevent unbounded disk usage.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="flex items-center gap-3">
                        <input
                            type="checkbox"
                            id="log_rotation_enabled"
                            checked={formData.log_rotation?.enabled ?? true}
                            onChange={(e) => {
                                setFormData((prev) => {
                                    if (!prev) return prev;
                                    return {
                                        ...prev,
                                        log_rotation: {
                                            ...prev.log_rotation,
                                            enabled: e.target.checked,
                                        },
                                    };
                                });
                                setIsDirty(true);
                            }}
                            className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                        />
                        <Label htmlFor="log_rotation_enabled">Enable log rotation</Label>
                    </div>

                    <div className={cn("grid grid-cols-2 gap-4", !formData.log_rotation?.enabled && "opacity-50 pointer-events-none")}>
                        <div className="space-y-2">
                            <Label>Max File Size (MB)</Label>
                            <Input
                                type="number"
                                min={LOG_ROTATION_LIMITS.MIN_SIZE_MB}
                                max={LOG_ROTATION_LIMITS.MAX_SIZE_MB}
                                value={formData.log_rotation?.max_size_mb ?? LOG_ROTATION_DEFAULTS.MAX_SIZE_MB}
                                onChange={(e) => {
                                    const value = parseInt(e.target.value, 10) || LOG_ROTATION_DEFAULTS.MAX_SIZE_MB;
                                    setFormData((prev) => {
                                        if (!prev) return prev;
                                        return {
                                            ...prev,
                                            log_rotation: {
                                                ...prev.log_rotation,
                                                max_size_mb: Math.min(Math.max(value, LOG_ROTATION_LIMITS.MIN_SIZE_MB), LOG_ROTATION_LIMITS.MAX_SIZE_MB),
                                            },
                                        };
                                    });
                                    setIsDirty(true);
                                }}
                            />
                            <p className="text-xs text-muted-foreground">
                                Rotate when file exceeds this size ({LOG_ROTATION_LIMITS.MIN_SIZE_MB}-{LOG_ROTATION_LIMITS.MAX_SIZE_MB} MB)
                            </p>
                        </div>
                        <div className="space-y-2">
                            <Label>Backup Count</Label>
                            <Input
                                type="number"
                                min={0}
                                max={LOG_ROTATION_LIMITS.MAX_BACKUP_COUNT}
                                value={formData.log_rotation?.backup_count ?? LOG_ROTATION_DEFAULTS.BACKUP_COUNT}
                                onChange={(e) => {
                                    const value = parseInt(e.target.value, 10) || 0;
                                    setFormData((prev) => {
                                        if (!prev) return prev;
                                        return {
                                            ...prev,
                                            log_rotation: {
                                                ...prev.log_rotation,
                                                backup_count: Math.min(Math.max(value, 0), LOG_ROTATION_LIMITS.MAX_BACKUP_COUNT),
                                            },
                                        };
                                    });
                                    setIsDirty(true);
                                }}
                            />
                            <p className="text-xs text-muted-foreground">
                                Keep up to {LOG_ROTATION_LIMITS.MAX_BACKUP_COUNT} backup files (daemon.log.1, .2, etc.)
                            </p>
                        </div>
                    </div>

                    {formData.log_rotation?.enabled && (
                        <div className="flex items-center gap-2 text-sm text-muted-foreground bg-muted/30 p-3 rounded-md">
                            <AlertCircle className="h-4 w-4" />
                            <span>
                                Max disk usage: {calculateMaxLogDiskUsage(
                                    formData.log_rotation?.max_size_mb ?? LOG_ROTATION_DEFAULTS.MAX_SIZE_MB,
                                    formData.log_rotation?.backup_count ?? LOG_ROTATION_DEFAULTS.BACKUP_COUNT
                                )} MB
                                ({formData.log_rotation?.max_size_mb ?? LOG_ROTATION_DEFAULTS.MAX_SIZE_MB} MB × {1 + (formData.log_rotation?.backup_count ?? LOG_ROTATION_DEFAULTS.BACKUP_COUNT)} files)
                            </span>
                        </div>
                    )}
                </CardContent>
                <CardFooter className="bg-muted/30 py-3 border-t flex items-center justify-between">
                    <p className="text-xs text-muted-foreground">
                        Requires daemon restart to take effect.
                    </p>
                    <Button onClick={handleSave} disabled={!isDirty || updateConfig.isPending} size="sm">
                        {updateConfig.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        <Save className="mr-2 h-4 w-4" /> Save
                    </Button>
                </CardFooter>
            </Card>

            {/* Exclusions Section */}
            <ExclusionsCard />
        </div>
    )
}

// =============================================================================
// Exclusions Management Component
// =============================================================================

function ExclusionsCard() {
    const queryClient = useQueryClient();
    const { data: exclusions, isLoading } = useExclusions();
    const updateExclusions = useUpdateExclusions();

    const [newPattern, setNewPattern] = useState("");
    const [isResetting, setIsResetting] = useState(false);
    const [isApplying, setIsApplying] = useState(false);
    const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);

    // After updating exclusions, restart daemon to apply changes and trigger re-index
    const applyExclusionChanges = async () => {
        setIsApplying(true);
        try {
            const result: RestartResponse = await restartDaemon();
            // Invalidate status to refresh dashboard stats
            queryClient.invalidateQueries({ queryKey: ["status"] });
            if (result.indexing_started) {
                setMessage({ type: 'success', text: "Re-indexing with updated exclusions..." });
            }
        } catch (e) {
            console.error("Failed to apply changes:", e);
        } finally {
            setIsApplying(false);
        }
    };

    const handleAddPattern = async () => {
        if (!newPattern.trim()) return;
        try {
            const result = await updateExclusions.mutateAsync({ add: [newPattern.trim()] }) as ExclusionsUpdateResponse;
            setNewPattern("");
            if (result.added?.length && result.added.length > 0) {
                setMessage({ type: 'success', text: `Added: ${result.added.join(", ")}. Applying changes...` });
                // Trigger restart to apply exclusions and re-index
                await applyExclusionChanges();
            } else if (result.already_exists?.length && result.already_exists.length > 0) {
                setMessage({ type: 'error', text: `Already excluded: ${result.already_exists.join(", ")}` });
            }
        } catch (e) {
            const errorMessage = e instanceof Error ? e.message : "Unknown error";
            setMessage({ type: 'error', text: errorMessage });
        }
    };

    const handleRemovePattern = async (pattern: string) => {
        try {
            await updateExclusions.mutateAsync({ remove: [pattern] });
            setMessage({ type: 'success', text: `Removed: ${pattern}. Applying changes...` });
            // Trigger restart to apply exclusions and re-index
            await applyExclusionChanges();
        } catch (e) {
            const errorMessage = e instanceof Error ? e.message : "Unknown error";
            setMessage({ type: 'error', text: errorMessage });
        }
    };

    const handleReset = async () => {
        setIsResetting(true);
        try {
            await resetExclusions();
            queryClient.invalidateQueries({ queryKey: ["exclusions"] });
            setMessage({ type: 'success', text: "Reset to defaults. Applying changes..." });
            // Trigger restart to apply exclusions and re-index
            await applyExclusionChanges();
        } catch (e) {
            const errorMessage = e instanceof Error ? e.message : "Unknown error";
            setMessage({ type: 'error', text: errorMessage });
        } finally {
            setIsResetting(false);
        }
    };

    if (isLoading) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <FolderX className="h-5 w-5" />
                        Directory Exclusions
                    </CardTitle>
                </CardHeader>
                <CardContent className="flex items-center justify-center p-8">
                    <Loader2 className="animate-spin" />
                </CardContent>
            </Card>
        );
    }

    return (
        <Card>
            <CardHeader>
                <div className="flex items-center justify-between">
                    <div>
                        <CardTitle className="flex items-center gap-2">
                            <FolderX className="h-5 w-5" />
                            Directory Exclusions
                        </CardTitle>
                        <CardDescription>
                            Exclude directories and files from indexing. Changes are applied automatically.
                        </CardDescription>
                    </div>
                    <Button variant="outline" size="sm" onClick={handleReset} disabled={isResetting || isApplying}>
                        {(isResetting || isApplying) ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />}
                        <span className="ml-2">{isApplying ? "Applying..." : "Reset"}</span>
                    </Button>
                </div>
            </CardHeader>
            <CardContent className="space-y-4">
                {message && (
                    <div className={cn(
                        "p-3 rounded-md text-sm flex items-center gap-2",
                        message.type === 'success' ? "bg-green-500/10 text-green-600" : "bg-red-500/10 text-red-600"
                    )}>
                        {message.type === 'success' ? <CheckCircle2 className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
                        {message.text}
                    </div>
                )}

                {/* Add new pattern */}
                <div className="flex gap-2">
                    <input
                        type="text"
                        value={newPattern}
                        onChange={(e) => setNewPattern(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && handleAddPattern()}
                        placeholder="e.g., vendor, tmp/*, *.log"
                        className="flex-1 h-10 rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                    />
                    <Button onClick={handleAddPattern} disabled={!newPattern.trim() || updateExclusions.isPending || isApplying}>
                        {(updateExclusions.isPending || isApplying) ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                        <span className="ml-2">{isApplying ? "Applying..." : "Add"}</span>
                    </Button>
                </div>

                {/* User patterns */}
                {exclusions?.user_patterns && exclusions.user_patterns.length > 0 && (
                    <div className="space-y-2">
                        <h4 className="text-sm font-medium">Your Exclusions</h4>
                        <div className="flex flex-wrap gap-2">
                            {exclusions.user_patterns.map((pattern) => (
                                <span
                                    key={pattern}
                                    className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-primary/10 text-primary text-sm"
                                >
                                    {pattern}
                                    <button
                                        onClick={() => handleRemovePattern(pattern)}
                                        className="ml-1 hover:text-destructive"
                                    >
                                        <X className="h-3 w-3" />
                                    </button>
                                </span>
                            ))}
                        </div>
                    </div>
                )}

                {/* Default patterns (collapsible) */}
                <details className="group">
                    <summary className="cursor-pointer text-sm text-muted-foreground hover:text-foreground">
                        Built-in exclusions ({exclusions?.default_patterns?.length || 0} patterns)
                    </summary>
                    <div className="mt-2 flex flex-wrap gap-1">
                        {exclusions?.default_patterns?.map((pattern) => (
                            <span
                                key={pattern}
                                className="inline-flex items-center px-2 py-0.5 rounded bg-muted text-muted-foreground text-xs"
                            >
                                {pattern}
                            </span>
                        ))}
                    </div>
                </details>

                <p className="text-xs text-muted-foreground">
                    Pattern format: <code>dirname</code> matches anywhere, <code>dirname/**</code> includes subdirs,
                    <code>*.log</code> matches file extensions.
                </p>
            </CardContent>
        </Card>
    );
}
