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


    useEffect(() => {
        if (config) {
            // Map API response keys to UI state keys
            const mappedData = JSON.parse(JSON.stringify(config));

            // Embedding mapping
            if (config.embedding.max_chunk_chars) {
                mappedData.embedding.chunk_size = config.embedding.max_chunk_chars;
            }
            if (config.embedding.context_tokens) {
                mappedData.embedding.max_tokens = config.embedding.context_tokens;
            }

            // Summarization mapping
            if (config.summarization.context_tokens) {
                mappedData.summarization.max_tokens = config.summarization.context_tokens;
            } else {
                // Important: ensures the input doesn't show "undefined" or empty if API returns null
                mappedData.summarization.max_tokens = "";
            }

            setFormData(mappedData);
        }
    }, [config]);

    const handleChange = (section: string, field: string, value: any) => {
        setFormData((prev: any) => ({
            ...prev,
            [section]: {
                ...prev[section],
                [field]: value
            }
        }));
        setIsDirty(true);
        setMessage(null);
        // Clear test results if key fields change
        if (section === 'embedding' && (field === 'provider' || field === 'base_url' || field === 'model')) {
            setEmbeddingTestResult(null);
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

    // Heuristic helpers
    const getModelHeuristics = (modelName: string) => {
        const lower = modelName.toLowerCase();
        let context = 8192; // Default reasonable context
        let dims = 768;

        if (lower.includes("nomic")) { context = 8192; dims = 768; }
        else if (lower.includes("bge-m3")) { context = 8192; dims = 1024; }
        else if (lower.includes("mxbai")) { context = 512; dims = 1024; } // mxbai usually smaller context? actually it's 512 for large-v1
        else if (lower.includes("minilm")) { context = 512; dims = 384; }
        else if (lower.includes("snowflake")) { context = 512; dims = 1024; } // arctic-embed-l
        else if (lower.includes("ada")) { context = 8192; dims = 1536; }
        else if (lower.includes("large")) { dims = 1024; }

        return { context, dims };
    };

    const handleModelSelect = (modelName: string) => {
        const model = embeddingModels.find(m => m.name === modelName);
        let dimensions = model?.dimensions || 0;
        let context = 0;

        // Try to get from API model object if available (rare for OAI/Ollama embeddings)
        if (model?.context_window) {
            context = model.context_window;
        }

        // Fallback to heuristics if missing
        const heuristics = getModelHeuristics(modelName);
        if (!dimensions) dimensions = heuristics.dims;
        if (!context) context = heuristics.context;

        // Calculate safe chunk size (80% of context)
        const chunkSize = Math.floor(context * 0.8);

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
    };

    const handleTestEmbedding = async () => {
        setIsTestingEmbedding(true);
        try {
            const res = await testEmbeddingConfig(formData.embedding) as any;
            setEmbeddingTestResult(res);
            if (res.success && res.dimensions) {
                // Auto-update dimensions from test result
                const currentData = { ...formData.embedding, dimensions: res.dimensions };

                // If context/chunk are still default/empty, try to heuristic them base on model name
                if (!currentData.max_tokens || !currentData.chunk_size) {
                    const heuristics = getModelHeuristics(currentData.model);
                    if (!currentData.max_tokens) currentData.max_tokens = heuristics.context;
                    if (!currentData.chunk_size) currentData.chunk_size = Math.floor(heuristics.context * 0.8);
                }

                setFormData((prev: any) => ({
                    ...prev,
                    embedding: currentData
                }));
                setIsDirty(true);
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
        let context = model?.context_window || 0;

        if (!context) {
            // Heuristics for LLMs
            const lower = modelName.toLowerCase();
            if (lower.includes("llama3")) context = 8192;
            else if (lower.includes("qwen") || lower.includes("mistral")) context = 32768;
            else if (lower.includes("gpt-4")) context = 128000;
            else if (lower.includes("gpt-3.5")) context = 16385;
            else context = 4096; // old default
        }

        setFormData((prev: any) => ({
            ...prev,
            summarization: {
                ...prev.summarization,
                model: modelName,
                max_tokens: context
            }
        }));
        setIsDirty(true);
    }

    const handleTestSum = async () => {
        setIsTestingSum(true);
        try {
            const res = await testSummarizationConfig(formData.summarization) as any;
            setSumTestResult(res);

            // Auto-populate context window using heuristics ONLY if missing from test/discovery
            if (res.success && !formData.summarization.max_tokens) {
                // First check if the model object itself has a context_window (from discovery)
                const model = summarizationModels.find(m => m.id === formData.summarization.model);

                if (model?.context_window) {
                    setFormData((prev: any) => ({
                        ...prev,
                        summarization: {
                            ...prev.summarization,
                            max_tokens: model.context_window
                        }
                    }));
                } else {
                    // Fallback to heuristics
                    const lower = formData.summarization.model.toLowerCase();
                    let context = 4096; // safe default

                    if (lower.includes("llama3")) context = 8192;
                    else if (lower.includes("qwen") || lower.includes("mistral")) context = 32768;
                    else if (lower.includes("gpt-4")) context = 128000;
                    else if (lower.includes("gpt-3.5")) context = 16385;
                    else if (lower.includes("gpt-oss")) context = 131072; // specific fix

                    setFormData((prev: any) => ({
                        ...prev,
                        summarization: {
                            ...prev.summarization,
                            max_tokens: context
                        }
                    }));
                }
                setIsDirty(true);
            }

        } catch (e: any) {
            setSumTestResult({ success: false, error: e.message });
        } finally {
            setIsTestingSum(false);
        }
    };

    const handleSave = async () => {
        try {
            const result = await updateConfig.mutateAsync(formData) as any;
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
                    <CardTitle>Embedding Settings</CardTitle>
                    <CardDescription>Configure the model used for semantic search code indexing.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <Label>Provider</Label>
                            <Select
                                value={formData.embedding.provider}
                                onChange={(e: any) => handleChange("embedding", "provider", e.target.value)}
                            >
                                <option value="ollama">Ollama</option>
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

                    <div className="space-y-2">
                        <Label>Model Name</Label>
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
                            {embeddingModels.length === 0 ? "Click refresh icon to discover available models." : "Models loaded based on provider."}
                        </p>
                    </div>

                    <div className="grid grid-cols-2 gap-4 bg-muted/30 p-4 rounded-md border border-dashed">
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
                                    disabled={isTestingEmbedding}
                                >
                                    {isTestingEmbedding ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plug className="mr-2 h-4 w-4" />}
                                    Test & Detect
                                </Button>
                            </div>
                        </div>
                        {embeddingTestResult && (
                            <div className={cn("col-span-2 text-sm p-3 rounded flex items-start gap-2", embeddingTestResult.success ? "bg-green-500/10 text-green-700 from-green-50" : "bg-red-500/10 text-red-700")}>
                                {embeddingTestResult.success ? <CheckCircle2 className="w-4 h-4 mt-0.5" /> : <AlertCircle className="w-4 h-4 mt-0.5" />}
                                <div>
                                    <p className="font-medium">{embeddingTestResult.success ? "Connection Successful" : "Test Failed"}</p>
                                    <p>{embeddingTestResult.success ? embeddingTestResult.message : embeddingTestResult.error}</p>
                                    {embeddingTestResult.suggestion && <p className="mt-1 font-semibold">{embeddingTestResult.suggestion}</p>}
                                </div>
                            </div>
                        )}
                    </div>
                </CardContent>
            </Card>

            {/* Summarization Section */}
            <Card>
                <CardHeader>
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
                            <CardDescription>Enable LLM-powered activity summarization.</CardDescription>
                        </div>
                    </div>
                </CardHeader>
                <CardContent className={cn("space-y-6 transition-all", !formData.summarization.enabled && "opacity-50 pointer-events-none")}>
                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <Label>Provider</Label>
                            <Select
                                value={formData.summarization.provider}
                                onChange={(e: any) => handleChange("summarization", "provider", e.target.value)}
                            >
                                <option value="ollama">Ollama</option>
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

                    <div className="space-y-2">
                        <Label>Model Name</Label>
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
                    </div>

                    <div className="space-y-2">
                        <Label>Context Window</Label>
                        <Input
                            type="number"
                            value={formData.summarization.max_tokens || ''}
                            onChange={(e: any) => handleChange("summarization", "max_tokens", parseInt(e.target.value))}
                            placeholder="e.g. 32768"
                        />
                    </div>

                    <div className="flex justify-end">
                        <Button variant="secondary" size="sm" onClick={handleTestSum} disabled={isTestingSum}>
                            {isTestingSum ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plug className="mr-2 h-4 w-4" />}
                            Test LLM Connection
                        </Button>
                    </div>
                    {sumTestResult && (
                        <div className={cn("text-sm p-3 rounded flex items-start gap-2", sumTestResult.success ? "bg-green-500/10 text-green-700" : "bg-red-500/10 text-red-700")}>
                            {sumTestResult.success ? <CheckCircle2 className="w-4 h-4 mt-0.5" /> : <AlertCircle className="w-4 h-4 mt-0.5" />}
                            <div>{sumTestResult.success ? "LLM Connected Successfully" : sumTestResult.error}</div>
                        </div>
                    )}
                </CardContent>
                <CardFooter className="bg-muted/30 py-4 flex justify-end sticky bottom-0 z-10 border-t">
                    <Button onClick={handleSave} disabled={!isDirty || updateConfig.isPending} size="lg" className="shadow-lg">
                        {updateConfig.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        <Save className="mr-2 h-4 w-4" /> Save Configuration
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
