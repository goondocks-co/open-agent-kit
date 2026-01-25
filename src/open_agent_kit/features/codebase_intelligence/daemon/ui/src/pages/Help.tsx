import { useState } from "react";
import { Link } from "react-router-dom";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Copy, Check, ExternalLink, Terminal } from "lucide-react";
import { cn } from "@/lib/utils";

// =============================================================================
// Copy Button Component
// =============================================================================

interface CopyButtonProps {
    text: string;
    className?: string;
}

function CopyButton({ text, className }: CopyButtonProps) {
    const [copied, setCopied] = useState(false);

    const handleCopy = async () => {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <Button
            variant="ghost"
            size="sm"
            onClick={handleCopy}
            className={cn("h-8 w-8 p-0", className)}
        >
            {copied ? (
                <Check className="h-4 w-4 text-green-500" />
            ) : (
                <Copy className="h-4 w-4" />
            )}
        </Button>
    );
}

// =============================================================================
// Command Block Component
// =============================================================================

interface CommandBlockProps {
    command: string;
    label?: string;
}

function CommandBlock({ command, label }: CommandBlockProps) {
    return (
        <div className="relative group">
            {label && (
                <div className="text-xs text-muted-foreground mb-1">{label}</div>
            )}
            <div className="flex items-center gap-2 bg-muted rounded-md px-4 py-3 font-mono text-sm">
                <Terminal className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                <code className="flex-1">{command}</code>
                <CopyButton text={command} className="opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>
        </div>
    );
}

// =============================================================================
// Help Page Component
// =============================================================================

