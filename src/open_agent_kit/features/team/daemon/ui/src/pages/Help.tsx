import { useState, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@oak/ui/components/ui/card";
import { ExternalLink, BookOpen, Wrench, Cloud } from "lucide-react";
import { cn } from "@/lib/utils";
import { CommandBlock } from "@oak/ui/components/ui/command-block";

// =============================================================================
// Tab Constants
// =============================================================================

const HELP_TABS = {
    SETUP: "setup",
    CLOUD_RELAY: "cloud-relay",
    TROUBLESHOOTING: "troubleshooting",
} as const;

type HelpTab = typeof HELP_TABS[keyof typeof HELP_TABS];

// =============================================================================
// Tab Button Component
// =============================================================================

interface TabButtonProps {
    active: boolean;
    onClick: () => void;
    icon: React.ReactNode;
    label: string;
}

function TabButton({ active, onClick, icon, label }: TabButtonProps) {
    return (
        <button
            onClick={onClick}
            className={cn(
                "flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors",
                active
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
            )}
        >
            {icon}
            {label}
        </button>
    );
}

// =============================================================================
// Performance Tuning Card (tabbed by platform)
// =============================================================================

const PLATFORMS = ["macOS", "Linux", "Windows"] as const;
type Platform = typeof PLATFORMS[number];

function PlatformTab({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
    return (
        <button
            onClick={onClick}
            className={cn(
                "px-3 py-1.5 text-xs font-medium rounded-md transition-colors",
                active
                    ? "bg-blue-600 text-white dark:bg-blue-500"
                    : "text-blue-700 dark:text-blue-300 hover:bg-blue-100 dark:hover:bg-blue-900/50"
            )}
        >
            {label}
        </button>
    );
}

function PerformanceTuningCard() {
    const [platform, setPlatform] = useState<Platform>("macOS");

    return (
        <div className="rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-950/30 p-4 space-y-3">
            <p className="text-sm font-medium text-blue-800 dark:text-blue-200">
                Performance Tuning
            </p>
            <p className="text-xs text-blue-700 dark:text-blue-300">
                Ollama defaults to a small context window (2–4K tokens) which can truncate longer code during summarization.
                OAK works well with 8K — large enough without wasting memory.
            </p>

            {/* Recommended variables */}
            <div className="space-y-1.5">
                <p className="text-xs font-medium text-blue-800 dark:text-blue-200">Recommended Settings</p>
                <div className="space-y-1 text-xs text-blue-700 dark:text-blue-300">
                    <p>
                        <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded">OLLAMA_CONTEXT_LENGTH=8192</code>{" "}
                        — 8K context for code summarization. 32K+ wastes memory with little benefit for OAK.
                    </p>
                    <p>
                        <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded">OLLAMA_KV_CACHE_TYPE=q8_0</code>{" "}
                        — Halves attention cache memory, letting you fit larger contexts or more models.
                    </p>
                    <p>
                        <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded">OLLAMA_FLASH_ATTENTION=1</code>{" "}
                        — Faster long-context inference. <strong>NVIDIA GPUs only</strong> (not needed on Apple Silicon).
                    </p>
                </div>
            </div>

            <div className="h-px bg-blue-200 dark:bg-blue-800" />

            {/* Platform tabs */}
            <div className="space-y-3">
                <div className="flex gap-1">
                    {PLATFORMS.map((p) => (
                        <PlatformTab key={p} label={p} active={platform === p} onClick={() => setPlatform(p)} />
                    ))}
                </div>

                {platform === "macOS" && (
                    <div className="space-y-3 text-xs text-blue-700 dark:text-blue-300">
                        <p>
                            Most Ollama installations on macOS run as a LaunchAgent — either from Homebrew or the desktop app.
                            Add these keys to the{" "}
                            <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded">EnvironmentVariables</code> dict in your
                            plist file:
                        </p>
                        <CommandBlock command={[
                            "<key>OLLAMA_CONTEXT_LENGTH</key>",
                            "<string>8192</string>",
                            "<key>OLLAMA_KV_CACHE_TYPE</key>",
                            "<string>q8_0</string>",
                        ].join("\n")} />
                        <p>
                            The plist is typically at{" "}
                            <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded">~/Library/LaunchAgents/com.user.ollama.plist</code>{" "}
                            or{" "}
                            <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded">~/Library/LaunchAgents/homebrew.mxcl.ollama.plist</code>{" "}
                            if installed via Homebrew. After editing, reload the service:
                        </p>
                        <CommandBlock command={[
                            "launchctl stop com.user.ollama",
                            "launchctl unload ~/Library/LaunchAgents/com.user.ollama.plist",
                            "launchctl load ~/Library/LaunchAgents/com.user.ollama.plist",
                            "launchctl start com.user.ollama",
                        ].join("\n")} />
                        <p>
                            Settings in the plist persist across reboots automatically.
                        </p>
                    </div>
                )}

                {platform === "Linux" && (
                    <div className="space-y-3 text-xs text-blue-700 dark:text-blue-300">
                        <p>
                            Ollama typically runs as a systemd service on Linux.
                            Create an override file to set the variables without editing the packaged unit:
                        </p>
                        <CommandBlock command="sudo systemctl edit ollama" />
                        <p>Add the following under <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded">[Service]</code>:</p>
                        <CommandBlock command={[
                            "[Service]",
                            'Environment="OLLAMA_CONTEXT_LENGTH=8192"',
                            'Environment="OLLAMA_KV_CACHE_TYPE=q8_0"',
                            'Environment="OLLAMA_FLASH_ATTENTION=1"',
                        ].join("\n")} />
                        <p>Then restart:</p>
                        <CommandBlock command="sudo systemctl restart ollama" />
                    </div>
                )}

                {platform === "Windows" && (
                    <div className="space-y-3 text-xs text-blue-700 dark:text-blue-300">
                        <p>
                            On Windows, set the environment variables system-wide via PowerShell (run as Administrator):
                        </p>
                        <CommandBlock command={[
                            "[System.Environment]::SetEnvironmentVariable('OLLAMA_CONTEXT_LENGTH', '8192', 'User')",
                            "[System.Environment]::SetEnvironmentVariable('OLLAMA_KV_CACHE_TYPE', 'q8_0', 'User')",
                            "[System.Environment]::SetEnvironmentVariable('OLLAMA_FLASH_ATTENTION', '1', 'User')",
                        ].join("\n")} />
                        <p>
                            Then restart the Ollama desktop app (or the Ollama service from Task Manager).
                            These persist across reboots. You can also set them through{" "}
                            <strong>System Settings → System → About → Advanced system settings → Environment Variables</strong>.
                        </p>
                    </div>
                )}
            </div>
        </div>
    );
}

// =============================================================================
// Setup Guide Tab Content
// =============================================================================

function SetupGuideContent() {
    return (
        <div className="space-y-6">
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
                        <p className="text-sm text-muted-foreground">
                            You need an embedding model to index your codebase. Pick one based on your needs:
                        </p>
                        <div className="space-y-3">
                            <div className="rounded-lg border p-3 space-y-2">
                                <div className="flex items-center gap-2">
                                    <span className="font-medium text-sm">nomic-embed-text</span>
                                    <span className="text-xs bg-green-500/10 text-green-500 px-2 py-0.5 rounded-full">
                                        Quick Start
                                    </span>
                                </div>
                                <p className="text-xs text-muted-foreground">
                                    768 dimensions, 2K context. Fast, lightweight, and a great default for most projects.
                                </p>
                                <CommandBlock command="ollama pull nomic-embed-text" />
                            </div>
                            <div className="rounded-lg border p-3 space-y-2">
                                <div className="flex items-center gap-2">
                                    <span className="font-medium text-sm">nomic-embed-code</span>
                                    <span className="text-xs bg-blue-500/10 text-blue-500 px-2 py-0.5 rounded-full">
                                        Best for Code
                                    </span>
                                </div>
                                <p className="text-xs text-muted-foreground">
                                    768 dimensions, 32K context. Trained specifically on source code — better results for code search and indexing.
                                </p>
                                <CommandBlock command="ollama pull manutic/nomic-embed-code" />
                            </div>
                            <div className="rounded-lg border p-3 space-y-2">
                                <div className="flex items-center gap-2">
                                    <span className="font-medium text-sm">bge-m3</span>
                                    <span className="text-xs bg-purple-500/10 text-purple-500 px-2 py-0.5 rounded-full">
                                        Higher Quality
                                    </span>
                                </div>
                                <p className="text-xs text-muted-foreground">
                                    1024 dimensions, 8K context. Larger model with stronger retrieval quality, especially for mixed code and prose.
                                </p>
                                <CommandBlock command="ollama pull bge-m3" />
                            </div>
                        </div>
                    </div>

                    {/* Summarization Model */}
                    <div className="space-y-3">
                        <h3 className="font-semibold">4. Pull a Summarization Model</h3>
                        <p className="text-sm text-muted-foreground">
                            A summarization model generates natural-language summaries of your coding sessions. Pick one based on your available RAM:
                        </p>
                        <div className="space-y-3">
                            <div className="rounded-lg border p-3 space-y-2">
                                <div className="flex items-center gap-2">
                                    <span className="font-medium text-sm">gpt-oss-20b</span>
                                    <span className="text-xs bg-green-500/10 text-green-500 px-2 py-0.5 rounded-full">
                                        Recommended
                                    </span>
                                </div>
                                <p className="text-xs text-muted-foreground">
                                    128K context. Strong summarization quality. Recommend ~36 GB+ RAM Mac (or a GPU with sufficient VRAM).
                                </p>
                                <CommandBlock command="ollama pull gpt-oss-20b" />
                            </div>
                            <div className="rounded-lg border p-3 space-y-2">
                                <div className="flex items-center gap-2">
                                    <span className="font-medium text-sm">gemma3:12b</span>
                                    <span className="text-xs bg-blue-500/10 text-blue-500 px-2 py-0.5 rounded-full">
                                        Popular
                                    </span>
                                </div>
                                <p className="text-xs text-muted-foreground">
                                    128K context. Good quality in a smaller footprint. A solid choice for machines with 16-32 GB of RAM on Mac or dedicated GPU on PC.
                                </p>
                                <CommandBlock command="ollama pull gemma3:12b" />
                            </div>
                            <div className="rounded-lg border p-3 space-y-2">
                                <div className="flex items-center gap-2">
                                    <span className="font-medium text-sm">qwen3:8b / qwen3:4b</span>
                                    <span className="text-xs bg-orange-500/10 text-orange-500 px-2 py-0.5 rounded-full">
                                        Lightweight
                                    </span>
                                </div>
                                <p className="text-xs text-muted-foreground">
                                    40K context (8B) / 256K context (4B). Surprisingly capable for their size — great if you're resource-constrained or want fast inference. Should work on most machines.
                                </p>
                                <CommandBlock command="ollama pull qwen3:8b" />
                            </div>
                        </div>
                        <p className="text-xs text-muted-foreground">
                            You can always change your summarization model later from the <Link to="/config" className="text-primary hover:underline">Configuration page</Link>.
                        </p>

                        {/* RAM vs VRAM Note */}
                        <div className="rounded-lg border border-muted bg-muted/30 p-4 space-y-1">
                            <p className="text-sm font-medium">A note on RAM vs. VRAM</p>
                            <p className="text-xs text-muted-foreground">
                                <strong>Mac (Apple Silicon):</strong> Memory is shared between CPU and GPU, so a MacBook Pro with 32 GB of RAM can allocate most of it as VRAM — the RAM numbers above map directly to your system memory.
                            </p>
                            <p className="text-xs text-muted-foreground">
                                <strong>PC / Linux with a dedicated GPU:</strong> Ollama runs on your GPU's dedicated VRAM. If the model doesn't fit in VRAM it will fall back to CPU, which is significantly slower. Check your GPU's VRAM (e.g. 8 GB, 16 GB, 24 GB) and pick a model that fits.
                            </p>
                        </div>

                        {/* Performance Tuning Tips */}
                        <PerformanceTuningCard />
                    </div>

                    {/* Configure */}
                    <div className="space-y-3">
                        <h3 className="font-semibold">5. Configure in Oak CI</h3>
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
        </div>
    );
}

// =============================================================================
// Troubleshooting Tab Content
// =============================================================================

function TroubleshootingContent() {
    return (
        <div className="space-y-6">
            <Card>
                <CardHeader>
                    <CardTitle>Common Issues</CardTitle>
                    <CardDescription>
                        Solutions for frequently encountered problems.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                    <div>
                        <h3 className="font-semibold text-sm">Connection refused</h3>
                        <p className="text-sm text-muted-foreground mt-1">
                            Make sure your embedding provider is running. For Ollama, run <code className="bg-muted px-1 rounded">ollama serve</code> or start the desktop app.
                        </p>
                    </div>
                    <div>
                        <h3 className="font-semibold text-sm">No models found</h3>
                        <p className="text-sm text-muted-foreground mt-1">
                            You need to pull/download a model first. For Ollama: <code className="bg-muted px-1 rounded">ollama pull nomic-embed-text</code>
                        </p>
                    </div>
                    <div>
                        <h3 className="font-semibold text-sm">Test & Detect fails</h3>
                        <p className="text-sm text-muted-foreground mt-1">
                            Verify your base URL is correct and the model supports embeddings. Some LLM-only models don't support the embeddings API.
                        </p>
                    </div>
                    <div>
                        <h3 className="font-semibold text-sm">Indexing seems slow</h3>
                        <p className="text-sm text-muted-foreground mt-1">
                            Large codebases take time to index. Check the Dashboard for progress. You can also add exclusions on the <Link to="/config" className="text-primary hover:underline">Configuration page</Link> to skip large directories like <code className="bg-muted px-1 rounded">node_modules</code> or <code className="bg-muted px-1 rounded">vendor</code>.
                        </p>
                    </div>
                    <div>
                        <h3 className="font-semibold text-sm">Search returns no results</h3>
                        <p className="text-sm text-muted-foreground mt-1">
                            Make sure indexing is complete (check Dashboard). If the index is out of sync, use the "Rebuild Codebase Index" option in <Link to="/devtools" className="text-primary hover:underline">DevTools</Link>.
                        </p>
                    </div>
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>Memory & Data Issues</CardTitle>
                    <CardDescription>
                        Resolving problems with memories and observations.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                    <div>
                        <h3 className="font-semibold text-sm">Memories not appearing in search</h3>
                        <p className="text-sm text-muted-foreground mt-1">
                            Check the Memory Status in <Link to="/devtools" className="text-primary hover:underline">DevTools</Link>. If there are pending items, wait for background processing. If ChromaDB is out of sync, use "Re-embed Memories".
                        </p>
                    </div>
                    <div>
                        <h3 className="font-semibold text-sm">After backup restore, data seems incomplete</h3>
                        <p className="text-sm text-muted-foreground mt-1">
                            After restoring from backup, go to <Link to="/devtools" className="text-primary hover:underline">DevTools</Link> and run "Re-embed Memories" with "Clear orphaned entries" checked to rebuild the search index.
                        </p>
                    </div>
                    <div>
                        <h3 className="font-semibold text-sm">Duplicate memories appearing</h3>
                        <p className="text-sm text-muted-foreground mt-1">
                            This shouldn't happen with the content-hash deduplication. If it does, run "Backfill Content Hashes" in DevTools, then restore from backup again.
                        </p>
                    </div>
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>Getting More Help</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                    <p className="text-sm text-muted-foreground">
                        If you're still having issues:
                    </p>
                    <ul className="list-disc list-inside text-sm text-muted-foreground space-y-1">
                        <li>Check the <Link to="/logs" className="text-primary hover:underline">Logs page</Link> for detailed error messages</li>
                        <li>Review the daemon log file at <code className="bg-muted px-1 rounded">.oak/ci/daemon.log</code></li>
                        <li>Open an issue on the project repository</li>
                    </ul>
                </CardContent>
            </Card>
        </div>
    );
}

// =============================================================================
// Cloud Relay Tab Content
// =============================================================================

function CloudRelayContent() {
    return (
        <div className="space-y-6">
            {/* Getting Started */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Cloud className="w-5 h-5" />
                        Getting Started
                    </CardTitle>
                    <CardDescription>
                        The Cloud Relay lets cloud AI agents (Claude.ai, ChatGPT, etc.) access your local Oak CI instance
                        through a Cloudflare Worker.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                    <div className="space-y-3">
                        <h3 className="font-semibold">One-Click Start</h3>
                        <p className="text-sm text-muted-foreground">
                            Click <strong>Start Relay</strong> on the <Link to="/team/relay" className="text-primary hover:underline">Connectivity</Link> page.
                            Oak CI will automatically scaffold, deploy, and connect a Cloudflare Worker for you.
                        </p>
                    </div>

                    <div className="space-y-3">
                        <h3 className="font-semibold">Prerequisites</h3>
                        <ul className="list-disc list-inside text-sm text-muted-foreground space-y-2">
                            <li>
                                A <a
                                    href="https://dash.cloudflare.com/sign-up"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-primary hover:underline inline-flex items-center gap-1"
                                >
                                    Cloudflare account <ExternalLink className="h-3 w-3" />
                                </a> (free tier is sufficient)
                            </li>
                            <li>Node.js / npm installed</li>
                            <li>Wrangler CLI authenticated</li>
                        </ul>
                        <CommandBlock command="npm install -g wrangler && wrangler login" label="Install and authenticate Wrangler" />
                    </div>

                    <div className="rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-950/30 p-4">
                        <p className="text-sm text-blue-800 dark:text-blue-200">
                            The <Link to="/team/relay" className="font-medium underline">Connectivity</Link> page shows a prerequisites checklist
                            and will guide you through any missing steps before starting.
                        </p>
                    </div>
                </CardContent>
            </Card>

            {/* Troubleshooting */}
            <Card>
                <CardHeader>
                    <CardTitle>Troubleshooting</CardTitle>
                    <CardDescription>
                        Common issues with the cloud relay.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                    <div>
                        <h3 className="font-semibold text-sm">"wrangler: command not found"</h3>
                        <p className="text-sm text-muted-foreground mt-1">
                            Install Wrangler globally with <code className="bg-muted px-1 rounded">npm install -g wrangler</code>.
                            Make sure Node.js is installed and npm is on your PATH.
                        </p>
                    </div>
                    <div>
                        <h3 className="font-semibold text-sm">Wrangler authentication failed</h3>
                        <p className="text-sm text-muted-foreground mt-1">
                            Re-run <code className="bg-muted px-1 rounded">wrangler login</code> and complete the browser
                            authorization flow. Check that your Cloudflare account is active.
                        </p>
                    </div>
                    <div>
                        <h3 className="font-semibold text-sm">Deploy errors</h3>
                        <p className="text-sm text-muted-foreground mt-1">
                            The error detail shown on the Cloud page includes the full output from the deploy step.
                            Common causes: expired Wrangler auth, account limits, or network issues.
                            Try <code className="bg-muted px-1 rounded">wrangler whoami</code> to verify your auth status.
                        </p>
                    </div>
                    <div>
                        <h3 className="font-semibold text-sm">Cloud agent can't reach the relay</h3>
                        <p className="text-sm text-muted-foreground mt-1">
                            Verify the agent token matches, the MCP URL includes the <code className="bg-muted px-1 rounded">/mcp</code> path,
                            and test with the curl command shown on the <Link to="/team/relay" className="text-primary hover:underline">Connectivity</Link> page.
                        </p>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}

// =============================================================================
// Help Page Component
// =============================================================================

export default function Help() {
    const location = useLocation();
    const [activeTab, setActiveTab] = useState<HelpTab>(HELP_TABS.SETUP);

    // Handle navigation state (e.g., from Team page linking to cloud-relay tab)
    useEffect(() => {
        const state = location.state as { tab?: string } | null;
        if (state?.tab === "cloud-relay") {
            setActiveTab(HELP_TABS.CLOUD_RELAY);
        }
    }, [location.state]);

    return (
        <div className="space-y-6">
            {/* Header */}
            <div>
                <h1 className="text-3xl font-bold tracking-tight">Help</h1>
                <p className="text-muted-foreground mt-2">
                    Get started with Codebase Intelligence and troubleshoot common issues.
                </p>
            </div>

            {/* Tab Navigation */}
            <div className="flex gap-2 border-b pb-2">
                <TabButton
                    active={activeTab === HELP_TABS.SETUP}
                    onClick={() => setActiveTab(HELP_TABS.SETUP)}
                    icon={<BookOpen className="h-4 w-4" />}
                    label="Setup Guide"
                />
                <TabButton
                    active={activeTab === HELP_TABS.CLOUD_RELAY}
                    onClick={() => setActiveTab(HELP_TABS.CLOUD_RELAY)}
                    icon={<Cloud className="h-4 w-4" />}
                    label="Cloud Relay"
                />
                <TabButton
                    active={activeTab === HELP_TABS.TROUBLESHOOTING}
                    onClick={() => setActiveTab(HELP_TABS.TROUBLESHOOTING)}
                    icon={<Wrench className="h-4 w-4" />}
                    label="Troubleshooting"
                />
            </div>

            {/* Tab Content */}
            {activeTab === HELP_TABS.SETUP && <SetupGuideContent />}
            {activeTab === HELP_TABS.CLOUD_RELAY && <CloudRelayContent />}
            {activeTab === HELP_TABS.TROUBLESHOOTING && <TroubleshootingContent />}
        </div>
    );
}
