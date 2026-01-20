import { useState, useEffect } from "react";
import { useConfig, useUpdateConfig, useExclusions, useUpdateExclusions, resetExclusions, restartDaemon, listProviderModels, listSummarizationModels, testEmbeddingConfig, testSummarizationConfig } from "@/hooks/use-config";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { AlertCircle, Save, Loader2, CheckCircle2, RotateCw, Plug, Plus, X, RotateCcw, FolderX } from "lucide-react";
import { cn } from "@/lib/utils";
import { useQueryClient } from "@tanstack/react-query";

// Simple Label/Input helpers
const Label = ({ children, className }: any) => (
    <label className={cn("text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70", className)}>
        {children}
    </label>
);

const Input = ({ className, ...props }: any) => (
    <input className={cn("flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50", className)} {...props} />
);

const Select = ({ className, children, ...props }: any) => (
    <select className={cn("flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50", className)} {...props}>
        {children}
    </select>
);

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
            } else if (chunk > context * 0.9) {
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
            const urlDefaults: Record<string, string> = {
                ollama: 'http://localhost:11434',
                lmstudio: 'http://localhost:1234',
                openai: 'http://localhost:1234',
            };
            if (urlDefaults[value]) {
                updates.base_url = urlDefaults[value];
            }
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
        if (section === 'embedding' && (field === 'provider' || field === 'base_url' || field === 'model')) {
            setEmbeddingTestResult(null);
            setEmbeddingModels([]);
        }
        if (section === 'summarization' && (field === 'provider' || field === 'base_url' || field === 'model')) {
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
        const chunkSize = context ? Math.floor(Number(context) * 0.8) : "";

        setFormData((prev: any) => ({
            ...prev,
            embedding: {
                ...prev.embedding,
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
            const res = await testEmbeddingConfig(formData.embedding) as any;
            setEmbeddingTestResult(res);
            if (res.success) {
                // Only update values that come back from the API
                const updates: any = {};
                if (res.dimensions) {
                    updates.dimensions = res.dimensions;
                }
                if (res.context_window) {
                    updates.max_tokens = res.context_window;
                    // Auto-calculate chunk_size as 80% of context
                    updates.chunk_size = Math.floor(res.context_window * 0.8);
                }

                if (Object.keys(updates).length > 0) {
                    setFormData((prev: any) => ({
                        ...prev,
                        embedding: {
                            ...prev.embedding,
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
            summarization: {
                ...prev.summarization,
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
            const res = await testSummarizationConfig(formData.summarization) as any;
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
                    setFormData((prev: any) => ({
                        ...prev,
                        summarization: {
                            ...prev.summarization,
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
            // Helper to convert UI field values to API-safe values
            // Empty string, NaN, or undefined become null; valid numbers pass through
            const toApiNumber = (value: any): number | null => {
                if (value === "" || value === undefined || value === null) return null;
                const num = typeof value === "number" ? value : parseInt(value, 10);
                return isNaN(num) ? null : num;
            };

            // Debug: log what we're about to save
            console.log("[Config Save] formData.summarization.max_tokens:", formData.summarization.max_tokens, typeof formData.summarization.max_tokens);
            console.log("[Config Save] toApiNumber result:", toApiNumber(formData.summarization.max_tokens));

            // Transform UI field names back to API field names
            const apiPayload = {
                embedding: {
                    provider: formData.embedding.provider,
                    model: formData.embedding.model,
                    base_url: formData.embedding.base_url,
                    dimensions: toApiNumber(formData.embedding.dimensions),
                    // UI uses max_tokens/chunk_size, API expects context_tokens/max_chunk_chars
                    context_tokens: toApiNumber(formData.embedding.max_tokens),
                    max_chunk_chars: toApiNumber(formData.embedding.chunk_size),
                },
                summarization: {
                    enabled: formData.summarization.enabled,
                    provider: formData.summarization.provider,
                    model: formData.summarization.model,
                    base_url: formData.summarization.base_url,
                    // UI uses max_tokens, API expects context_tokens
                    context_tokens: toApiNumber(formData.summarization.max_tokens),
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
                        {embeddingValidation.isValid && (
                            <div className="flex items-center gap-2 text-green-600">
                                <CheckCircle2 className="h-5 w-5" />
                                <span className="text-sm font-medium">Ready</span>
                            </div>
                        )}
                    </div>
                </CardHeader>
                <CardContent className="space-y-6">
                    {/* Step 1: Provider & Connect */}
                    <div className="space-y-3">
                        <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                            <span className={cn(
                                "flex items-center justify-center w-5 h-5 rounded-full text-xs",
                                (formData.embedding.provider && formData.embedding.base_url) ? "bg-green-600 text-white" : "bg-muted-foreground/20"
                            )}>1</span>
                            Connect to Provider
                        </div>
                        <div className="grid grid-cols-2 gap-4 pl-7">
                            <div className="space-y-2">
                                <Label>Provider</Label>
                                <Select
                                    value={formData.embedding.provider}
                                    onChange={(e: any) => handleChange("embedding", "provider", e.target.value)}
                                >
                                    <option value="ollama">Ollama</option>
                                    <option value="lmstudio">LM Studio</option>
                                    <option value="openai">OpenAI Compatible</option>
                                </Select>
                            </div>
                            <div className="space-y-2">
                                <Label>Base URL</Label>
                                <div className="flex gap-2">
                                    <Input
                                        value={formData.embedding.base_url}
                                        onChange={(e: any) => handleChange("embedding", "base_url", e.target.value)}
                                        placeholder="http://localhost:11434"
                                    />
                                    <Button variant="outline" size="icon" onClick={handleDiscoverEmbedding} title="Load Models">
                                        {isDiscoveringEmbedding ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCw className="h-4 w-4" />}
                                    </Button>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Step 2: Select Model */}
                    <div className="space-y-3">
                        <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                            <span className={cn(
                                "flex items-center justify-center w-5 h-5 rounded-full text-xs",
                                formData.embedding.model ? "bg-green-600 text-white" : "bg-muted-foreground/20"
                            )}>2</span>
                            Select Model
                        </div>
                        <div className="pl-7 space-y-2">
                            {embeddingModels.length > 0 ? (
                                <Select
                                    value={formData.embedding.model}
                                    onChange={(e: any) => handleModelSelect(e.target.value)}
                                >
                                    <option value="" disabled>Select a model...</option>
                                    {embeddingModels.map(m => (
                                        <option key={m.name} value={m.name}>
                                            {m.name} ({m.dimensions} dims) - {m.provider}
                                        </option>
                                    ))}
                                </Select>
                            ) : (
                                <Input
                                    value={formData.embedding.model}
                                    onChange={(e: any) => handleChange("embedding", "model", e.target.value)}
                                    placeholder="e.g. nomic-embed-text"
                                />
                            )}
                            <p className="text-xs text-muted-foreground">
                                {embeddingModels.length === 0 ? "Models will auto-load. Click refresh if discovery fails." : "Select a model from the dropdown."}
                            </p>
                        </div>
                    </div>

                    {/* Step 3: Test & Configure */}
                    <div className="space-y-3">
                        <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                            <span className={cn(
                                "flex items-center justify-center w-5 h-5 rounded-full text-xs",
                                embeddingTestResult?.success ? "bg-green-600 text-white" : "bg-muted-foreground/20"
                            )}>3</span>
                            Test & Configure
                        </div>
                        <div className="pl-7 grid grid-cols-2 gap-4 bg-muted/30 p-4 rounded-md border border-dashed">
                            <div className="space-y-2">
                                <Label>Dimensions</Label>
                                <Input
                                    type="number"
                                    value={formData.embedding.dimensions || ''}
                                    onChange={(e: any) => handleChange("embedding", "dimensions", parseInt(e.target.value))}
                                    placeholder="Auto-detect"
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>Chunk Size</Label>
                                <Input
                                    type="number"
                                    value={formData.embedding.chunk_size || ''}
                                    onChange={(e: any) => handleChange("embedding", "chunk_size", parseInt(e.target.value))}
                                    placeholder="e.g. 512"
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>Context Window</Label>
                                <Input
                                    type="number"
                                    value={formData.embedding.max_tokens || ''}
                                    onChange={(e: any) => handleChange("embedding", "max_tokens", parseInt(e.target.value))}
                                    placeholder="e.g. 8192"
                                />
                            </div>
                            <div className="space-y-2">
                                <div className="h-full flex items-end">
                                    <Button
                                        variant="secondary"
                                        className="w-full"
                                        onClick={handleTestEmbedding}
                                        disabled={isTestingEmbedding || !formData.embedding.model}
                                    >
                                        {isTestingEmbedding ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plug className="mr-2 h-4 w-4" />}
                                        Test & Detect
                                    </Button>
                                </div>
                            </div>
                            <p className="col-span-2 text-xs text-muted-foreground">
                                Click Test & Detect to auto-fill dimensions. If context window isn't detected, enter it manually.
                            </p>
                            {embeddingTestResult && (
                                <div className={cn(
                                    "col-span-2 text-sm p-3 rounded flex items-start gap-2",
                                    embeddingTestResult.success && embeddingTestResult.pending_load ? "bg-yellow-500/10 text-yellow-700" :
                                    embeddingTestResult.success ? "bg-green-500/10 text-green-700" : "bg-red-500/10 text-red-700"
                                )}>
                                    {embeddingTestResult.success ? <CheckCircle2 className="w-4 h-4 mt-0.5" /> : <AlertCircle className="w-4 h-4 mt-0.5" />}
                                    <div>
                                        <p className="font-medium">
                                            {embeddingTestResult.success && embeddingTestResult.pending_load ? "Configuration Valid" :
                                             embeddingTestResult.success ? "Connection Successful" : "Test Failed"}
                                        </p>
                                        <p>{embeddingTestResult.success ? embeddingTestResult.message : embeddingTestResult.error}</p>
                                        {embeddingTestResult.suggestion && <p className="mt-1 font-semibold">{embeddingTestResult.suggestion}</p>}
                                    </div>
                                </div>
                            )}
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
                                checked={formData.summarization.enabled}
                                onChange={(e) => handleChange("summarization", "enabled", e.target.checked)}
                                className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                            />
                            <div>
                                <CardTitle>Summarization</CardTitle>
                                <CardDescription>Enable LLM-powered activity summarization (optional).</CardDescription>
                            </div>
                        </div>
                        {formData.summarization.enabled && summarizationValidation.isValid && (
                            <div className="flex items-center gap-2 text-green-600">
                                <CheckCircle2 className="h-5 w-5" />
                                <span className="text-sm font-medium">Ready</span>
                            </div>
                        )}
                    </div>
                </CardHeader>
                <CardContent className={cn("space-y-6 transition-all", !formData.summarization.enabled && "opacity-50 pointer-events-none")}>
                    {/* Step 1: Provider & Connect */}
                    <div className="space-y-3">
                        <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                            <span className={cn(
                                "flex items-center justify-center w-5 h-5 rounded-full text-xs",
                                (formData.summarization.provider && formData.summarization.base_url) ? "bg-green-600 text-white" : "bg-muted-foreground/20"
                            )}>1</span>
                            Connect to Provider
                        </div>
                        <div className="grid grid-cols-2 gap-4 pl-7">
                            <div className="space-y-2">
                                <Label>Provider</Label>
                                <Select
                                    value={formData.summarization.provider}
                                    onChange={(e: any) => handleChange("summarization", "provider", e.target.value)}
                                >
                                    <option value="ollama">Ollama</option>
                                    <option value="lmstudio">LM Studio</option>
                                    <option value="openai">OpenAI Compatible</option>
                                </Select>
                            </div>
                            <div className="space-y-2">
                                <Label>Base URL</Label>
                                <div className="flex gap-2">
                                    <Input
                                        value={formData.summarization.base_url}
                                        onChange={(e: any) => handleChange("summarization", "base_url", e.target.value)}
                                    />
                                    <Button variant="outline" size="icon" onClick={handleDiscoverSum} title="Load Models">
                                        {isDiscoveringSum ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCw className="h-4 w-4" />}
                                    </Button>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Step 2: Select Model */}
                    <div className="space-y-3">
                        <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                            <span className={cn(
                                "flex items-center justify-center w-5 h-5 rounded-full text-xs",
                                formData.summarization.model ? "bg-green-600 text-white" : "bg-muted-foreground/20"
                            )}>2</span>
                            Select Model
                        </div>
                        <div className="pl-7 space-y-2">
                            {summarizationModels.length > 0 ? (
                                <Select
                                    value={formData.summarization.model}
                                    onChange={(e: any) => handleSumModelSelect(e.target.value)}
                                >
                                    <option value="" disabled>Select a model...</option>
                                    {summarizationModels.map(m => (
                                        <option key={m.id} value={m.id}>
                                            {m.name}
                                        </option>
                                    ))}
                                </Select>
                            ) : (
                                <Input
                                    value={formData.summarization.model}
                                    onChange={(e: any) => handleChange("summarization", "model", e.target.value)}
                                    placeholder="e.g. qwen2.5:3b"
                                />
                            )}
                            <p className="text-xs text-muted-foreground">
                                {summarizationModels.length === 0 ? "Models will auto-load. Click refresh if discovery fails." : "Select a model from the dropdown."}
                            </p>
                        </div>
                    </div>

                    {/* Step 3: Test & Configure */}
                    <div className="space-y-3">
                        <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                            <span className={cn(
                                "flex items-center justify-center w-5 h-5 rounded-full text-xs",
                                sumTestResult?.success ? "bg-green-600 text-white" : "bg-muted-foreground/20"
                            )}>3</span>
                            Test & Configure
                        </div>
                        <div className="pl-7 grid grid-cols-2 gap-4 bg-muted/30 p-4 rounded-md border border-dashed">
                            <div className="space-y-2">
                                <Label>Context Window</Label>
                                <Input
                                    type="number"
                                    value={formData.summarization.max_tokens || ''}
                                    onChange={(e: any) => handleChange("summarization", "max_tokens", parseInt(e.target.value))}
                                    placeholder="e.g. 32768"
                                />
                            </div>
                            <div className="space-y-2">
                                <div className="h-full flex items-end">
                                    <Button
                                        variant="secondary"
                                        className="w-full"
                                        onClick={handleTestSum}
                                        disabled={isTestingSum || !formData.summarization.model}
                                    >
                                        {isTestingSum ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plug className="mr-2 h-4 w-4" />}
                                        Test & Detect
                                    </Button>
                                </div>
                            </div>
                            <p className="col-span-2 text-xs text-muted-foreground">
                                Click Test & Detect to verify connection. If context window isn't detected, enter it manually.
                            </p>
                            {sumTestResult && (
                                <div className={cn(
                                    "col-span-2 text-sm p-3 rounded flex items-start gap-2",
                                    sumTestResult.success ? "bg-green-500/10 text-green-700" : "bg-red-500/10 text-red-700"
                                )}>
                                    {sumTestResult.success ? <CheckCircle2 className="w-4 h-4 mt-0.5" /> : <AlertCircle className="w-4 h-4 mt-0.5" />}
                                    <div>
                                        <p className="font-medium">
                                        {sumTestResult.success ? "Connection Successful" : "Test Failed"}
                                    </p>
                                    <p>{sumTestResult.success ? sumTestResult.message || "LLM is accessible" : sumTestResult.error}</p>
                                </div>
                            </div>
                        )}
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