export default function Help() {
    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center gap-4">
                <Link to="/config">
                    <Button variant="ghost" size="sm" className="gap-2">
                        <ArrowLeft className="h-4 w-4" />
                        Back to Config
                    </Button>
                </Link>
            </div>

            <div>
                <h1 className="text-3xl font-bold tracking-tight">Setup Guide</h1>
                <p className="text-muted-foreground mt-2">
                    Get Codebase Intelligence up and running with an embedding provider.
                </p>
            </div>

            {/* Ollama Setup (Recommended) */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        Ollama
                        <span className="text-xs bg-green-500/10 text-green-500 px-2 py-1 rounded-full font-normal">
                            Recommended
                        </span>
                    </CardTitle>
                    <CardDescription>
                        Free, local, and private. Runs entirely on your machine.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                    {/* Installation */}
                    <div className="space-y-3">
                        <h3 className="font-semibold">1. Install Ollama</h3>
                        <div className="space-y-2">
                            <CommandBlock
                                label="macOS (Homebrew)"
                                command="brew install ollama"
                            />
                            <CommandBlock
                                label="Linux"
                                command="curl -fsSL https://ollama.ai/install.sh | sh"
                            />
                            <div className="text-sm text-muted-foreground">
                                Windows: <a
                                    href="https://ollama.ai/download"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-primary hover:underline inline-flex items-center gap-1"
                                >
                                    Download from ollama.ai
                                    <ExternalLink className="h-3 w-3" />
                                </a>
                            </div>
                        </div>
                    </div>

                    {/* Start Ollama */}
                    <div className="space-y-3">
                        <h3 className="font-semibold">2. Start Ollama</h3>
                        <CommandBlock command="ollama serve" />
                        <p className="text-sm text-muted-foreground">
                            Or run the Ollama desktop app if installed.
                        </p>
                    </div>

                    {/* Pull Embedding Model */}
                    <div className="space-y-3">
                        <h3 className="font-semibold">3. Pull an Embedding Model</h3>
                        <CommandBlock
                            label="Recommended: nomic-embed-text"
                            command="ollama pull nomic-embed-text"
                        />
                        <p className="text-sm text-muted-foreground">
                            Other good options: <code className="bg-muted px-1 rounded">mxbai-embed-large</code>, <code className="bg-muted px-1 rounded">all-minilm</code>
                        </p>
                    </div>

                    {/* Configure */}
                    <div className="space-y-3">
                        <h3 className="font-semibold">4. Configure in Oak CI</h3>
                        <p className="text-sm text-muted-foreground">
                            Go to the <Link to="/config" className="text-primary hover:underline">Configuration page</Link>, select Ollama as your provider, and click "Refresh" to discover your models.
                        </p>
                    </div>
                </CardContent>
            </Card>

            {/* LM Studio Setup */}
            <Card>
                <CardHeader>
                    <CardTitle>LM Studio</CardTitle>
                    <CardDescription>
                        User-friendly desktop app for running local models.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                    <div className="space-y-3">
                        <h3 className="font-semibold">1. Download LM Studio</h3>
                        <p className="text-sm text-muted-foreground">
                            <a
                                href="https://lmstudio.ai"
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-primary hover:underline inline-flex items-center gap-1"
                            >
                                Download from lmstudio.ai
                                <ExternalLink className="h-3 w-3" />
                            </a>
                            {" "}- Available for macOS, Windows, and Linux.
                        </p>
                    </div>

                    <div className="space-y-3">
                        <h3 className="font-semibold">2. Download an Embedding Model</h3>
                        <p className="text-sm text-muted-foreground">
                            In LM Studio, go to the Discover tab and search for embedding models like <code className="bg-muted px-1 rounded">nomic-embed-text-v1.5</code>.
                        </p>
                    </div>

                    <div className="space-y-3">
                        <h3 className="font-semibold">3. Start the Local Server</h3>
                        <p className="text-sm text-muted-foreground">
                            Go to the Developer tab, load your embedding model, and start the server (default port: 1234).
                        </p>
                    </div>

                    <div className="space-y-3">
                        <h3 className="font-semibold">4. Configure in Oak CI</h3>
                        <p className="text-sm text-muted-foreground">
                            Select "LM Studio" as your provider on the <Link to="/config" className="text-primary hover:underline">Configuration page</Link> and set the base URL to <code className="bg-muted px-1 rounded">http://localhost:1234</code>.
                        </p>
                    </div>
                </CardContent>
            </Card>

            {/* OpenAI Compatible */}
            <Card>
                <CardHeader>
                    <CardTitle>OpenAI Compatible APIs</CardTitle>
                    <CardDescription>
                        Use any OpenAI-compatible embedding service.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <p className="text-sm text-muted-foreground">
                        Select "OpenAI Compatible" as your provider and configure the base URL and model name for your service. This works with:
                    </p>
                    <ul className="list-disc list-inside text-sm text-muted-foreground space-y-1">
                        <li>OpenAI API (api.openai.com)</li>
                        <li>Azure OpenAI</li>
                        <li>Together AI</li>
                        <li>Anyscale</li>
                        <li>Any other OpenAI-compatible endpoint</li>
                    </ul>
                </CardContent>
            </Card>

            {/* Troubleshooting */}
            <Card>
                <CardHeader>
                    <CardTitle>Troubleshooting</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div>
                        <h3 className="font-semibold text-sm">Connection refused</h3>
                        <p className="text-sm text-muted-foreground">
                            Make sure your embedding provider is running. For Ollama, run <code className="bg-muted px-1 rounded">ollama serve</code> or start the desktop app.
                        </p>
                    </div>
                    <div>
                        <h3 className="font-semibold text-sm">No models found</h3>
                        <p className="text-sm text-muted-foreground">
                            You need to pull/download a model first. For Ollama: <code className="bg-muted px-1 rounded">ollama pull nomic-embed-text</code>
                        </p>
                    </div>
                    <div>
                        <h3 className="font-semibold text-sm">Test & Detect fails</h3>
                        <p className="text-sm text-muted-foreground">
                            Verify your base URL is correct and the model supports embeddings. Some LLM-only models don't support the embeddings API.
                        </p>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
