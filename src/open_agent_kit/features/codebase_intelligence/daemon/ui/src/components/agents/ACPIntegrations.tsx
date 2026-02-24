/**
 * ACP Integrations component showing editor setup instructions
 * and ACP server log viewer.
 */

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import {
    Plug,
    RefreshCw,
    ChevronDown,
    ChevronUp,
    Terminal,
    FileCode,
} from "lucide-react";
import { useAcpLogs } from "@/hooks/use-acp";
import { useStatus } from "@/hooks/use-status";

const LOG_LINES_COUNT = 100;

function buildZedConfig(cliCommand: string): string {
    return JSON.stringify(
        {
            agent_servers: {
                "OAK Agent": {
                    type: "custom",
                    command: cliCommand,
                    args: ["acp", "serve"],
                    env: {},
                },
            },
        },
        null,
        2,
    );
}

export default function ACPIntegrations() {
    const { data: daemonStatus } = useStatus();
    const { data: logsData } = useAcpLogs(LOG_LINES_COUNT);
    const [showZedSetup, setShowZedSetup] = useState(false);
    const [showLogs, setShowLogs] = useState(false);

    const cliCommand = daemonStatus?.cli_command || "oak";

    return (
        <div className="space-y-6">
            {/* Overview Card */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Plug className="h-5 w-5" />
                        ACP Server
                    </CardTitle>
                    <CardDescription>
                        Connect ACP-compatible editors (Zed, Neovim, JetBrains) to OAK.
                        The editor launches the ACP server automatically — no manual setup needed.
                    </CardDescription>
                </CardHeader>
            </Card>

            {/* Zed Setup Card */}
            <Card>
                <CardHeader
                    className="cursor-pointer"
                    onClick={() => setShowZedSetup(!showZedSetup)}
                >
                    <CardTitle className="flex items-center justify-between text-base">
                        <span className="flex items-center gap-2">
                            <FileCode className="h-4 w-4" />
                            Zed Setup
                        </span>
                        {showZedSetup ? (
                            <ChevronUp className="h-4 w-4 text-muted-foreground" />
                        ) : (
                            <ChevronDown className="h-4 w-4 text-muted-foreground" />
                        )}
                    </CardTitle>
                    <CardDescription>
                        Configure Zed editor to use OAK as an ACP agent.
                    </CardDescription>
                </CardHeader>
                {showZedSetup && (
                    <CardContent className="space-y-3">
                        <p className="text-sm text-muted-foreground">
                            Add the following to your Zed <code className="bg-muted px-1.5 py-0.5 rounded text-xs font-mono">settings.json</code>:
                        </p>
                        <pre className="bg-muted border rounded-md p-4 text-xs font-mono overflow-x-auto">
                            <code>{buildZedConfig(cliCommand)}</code>
                        </pre>
                        <p className="text-xs text-muted-foreground">
                            Zed will spawn <code className="bg-muted px-1.5 py-0.5 rounded text-xs font-mono">{cliCommand} acp serve</code> automatically
                            when you select OAK Agent in the AI panel.
                        </p>
                    </CardContent>
                )}
            </Card>

            {/* Log Viewer Card */}
            <Card>
                <CardHeader
                    className="cursor-pointer"
                    onClick={() => setShowLogs(!showLogs)}
                >
                    <CardTitle className="flex items-center justify-between text-base">
                        <span className="flex items-center gap-2">
                            <Terminal className="h-4 w-4" />
                            Logs
                        </span>
                        <div className="flex items-center gap-2">
                            {showLogs && (
                                <RefreshCw className="h-3 w-3 text-muted-foreground" />
                            )}
                            {showLogs ? (
                                <ChevronUp className="h-4 w-4 text-muted-foreground" />
                            ) : (
                                <ChevronDown className="h-4 w-4 text-muted-foreground" />
                            )}
                        </div>
                    </CardTitle>
                    <CardDescription>
                        Recent ACP server log output.
                    </CardDescription>
                </CardHeader>
                {showLogs && (
                    <CardContent>
                        {logsData?.lines && logsData.lines.length > 0 ? (
                            <pre className="bg-muted border rounded-md p-4 text-xs font-mono overflow-x-auto max-h-96 overflow-y-auto">
                                <code>
                                    {logsData.lines.join("\n")}
                                </code>
                            </pre>
                        ) : (
                            <p className="text-sm text-muted-foreground">
                                No log output yet. Select OAK Agent in your editor to see logs.
                            </p>
                        )}
                        {logsData?.log_file && (
                            <p className="text-xs text-muted-foreground mt-2">
                                Log file: <code className="bg-muted px-1.5 py-0.5 rounded text-xs font-mono">{logsData.log_file}</code>
                            </p>
                        )}
                    </CardContent>
                )}
            </Card>
        </div>
    );
}
