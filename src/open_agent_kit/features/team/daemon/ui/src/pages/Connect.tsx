/**
 * Connect page — surfaces how to use the team MCP server and skills.
 *
 * Two access modes:
 *   1. **Local** — Oak auto-installs the team MCP server for any configured agent.
 *      No manual setup needed; tools and skills just work.
 *   2. **Cloud** — The cloud relay endpoint lets remote/cloud agents (Claude.ai,
 *      ChatGPT, etc.) access the same tools over the internet with a token.
 *
 * The page makes this distinction explicit so users don't try to manually
 * configure something that's already set up locally.
 */

import {
    Search,
    Brain,
    Compass,
    CheckCircle2,
    ClipboardList,
    BarChart3,
    Activity,
    Archive,
    Download,
    Network,
    Globe as GlobeSearch,
    Terminal,
    TreePine,
    Monitor,
    Cloud,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@oak/ui/components/ui/card";
import { McpEndpointCard, ToolGrid, SkillGrid } from "@oak/ui/components/ui/connect-cards";
import { useCloudRelayStatus } from "@/hooks/use-cloud-relay";

/* ------------------------------------------------------------------ */
/*  Static data: MCP tools and skills                                  */
/* ------------------------------------------------------------------ */

const MCP_TOOLS = [
    {
        name: "oak_search",
        icon: Search,
        description: "Semantic search across code chunks, memories, sessions, and plans. The primary discovery tool.",
        params: "query, search_type?, limit?, include_network?",
    },
    {
        name: "oak_remember",
        icon: Brain,
        description: "Store an observation, decision, gotcha, or pattern as a persistent memory for future recall.",
        params: "content, category?, tags?",
    },
    {
        name: "oak_context",
        icon: Compass,
        description: "Get full context for a task — related code, recent decisions, relevant memories, and dependencies.",
        params: "task_description",
    },
    {
        name: "oak_resolve_memory",
        icon: CheckCircle2,
        description: "Mark a memory as resolved after fixing the issue it describes. Keeps the knowledge base clean.",
        params: "memory_uuid",
    },
    {
        name: "oak_sessions",
        icon: ClipboardList,
        description: "List recent coding sessions with summaries, timestamps, and token usage.",
        params: "limit?, offset?",
    },
    {
        name: "oak_memories",
        icon: Brain,
        description: "Browse stored memories with optional category and tag filters.",
        params: "category?, tag?, limit?",
    },
    {
        name: "oak_stats",
        icon: BarChart3,
        description: "Project statistics — index size, memory count, session history, and storage usage.",
        params: "none",
    },
    {
        name: "oak_activity",
        icon: Activity,
        description: "Recent activity feed — file changes, indexing events, and agent interactions.",
        params: "limit?, since?",
    },
    {
        name: "oak_archive_memories",
        icon: Archive,
        description: "Archive outdated memories in bulk. Useful for periodic knowledge base maintenance.",
        params: "memory_uuids",
    },
    {
        name: "oak_fetch",
        icon: Download,
        description: "Fetch full content for chunk IDs returned by oak_search. Retrieves the complete source context.",
        params: "ids, project_slug?",
    },
    {
        name: "oak_nodes",
        icon: Network,
        description: "List all team nodes connected via the relay, with status and capabilities.",
        params: "none",
    },
    {
        name: "swarm_search",
        icon: GlobeSearch,
        description: "Search across all projects connected to the swarm. Requires swarm connectivity.",
        params: "query, search_type?, limit?",
    },
    {
        name: "swarm_nodes",
        icon: Network,
        description: "List all projects in the swarm with status, capabilities, and node counts.",
        params: "none",
    },
] as const;

const SKILLS = [
    {
        name: "oak",
        icon: TreePine,
        description: "Codebase intelligence — recall decisions, find dependencies, query history, and store observations.",
        trigger: "/oak or ask about past decisions, dependencies, or what happened",
    },
] as const;

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function Connect() {
    const { data: relayStatus } = useCloudRelayStatus();

    const mcpEndpoint = relayStatus?.mcp_endpoint ?? "";
    const agentToken = relayStatus?.agent_token ?? "";
    const connected = relayStatus?.connected ?? false;

    return (
        <div className="space-y-8">
            <div>
                <h1 className="text-2xl font-bold">Connect</h1>
                <p className="text-muted-foreground text-sm mt-1">
                    Access tools and skills from your coding agents
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
                        Oak automatically installs the team MCP server for every configured
                        agent (Claude Code, Cursor, Windsurf, etc.). All tools and skills
                        listed below are available out of the box — no manual configuration
                        required.
                    </p>
                    <p>
                        To verify, check that{" "}
                        <code className="bg-muted px-1.5 py-0.5 rounded text-xs">oak-team</code>{" "}
                        appears in your agent&apos;s MCP server list, or try running{" "}
                        <code className="bg-muted px-1.5 py-0.5 rounded text-xs">/oak</code>{" "}
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
                    serverName="oak-team"
                    connected={connected}
                    connectedDescription="Connect cloud agents using this endpoint and token."
                    disconnectedDescription="Connect to the cloud relay to get your MCP endpoint."
                    emptyCta={{ href: "/team/relay", label: "Configure the cloud relay" }}
                />
            </div>

            {/* MCP Tools */}
            <ToolGrid
                tools={MCP_TOOLS}
                subtitle="Available locally (auto-configured) and via the cloud relay endpoint"
            />

            {/* Skills */}
            <SkillGrid skills={SKILLS} />

            {/* CLI fallback */}
            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2 text-base">
                        <Terminal className="h-4 w-4 text-primary" />
                        CLI Fallback
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <pre className="bg-muted rounded-md px-4 py-3 text-xs font-mono overflow-x-auto space-y-0">
{`oak ci search "error handling patterns"
oak ci search --type memory "retry logic"
oak ci sessions
oak ci stats`}
                    </pre>
                </CardContent>
            </Card>
        </div>
    );
}
