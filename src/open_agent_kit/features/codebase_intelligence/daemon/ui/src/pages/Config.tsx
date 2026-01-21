import { useState, useEffect } from "react";
import { useConfig, useUpdateConfig, useExclusions, useUpdateExclusions, resetExclusions, restartDaemon, listProviderModels, listSummarizationModels, testEmbeddingConfig, testSummarizationConfig } from "@/hooks/use-config";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { AlertCircle, Save, Loader2, CheckCircle2, Plus, X, RotateCcw, FolderX } from "lucide-react";
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
    getDefaultProviderUrl,
    calculateChunkSize,
    toApiNumber,
} from "@/lib/constants";

export default function Config() {
    const { data: config, isLoading } = useConfig();
    const updateConfig = useUpdateConfig();

    const [formData, setFormData] = useState<any>(null);
    const [isDirty, setIsDirty] = useState(false);
    const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);

    // Discovery State
    const [embeddingModels, setEmbeddingModels] = useState<any[]>([]);
    const [isDiscoveringEmbedding, setIsDiscoveringEmbedding] = useState(false);
    const [isTestingEmbedding, setIsTestingEmbedding] = useState(false);
    const [embeddingTestResult, setEmbeddingTestResult] = useState<any>(null);

    const [summarizationModels, setSummarizationModels] = useState<any[]>([]);
    const [isDiscoveringSum, setIsDiscoveringSum] = useState(false);
    const [isTestingSum, setIsTestingSum] = useState(false);
    const [sumTestResult, setSumTestResult] = useState<any>(null);

    // =============================================================================
    // Validation Logic for Guided Flow
    // =============================================================================

    // Check if embedding config is valid and complete
    const getEmbeddingValidation = () => {
        const errors: string[] = [];
        const emb = formData?.embedding;
        if (!emb) return { isValid: false, errors: ["Loading..."], warnings: [] };

        // Required fields
        if (!emb.provider) errors.push("Select a provider");
        if (!emb.base_url) errors.push("Enter a base URL");
        if (!emb.model) errors.push("Select a model");
        if (!emb.dimensions) errors.push("Dimensions required (click Test & Detect)");
        if (!emb.max_tokens) errors.push("Context window required (click Test & Detect or enter manually)");
        if (!emb.chunk_size) errors.push("Chunk size required");

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

        // Test requirement
        if (!embeddingTestResult?.success) {
            errors.push("Run Test & Detect to verify configuration");
        }

        return { isValid: errors.length === 0, errors, warnings };
    };

    // Check if summarization config is valid (only if enabled)
    const getSummarizationValidation = () => {
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

        // Test requirement when enabled
        if (!sumTestResult?.success) {
            errors.push("Run Test & Detect to verify configuration");
        }

        return { isValid: errors.length === 0, errors, warnings, isEnabled: true };
    };

    // Combined validation for save button
    const embeddingValidation = getEmbeddingValidation();
    const summarizationValidation = getSummarizationValidation();
    const canSave = isDirty && embeddingValidation.isValid && summarizationValidation.isValid;

    // Track if we've done initial model discovery
    const [initialLoadComplete, setInitialLoadComplete] = useState(false);

    useEffect(() => {
        // Don't overwrite user's pending changes if they have unsaved edits
        if (config && !isDirty) {
            // Debug: log what we received from API
            console.log("[Config Load] API returned summarization.context_tokens:", config.summarization.context_tokens);

            // Map API response keys to UI state keys
            const mappedData = JSON.parse(JSON.stringify(config));

            // Embedding mapping - always initialize to prevent undefined values
            // These use UI field names (max_tokens, chunk_size) mapped from API names (context_tokens, max_chunk_chars)
            mappedData.embedding.max_tokens = config.embedding.context_tokens ?? "";
            mappedData.embedding.chunk_size = config.embedding.max_chunk_chars ?? "";

            // Summarization mapping - always initialize
            mappedData.summarization.max_tokens = config.summarization.context_tokens ?? "";

            console.log("[Config Load] Mapped to summarization.max_tokens:", mappedData.summarization.max_tokens);
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
                    .then((res: any) => {
                        if (res.success && res.models) {
                            setEmbeddingModels(res.models);
                        }
                    })
                    .catch(() => { /* silently fail - user can manually refresh */ });
            }

            // Auto-discover summarization models if enabled and provider/URL are configured
            if (config.summarization?.enabled && config.summarization?.provider && config.summarization?.base_url) {
                listSummarizationModels(config.summarization.provider, config.summarization.base_url)
                    .then((res: any) => {
                        if (res.success && res.models) {
                            setSummarizationModels(res.models);
                        }
                    })
                    .catch(() => { /* silently fail - user can manually refresh */ });
            }
        }
    }, [config, initialLoadComplete]);

    const handleChange = (section: string, field: string, value: any) => {
        // Auto-update base URL when provider changes (embedding or summarization)
        let updates: any = { [field]: value };
        if (field === 'provider') {
            updates.base_url = getDefaultProviderUrl(value);
            // Clear model when provider changes
            updates.model = '';
        }

        setFormData((prev: any) => ({
            ...prev,
            [section]: {
                ...prev[section],
                ...updates
            }
        }));
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
    };

    const handleDiscoverEmbedding = async () => {
        setIsDiscoveringEmbedding(true);
        setEmbeddingTestResult(null);
        try {
            const res = await listProviderModels(
                formData.embedding.provider,
                formData.embedding.base_url
            ) as any;
            if (res.success) {
                setEmbeddingModels(res.models);
                if (res.models.length === 0) {
                    setEmbeddingTestResult({ success: false, error: "No models found. Pull a model first." });
                }
            } else {
                setEmbeddingTestResult({ success: false, error: res.error });
            }
        } catch (e: any) {
            setEmbeddingTestResult({ success: false, error: e.message });
        } finally {
            setIsDiscoveringEmbedding(false);
        }
    };

    const handleModelSelect = (modelName: string) => {
        const model = embeddingModels.find(m => m.name === modelName);
        // Only use values from API if available - don't guess with heuristics
        // User should click Test & Detect to get accurate values
        const dimensions = model?.dimensions || "";
        const context = model?.context_window || "";
        // Only calculate chunk_size if we have a real context value
        const chunkSize = context ? calculateChunkSize(Number(context)) : "";

        setFormData((prev: any) => ({
            ...prev,
            [CONFIG_SECTIONS.EMBEDDING]: {
                ...prev[CONFIG_SECTIONS.EMBEDDING],
                model: modelName,
                dimensions: dimensions,
                max_tokens: context,
                chunk_size: chunkSize
            }
        }));
        setIsDirty(true);
        // Clear previous test result since model changed
        setEmbeddingTestResult(null);
    };

    const handleTestEmbedding = async () => {
        setIsTestingEmbedding(true);
        try {
            const res = await testEmbeddingConfig(formData[CONFIG_SECTIONS.EMBEDDING]) as any;
            setEmbeddingTestResult(res);
            if (res.success) {
                // Only update values that come back from the API
                const updates: any = {};
                if (res.dimensions) {
                    updates.dimensions = res.dimensions;
                }
                if (res.context_window) {
                    updates.max_tokens = res.context_window;
                    // Auto-calculate chunk_size using standard percentage
                    updates.chunk_size = calculateChunkSize(res.context_window);
                }

                if (Object.keys(updates).length > 0) {
                    setFormData((prev: any) => ({
                        ...prev,
                        [CONFIG_SECTIONS.EMBEDDING]: {
                            ...prev[CONFIG_SECTIONS.EMBEDDING],
                            ...updates
                        }
                    }));
                    setIsDirty(true);
                }
            }
        } catch (e: any) {
            setEmbeddingTestResult({ success: false, error: e.message });
        } finally {
            setIsTestingEmbedding(false);
        }
    };

    const handleDiscoverSum = async () => {
        setIsDiscoveringSum(true);
        setSumTestResult(null);
        try {
            const res = await listSummarizationModels(
                formData.summarization.provider,
                formData.summarization.base_url
            ) as any;
            if (res.success) {
                setSummarizationModels(res.models);
            } else {
                setSumTestResult({ success: false, error: res.error });
            }
        } catch (e: any) {
            setSumTestResult({ success: false, error: e.message });
        } finally {
            setIsDiscoveringSum(false);
        }
    };

    const handleSumModelSelect = (modelName: string) => {
        const model = summarizationModels.find(m => m.id === modelName);
        // Only use context_window from API if available - don't guess with heuristics
        // User should click Test & Detect to get accurate values
        const context = model?.context_window || "";

        setFormData((prev: any) => ({
            ...prev,
            [CONFIG_SECTIONS.SUMMARIZATION]: {
                ...prev[CONFIG_SECTIONS.SUMMARIZATION],
                model: modelName,
                max_tokens: context
            }
        }));
        setIsDirty(true);
        // Clear previous test result since model changed
        setSumTestResult(null);
    }

    const handleTestSum = async () => {
        setIsTestingSum(true);
        try {
            const res = await testSummarizationConfig(formData[CONFIG_SECTIONS.SUMMARIZATION]) as any;
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
                    const model = summarizationModels.find(m => m.id === formData[CONFIG_SECTIONS.SUMMARIZATION].model);
                    if (model?.context_window) {
                        detectedContext = model.context_window;
                    }
                }

                // Only update if we got a real value from API
                if (detectedContext) {
                    setFormData((prev: any) => ({
                        ...prev,
                        [CONFIG_SECTIONS.SUMMARIZATION]: {
                            ...prev[CONFIG_SECTIONS.SUMMARIZATION],
                            max_tokens: detectedContext
                        }
                    }));
                    setIsDirty(true);
                }
            }

        } catch (e: any) {
            setSumTestResult({ success: false, error: e.message });
        } finally {
            setIsTestingSum(false);
        }
    };

    const handleSave = async () => {
        try {
            const emb = formData[CONFIG_SECTIONS.EMBEDDING];
            const sum = formData[CONFIG_SECTIONS.SUMMARIZATION];

            // Debug: log what we're about to save
            console.log("[Config Save] formData.summarization.max_tokens:", sum.max_tokens, typeof sum.max_tokens);
            console.log("[Config Save] toApiNumber result:", toApiNumber(sum.max_tokens));

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
            };
            console.log("[Config Save] Sending apiPayload:", JSON.stringify(apiPayload, null, 2));
            const result = await updateConfig.mutateAsync(apiPayload) as any;
            console.log("[Config Save] API response:", JSON.stringify(result, null, 2));
            setMessage({ type: 'success', text: result.message || "Configuration saved." });
            setIsDirty(false);
            setEmbeddingTestResult(null); // Clear transient test states
            setSumTestResult(null);
        } catch (err: any) {
            setMessage({ type: 'error', text: err.message || "Failed to save configuration." });
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

            {/* Embedding Section */}
            <Card>
                <CardHeader>
                    <div className="flex items-center justify-between">
                        <div>
                            <CardTitle>Embedding Settings</CardTitle>
                            <CardDescription>Configure the model used for semantic search code indexing.</CardDescription>
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
                                    onChange={(e: any) => handleChange(CONFIG_SECTIONS.EMBEDDING, "dimensions", parseInt(e.target.value))}
                                    placeholder={DEFAULT_DIMENSIONS_PLACEHOLDER}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>Chunk Size</Label>
                                <Input
                                    type="number"
                                    value={formData[CONFIG_SECTIONS.EMBEDDING].chunk_size || ''}
                                    onChange={(e: any) => handleChange(CONFIG_SECTIONS.EMBEDDING, "chunk_size", parseInt(e.target.value))}
                                    placeholder={DEFAULT_CHUNK_SIZE_PLACEHOLDER}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>Context Window</Label>
                                <Input
                                    type="number"
                                    value={formData[CONFIG_SECTIONS.EMBEDDING].max_tokens || ''}
                                    onChange={(e: any) => handleChange(CONFIG_SECTIONS.EMBEDDING, "max_tokens", parseInt(e.target.value))}
                                    placeholder={DEFAULT_CONTEXT_WINDOW_PLACEHOLDER}
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
                                Click Test & Detect to auto-fill dimensions. If context window isn't detected, enter it manually.
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
                                <CardTitle>Summarization</CardTitle>
                                <CardDescription>Enable LLM-powered activity summarization (optional).</CardDescription>
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
                                <Input
                                    type="number"
                                    value={formData[CONFIG_SECTIONS.SUMMARIZATION].max_tokens || ''}
                                    onChange={(e: any) => handleChange(CONFIG_SECTIONS.SUMMARIZATION, "max_tokens", parseInt(e.target.value))}
                                    placeholder={LARGE_CONTEXT_WINDOW_PLACEHOLDER}
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
                                Click Test & Detect to verify connection. If context window isn't detected, enter it manually.
                            </p>
                            <TestResult result={sumTestResult} />
                        </div>
                    </div>
                </CardContent>
                <CardFooter className="bg-muted/30 py-4 flex flex-col gap-3 sticky bottom-0 z-10 border-t">
                    {/* Validation Status */}
                    {isDirty && (!embeddingValidation.isValid || !summarizationValidation.isValid) && (
                        <div className="w-full text-sm space-y-1">
                            {embeddingValidation.errors.length > 0 && (
                                <div className="text-amber-600 flex items-start gap-2">
                                    <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                                    <span><strong>Embedding:</strong> {embeddingValidation.errors[0]}</span>
                                </div>
                            )}
                            {embeddingValidation.warnings.length > 0 && (
                                <div className="text-yellow-600 flex items-start gap-2">
                                    <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                                    <span>{embeddingValidation.warnings[0]}</span>
                                </div>
                            )}
                            {summarizationValidation.isEnabled && summarizationValidation.errors.length > 0 && (
                                <div className="text-amber-600 flex items-start gap-2">
                                    <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                                    <span><strong>Summarization:</strong> {summarizationValidation.errors[0]}</span>
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
            const result = await restartDaemon() as any;
            // Invalidate status to refresh dashboard stats
            queryClient.invalidateQueries({ queryKey: ["status"] });
            if (result.indexing_started) {
                setMessage({ type: 'success', text: "Re-indexing with updated exclusions..." });
            }
        } catch (e: any) {
            console.error("Failed to apply changes:", e);
        } finally {
            setIsApplying(false);
        }
    };

    const handleAddPattern = async () => {
        if (!newPattern.trim()) return;
        try {
            const result = await updateExclusions.mutateAsync({ add: [newPattern.trim()] }) as any;
            setNewPattern("");
            if (result.added?.length > 0) {
                setMessage({ type: 'success', text: `Added: ${result.added.join(", ")}. Applying changes...` });
                // Trigger restart to apply exclusions and re-index
                await applyExclusionChanges();
            } else if (result.already_exists?.length > 0) {
                setMessage({ type: 'error', text: `Already excluded: ${result.already_exists.join(", ")}` });
            }
        } catch (e: any) {
            setMessage({ type: 'error', text: e.message });
        }
    };

    const handleRemovePattern = async (pattern: string) => {
        try {
            await updateExclusions.mutateAsync({ remove: [pattern] });
            setMessage({ type: 'success', text: `Removed: ${pattern}. Applying changes...` });
            // Trigger restart to apply exclusions and re-index
            await applyExclusionChanges();
        } catch (e: any) {
            setMessage({ type: 'error', text: e.message });
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
        } catch (e: any) {
            setMessage({ type: 'error', text: e.message });
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
