import { defineConfig } from "astro/config";
import starlight from "@astrojs/starlight";
import starlightClientMermaid from "@pasqal-io/starlight-client-mermaid";

export default defineConfig({
  site: "https://openagentkit.app",
  integrations: [
    starlight({
      title: "Open Agent Kit",
      logo: {
        src: "./src/assets/images/oak-logo.png",
      },
      plugins: [starlightClientMermaid()],
      customCss: ["./src/styles/custom.css"],
      social: [
        {
          icon: "github",
          label: "GitHub",
          href: "https://github.com/goondocks-co/open-agent-kit",
        },
      ],
      sidebar: [
        { label: "Getting Started", link: "/" },
        {
          label: "Team",
          items: [
            {
              label: "Overview",
              slug: "team",
            },
            {
              label: "Getting Started",
              slug: "team/getting-started",
            },
            {
              label: "Dashboard",
              slug: "team/dashboard",
            },
            {
              label: "Activities",
              slug: "team/activities",
            },
            {
              label: "Logs",
              slug: "team/logs",
            },
            {
              label: "Configuration",
              slug: "team/configuration",
            },
            {
              label: "Governance",
              slug: "team/governance",
            },
            {
              label: "DevTools",
              slug: "team/devtools",
            },
            {
              label: "Memory",
              slug: "team/memory",
            },
            {
              label: "Session Lifecycle",
              slug: "team/session-lifecycle",
            },
            {
              label: "Team Sync",
              slug: "team/sync",
            },
            {
              label: "MCP",
              slug: "team/mcp",
            },
          ],
        },
        {
          label: "Swarm",
          items: [
            {
              label: "Overview",
              slug: "swarm",
            },
            {
              label: "MCP",
              slug: "swarm/mcp",
            },
          ],
        },
        {
          label: "OAK Agents",
          items: [
            {
              label: "Overview",
              slug: "team/agents",
            },
            {
              label: "Agent Client Protocol (ACP)",
              slug: "team/acp",
            },
            {
              label: "Documentation Agent",
              slug: "team/documentation-agent",
            },
            {
              label: "Analysis Agent",
              slug: "team/analysis-agent",
            },
            {
              label: "Engineering Agent",
              slug: "team/engineering-agent",
            },
            {
              label: "Maintenance Agent",
              slug: "team/maintenance-agent",
            },
          ],
        },
        {
          label: "Coding Agents",
          items: [
            { label: "Agent Overview", slug: "agents" },
            { label: "Skills", slug: "agents/skills" },
          ],
        },
        {
          label: "Reference",
          items: [
            { label: "CLI Commands", slug: "cli" },
            { label: "Configuration", slug: "configuration" },
            { label: "Hooks Reference", slug: "team/hooks-reference" },
            { label: "API Reference", slug: "team/developer-api" },
            { label: "Release Process", slug: "releasing" },
          ],
        },
        { label: "Troubleshooting", slug: "troubleshooting" },
      ],
    }),
  ],
});
