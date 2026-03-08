/**
 * Shared Connect page components — MCP endpoint card, tool grid, and skill grid.
 *
 * Used by both the team and swarm daemon Connect pages to avoid duplication.
 * Each component is self-contained: pass data in, get a styled card out.
 */

import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./card";
import { Button } from "./button";
import { CopyButton } from "./command-block";
import { Globe, Eye, EyeOff } from "lucide-react";
import type { LucideIcon } from "lucide-react";

// =============================================================================
// MCP Endpoint Card
// =============================================================================

export interface McpEndpointCardProps {
    mcpEndpoint: string;
    agentToken: string;
    /** Server name used in the mcp.json config snippet (e.g. "oak-swarm", "oak-ci") */
    serverName: string;
    connected: boolean;
    /** Description shown when connected */
    connectedDescription?: string;
    /** Description shown when disconnected */
    disconnectedDescription?: string;
    /** Link target + label for the empty-state CTA */
    emptyCta?: { href: string; label: string };
}

export function McpEndpointCard({
    mcpEndpoint,
    agentToken,
    serverName,
    connected,
    connectedDescription = "Connect agents using this endpoint and token.",
    disconnectedDescription = "Deploy and connect to get your MCP endpoint.",
    emptyCta,
}: McpEndpointCardProps) {
    const [showToken, setShowToken] = useState(false);
    const maskedToken = agentToken ? "\u2022".repeat(Math.min(agentToken.length, 32)) : "";

    return (
        <Card>
            <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                    <Globe className="h-4 w-4" />
                    MCP Server Endpoint
                </CardTitle>
                <CardDescription>
                    {connected ? connectedDescription : disconnectedDescription}
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                {mcpEndpoint ? (
                    <>
                        {/* Endpoint URL */}
                        <div className="space-y-1.5">
                            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                                Endpoint URL
                            </label>
                            <div className="flex items-center gap-2 bg-muted rounded-md px-4 py-3 font-mono text-sm">
                                <code className="flex-1 truncate">{mcpEndpoint}</code>
                                <CopyButton text={mcpEndpoint} />
                            </div>
                        </div>

                        {/* Agent Token */}
                        {agentToken && (
                            <div className="space-y-1.5">
                                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                                    Agent Token
                                </label>
                                <div className="flex items-center gap-2 bg-muted rounded-md px-4 py-3 font-mono text-sm">
                                    <code className="flex-1 truncate">
                                        {showToken ? agentToken : maskedToken}
                                    </code>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        className="h-8 w-8 p-0"
                                        onClick={() => setShowToken(!showToken)}
                                    >
                                        {showToken ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                                    </Button>
                                    <CopyButton text={agentToken} />
                                </div>
                                <p className="text-xs text-muted-foreground">
                                    Include in the{" "}
                                    <code className="bg-muted px-1 rounded">Authorization: Bearer</code>{" "}
                                    header when connecting.
                                </p>
                            </div>
                        )}

                        {/* Config snippet */}
                        <div className="space-y-1.5">
                            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                                Claude Code Config
                            </label>
                            <div className="relative">
                                <pre className="bg-muted rounded-md px-4 py-3 text-xs font-mono overflow-x-auto">
{`{
  "mcpServers": {
    "${serverName}": {
      "url": "${mcpEndpoint}",
      "headers": {
        "Authorization": "Bearer ${showToken && agentToken ? agentToken : "<your-token>"}"
      }
    }
  }
}`}
                                </pre>
                                <div className="absolute top-2 right-2">
                                    <CopyButton
                                        text={`{\n  "mcpServers": {\n    "${serverName}": {\n      "url": "${mcpEndpoint}",\n      "headers": {\n        "Authorization": "Bearer ${agentToken || "<your-token>"}"\n      }\n    }\n  }\n}`}
                                    />
                                </div>
                            </div>
                            <p className="text-xs text-muted-foreground">
                                Add this to your project&apos;s <code className="bg-muted px-1 rounded">.mcp.json</code> or global MCP config.
                            </p>
                        </div>
                    </>
                ) : (
                    <p className="text-sm text-muted-foreground py-4 text-center">
                        No MCP endpoint available.{" "}
                        {emptyCta && (
                            <a href={emptyCta.href} className="text-primary underline underline-offset-2 hover:text-primary/80">
                                {emptyCta.label}
                            </a>
                        )}
                    </p>
                )}
            </CardContent>
        </Card>
    );
}

// =============================================================================
// Tool Grid
// =============================================================================

export interface ToolDefinition {
    name: string;
    icon: LucideIcon;
    description: string;
    params: string;
}

export interface ToolGridProps {
    tools: readonly ToolDefinition[];
    title?: string;
    subtitle?: string;
}

export function ToolGrid({
    tools,
    title = "MCP Tools",
    subtitle = "Available to any agent connected via the MCP server endpoint above",
}: ToolGridProps) {
    return (
        <div>
            <h2 className="text-lg font-semibold mb-1">{title}</h2>
            <p className="text-sm text-muted-foreground mb-4">{subtitle}</p>
            <div className="grid gap-3 md:grid-cols-2">
                {tools.map((tool) => (
                    <Card key={tool.name}>
                        <CardContent className="pt-5 pb-4">
                            <div className="flex items-start gap-3">
                                <div className="rounded-md bg-primary/10 p-2 shrink-0">
                                    <tool.icon className="h-4 w-4 text-primary" />
                                </div>
                                <div className="min-w-0">
                                    <p className="font-mono text-sm font-medium">{tool.name}</p>
                                    <p className="text-xs text-muted-foreground mt-0.5">
                                        {tool.description}
                                    </p>
                                    <p className="text-xs text-muted-foreground mt-1.5">
                                        <span className="font-medium text-foreground">Params: </span>
                                        <code className="bg-muted px-1 rounded">{tool.params}</code>
                                    </p>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                ))}
            </div>
        </div>
    );
}

// =============================================================================
// Skill Grid
// =============================================================================

export interface SkillDefinition {
    name: string;
    icon: LucideIcon;
    description: string;
    trigger: string;
}

export interface SkillGridProps {
    skills: readonly SkillDefinition[];
    title?: string;
    subtitle?: string;
}

export function SkillGrid({
    skills,
    title = "Skills",
    subtitle = "Slash commands auto-installed by Oak — guide your agent through multi-step workflows",
}: SkillGridProps) {
    return (
        <div>
            <h2 className="text-lg font-semibold mb-1">{title}</h2>
            <p className="text-sm text-muted-foreground mb-4">{subtitle}</p>
            <div className="grid gap-3 md:grid-cols-2">
                {skills.map((skill) => (
                    <Card key={skill.name}>
                        <CardContent className="pt-5 pb-4">
                            <div className="flex items-start gap-3">
                                <div className="rounded-md bg-primary/10 p-2 shrink-0">
                                    <skill.icon className="h-4 w-4 text-primary" />
                                </div>
                                <div className="min-w-0">
                                    <p className="font-mono text-sm font-medium">/{skill.name}</p>
                                    <p className="text-xs text-muted-foreground mt-0.5">
                                        {skill.description}
                                    </p>
                                    <p className="text-xs text-muted-foreground mt-1.5">
                                        <span className="font-medium text-foreground">Try: </span>
                                        <code className="bg-muted px-1 rounded">{skill.trigger}</code>
                                    </p>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                ))}
            </div>
        </div>
    );
}
