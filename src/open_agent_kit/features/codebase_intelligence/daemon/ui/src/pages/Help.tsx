import { useState, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Copy, Check, ExternalLink, Terminal, BookOpen, Wrench, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";

// =============================================================================
// Tab Constants
// =============================================================================

const HELP_TABS = {
    SETUP: "setup",
    TEAM_SYNC: "team-sync",
    TROUBLESHOOTING: "troubleshooting",
} as const;

type HelpTab = typeof HELP_TABS[keyof typeof HELP_TABS];

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
        </div>
    );
}

// =============================================================================
// Sync Guide Tab Content
// =============================================================================

function SyncGuideContent() {
    return (
        <div className="space-y-6">
            {/* Overview */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        Team Sync
                        <span className="text-xs bg-blue-500/10 text-blue-500 px-2 py-1 rounded-full font-normal">
                            Recommended
                        </span>
                    </CardTitle>
                    <CardDescription>
                        The <code className="bg-muted px-1 rounded">oak ci sync</code> command is the preferred way to synchronize CI state after pulling code changes or merging team backups.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                    <div className="rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-950/30 p-4">
                        <p className="text-sm text-blue-800 dark:text-blue-200">
                            <strong>Why CLI?</strong> The CLI handles the complete sync workflow automatically: stopping the daemon, running migrations, importing backups in the correct order, and restarting with new code. This ensures schema compatibility and prevents data corruption.
                        </p>
                    </div>

                    <div className="space-y-3">
                        <h3 className="font-semibold">When to Use</h3>
                        <ul className="list-disc list-inside text-sm text-muted-foreground space-y-2">
                            <li><strong>After pulling OAK code changes</strong> - Restarts daemon with new code and runs any pending schema migrations</li>
                            <li><strong>After pulling project changes with team backups</strong> - Imports team knowledge from <code className="bg-muted px-1 rounded">oak/ci/history/</code></li>
                            <li><strong>When search results seem stale</strong> - Full rebuild recreates the vector index from scratch</li>
                        </ul>
                    </div>
                </CardContent>
            </Card>

            {/* Basic Commands */}
            <Card>
                <CardHeader>
                    <CardTitle>Quick Commands</CardTitle>
                    <CardDescription>
                        Common sync workflows for everyday use.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                    <div className="space-y-3">
                        <h3 className="font-semibold">Quick Sync (After Code Pull)</h3>
                        <CommandBlock command="oak ci sync" />
                        <p className="text-sm text-muted-foreground">
                            Detects version mismatches and restarts the daemon with new code. Use this after pulling OAK updates.
                        </p>
                    </div>

                    <div className="space-y-3">
                        <h3 className="font-semibold">Team Sync (Merge Team Knowledge)</h3>
                        <CommandBlock command="oak ci sync --team" />
                        <p className="text-sm text-muted-foreground">
                            Imports all team backup files from <code className="bg-muted px-1 rounded">oak/ci/history/</code>. Duplicates are automatically skipped using content-based hashing.
                        </p>
                    </div>

                    <div className="space-y-3">
                        <h3 className="font-semibold">Full Rebuild (Fresh Start)</h3>
                        <CommandBlock command="oak ci sync --full" />
                        <p className="text-sm text-muted-foreground">
                            Deletes the vector index (ChromaDB) and rebuilds from scratch. Use this if search results seem incorrect or after major schema changes.
                        </p>
                    </div>

                    <div className="space-y-3">
                        <h3 className="font-semibold">Preview Mode (Dry Run)</h3>
                        <CommandBlock command="oak ci sync --team --full --dry-run" />
                        <p className="text-sm text-muted-foreground">
                            Shows what would happen without making any changes. Great for verifying before a sync.
                        </p>
                    </div>

                    <div className="space-y-3">
                        <h3 className="font-semibold">Include Activities in Backup</h3>
                        <CommandBlock command="oak ci sync --team --include-activities" />
                        <p className="text-sm text-muted-foreground">
                            Creates larger backup files that include the activities table. Useful for debugging or when you want complete history preserved.
                        </p>
                    </div>
                </CardContent>
            </Card>

            {/* Workflow Details */}
            <Card>
                <CardHeader>
                    <CardTitle>Sync Workflow</CardTitle>
                    <CardDescription>
                        Understanding what happens during a sync operation.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <p className="text-sm text-muted-foreground">
                        The sync command orchestrates multiple operations in the correct order:
                    </p>
                    <ol className="list-decimal list-inside text-sm space-y-2">
                        <li><strong>Version Detection</strong> - Compares running daemon version against current code</li>
                        <li><strong>Stop Daemon</strong> - Gracefully stops the daemon if a restart is needed</li>
                        <li><strong>First Restore Pass</strong> - <span className="text-muted-foreground">(--team)</span> Imports all team backups</li>
                        <li><strong>Delete ChromaDB</strong> - <span className="text-muted-foreground">(--full)</span> Removes vector index for rebuild</li>
                        <li><strong>Start Daemon</strong> - Starts with new code, runs pending migrations</li>
                        <li><strong>Create Backup</strong> - <span className="text-muted-foreground">(--team)</span> Creates fresh backup with current schema</li>
                        <li><strong>Second Restore Pass</strong> - <span className="text-muted-foreground">(--team)</span> Re-imports team backups after migrations</li>
                        <li><strong>Background Rebuild</strong> - Vector index rebuilds automatically if needed</li>
                    </ol>
                    <p className="text-xs text-muted-foreground mt-2">
                        Steps marked with flags only run when those flags are provided. Duplicates are always skipped using content-based hashing.
                    </p>
                </CardContent>
            </Card>

            {/* Common Scenarios */}
            <Card>
                <CardHeader>
                    <CardTitle>Common Scenarios</CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                    <div>
                        <h3 className="font-semibold text-sm">New team member joining</h3>
                        <p className="text-sm text-muted-foreground mt-1">
                            After cloning the project, run <code className="bg-muted px-1 rounded">oak ci sync --team</code> to import all existing team knowledge.
                        </p>
                    </div>
                    <div>
                        <h3 className="font-semibold text-sm">Daily workflow</h3>
                        <p className="text-sm text-muted-foreground mt-1">
                            After <code className="bg-muted px-1 rounded">git pull</code>, run <code className="bg-muted px-1 rounded">oak ci sync --team</code> to get the latest from teammates.
                        </p>
                    </div>
                    <div>
                        <h3 className="font-semibold text-sm">After OAK upgrade</h3>
                        <p className="text-sm text-muted-foreground mt-1">
                            Run <code className="bg-muted px-1 rounded">oak ci sync</code> to restart the daemon with the new version and run any schema migrations.
                        </p>
                    </div>
                    <div>
                        <h3 className="font-semibold text-sm">Search returning wrong results</h3>
                        <p className="text-sm text-muted-foreground mt-1">
                            Run <code className="bg-muted px-1 rounded">oak ci sync --full</code> to rebuild the vector index from scratch.
                        </p>
                    </div>
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
// Help Page Component
// =============================================================================

export default function Help() {
    const location = useLocation();
    const [activeTab, setActiveTab] = useState<HelpTab>(HELP_TABS.SETUP);

    // Handle navigation state (e.g., from Team page linking to team-sync tab)
    useEffect(() => {
        const state = location.state as { tab?: string } | null;
        if (state?.tab === "team-sync") {
            setActiveTab(HELP_TABS.TEAM_SYNC);
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
                    active={activeTab === HELP_TABS.TEAM_SYNC}
                    onClick={() => setActiveTab(HELP_TABS.TEAM_SYNC)}
                    icon={<RefreshCw className="h-4 w-4" />}
                    label="Team Sync"
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
            {activeTab === HELP_TABS.TEAM_SYNC && <SyncGuideContent />}
            {activeTab === HELP_TABS.TROUBLESHOOTING && <TroubleshootingContent />}
        </div>
    );
}
