/**
 * Connect page — surfaces how to use the swarm MCP server and skills.
 *
 * Two access modes:
 *   1. **Local** — Oak auto-installs the swarm MCP server when a project joins
 *      a swarm. All tools and skills work out of the box.
 *   2. **Cloud** — The cloud endpoint lets remote/cloud agents access the same
 *      tools over the internet with a token.
 */

import {
    Search,
    Network,
    Activity,
    HeartPulse,
    Download,
    FileText,
    GitCompare,
    Layers,
    Plug,
    Terminal,
    Monitor,
    Cloud,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@oak/ui/components/ui/card";
import { McpEndpointCard, ToolGrid, SkillGrid } from "@oak/ui/components/ui/connect-cards";
import { useMcpConfig } from "@/hooks/use-mcp-config";
import { useSwarmStatus } from "@/hooks/use-swarm-status";

/* ------------------------------------------------------------------ */
/*  Static data: MCP tools and skills                                  */
/* ------------------------------------------------------------------ */

const MCP_TOOLS = [
    {
        name: "swarm_search",
        icon: Search,
        description: "Search across all connected projects. Use search_type to narrow to memories, sessions, or plans.",
        params: "query, search_type?, limit?",
    },
    {
        name: "swarm_fetch",
        icon: Download,
        description: "Fetch full details for items found via swarm_search. Pass chunk IDs and project slug.",
        params: "ids, project_slug?",
    },
    {
        name: "swarm_nodes",
        icon: Network,
        description: "List all projects currently connected to the swarm with status and capabilities.",
        params: "none",
    },
    {
        name: "swarm_status",
        icon: Activity,
        description: "Check connectivity status — whether connected, the swarm ID, and peer node count.",
        params: "none",
    },
    {
        name: "swarm_health_check",
        icon: HeartPulse,
        description: "Check health of a specific connected team. Returns version info and capabilities.",
        params: "team_slug",
    },
] as const;

const SKILLS = [
    {
        name: "swarm",
        icon: Plug,
        description: "Interactive swarm search. Query cross-project patterns, org-level conventions, and shared decisions.",
        trigger: "/swarm or ask about other teams' patterns",
    },
    {
        name: "swarm-report",
        icon: FileText,
        description: "Generate a cross-project comparative report with activity comparison, shared patterns, and recommendations.",
        trigger: "/swarm-report or ask for an org overview",
    },
    {
        name: "dependency-audit",
        icon: GitCompare,
        description: "Audit dependencies across projects to find version conflicts, outdated packages, and security risks.",
        trigger: "/dependency-audit or ask about package alignment",
    },
    {
        name: "pattern-finder",
        icon: Layers,
        description: "Discover recurring code patterns, architectural decisions, and candidates for shared libraries.",
        trigger: "/pattern-finder or ask about org-wide conventions",
    },
] as const;

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function Connect() {
    const { data: mcpConfig } = useMcpConfig();
    const { data: swarmStatus } = useSwarmStatus();

    const mcpEndpoint = mcpConfig?.mcp_endpoint ?? "";
    const agentToken = mcpConfig?.agent_token ?? "";
    const connected = swarmStatus?.connected ?? false;

    return (
        <div className="space-y-8">
            <div>
                <h1 className="text-2xl font-bold">Connect</h1>
                <p className="text-muted-foreground text-sm mt-1">
                    Access swarm tools and skills from your coding agents
                </p>
            </div>

            {/* Local access */}
            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2 text-base">
                        <Monitor className="h-4 w-4 text-primary" />
                        Local Access
                    </CardTitle>
                    <CardDescription>
                        Already configured — no setup needed
                    </CardDescription>
                </CardHeader>
                <CardContent className="text-sm text-muted-foreground space-y-3">
                    <p>
                        Oak automatically installs the swarm MCP server for every configured
                        agent when a project joins a swarm. All tools and skills listed below
                        are available out of the box — no manual configuration required.
                    </p>
                    <p>
                        To verify, check that{" "}
                        <code className="bg-muted px-1.5 py-0.5 rounded text-xs">oak-swarm</code>{" "}
                        appears in your agent&apos;s MCP server list, or try running{" "}
                        <code className="bg-muted px-1.5 py-0.5 rounded text-xs">/swarm</code>{" "}
                        in your editor.
                    </p>
                </CardContent>
            </Card>

            {/* Cloud access */}
            <div className="space-y-4">
                <div className="flex items-center gap-2">
                    <Cloud className="h-5 w-5 text-primary" />
                    <div>
                        <h2 className="text-lg font-semibold">Cloud Access</h2>
                        <p className="text-sm text-muted-foreground">
                            For remote agents (Claude.ai, ChatGPT, etc.) that can&apos;t reach your local machine
                        </p>
                    </div>
                </div>

                <McpEndpointCard
                    mcpEndpoint={mcpEndpoint}
                    agentToken={agentToken}
                    serverName="oak-swarm"
                    connected={connected}
                    connectedDescription="Connect cloud agents to the swarm using this endpoint and token."
                    disconnectedDescription="Deploy and connect to a swarm worker to get your MCP endpoint."
                    emptyCta={{ href: "/deploy", label: "Deploy a swarm worker" }}
                />
            </div>

            {/* MCP Tools */}
            <ToolGrid tools={MCP_TOOLS} />

            {/* Skills */}
            <SkillGrid
                skills={SKILLS}
                subtitle="Slash commands auto-installed by Oak — guide your agent through multi-step swarm workflows"
            />

            {/* CLI fallback */}
            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2 text-base">
                        <Terminal className="h-4 w-4 text-primary" />
                        CLI Fallback
                    </CardTitle>
                    <CardDescription>
                        If MCP tools are unavailable, use the Oak CLI directly
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <pre className="bg-muted rounded-md px-4 py-3 text-xs font-mono overflow-x-auto space-y-0">
{`oak swarm search "error handling patterns"
oak swarm search --type memory "retry logic"
oak swarm nodes
oak swarm status`}
                    </pre>
                </CardContent>
            </Card>
        </div>
    );
}
