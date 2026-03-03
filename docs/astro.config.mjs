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
          label: "Codebase Intelligence",
          items: [
            {
              label: "Overview",
              slug: "features/codebase-intelligence",
            },
            {
              label: "Getting Started",
              slug: "features/codebase-intelligence/getting-started",
            },
            {
              label: "Dashboard",
              slug: "features/codebase-intelligence/dashboard",
            },
            {
              label: "Activities",
              slug: "features/codebase-intelligence/activities",
            },
            {
              label: "Logs",
              slug: "features/codebase-intelligence/logs",
            },
            {
              label: "Configuration",
              slug: "features/codebase-intelligence/configuration",
            },
            {
              label: "Governance",
              slug: "features/codebase-intelligence/governance",
            },
            {
              label: "DevTools",
              slug: "features/codebase-intelligence/devtools",
            },
            {
              label: "Memory",
              slug: "features/codebase-intelligence/memory",
            },
            {
              label: "Session Lifecycle",
              slug: "features/codebase-intelligence/session-lifecycle",
            },
            {
              label: "Hooks Reference",
              slug: "features/codebase-intelligence/hooks-reference",
            },
            {
              label: "API Reference",
              slug: "features/codebase-intelligence/developer-api",
            },
          ],
        },
        {
          label: "Teams",
          items: [
            {
              label: "Overview",
              slug: "features/teams",
            },
            {
              label: "Cloud Relay",
              slug: "features/cloud-relay",
            },
            {
              label: "Cloudflare Setup",
              slug: "features/cloud-relay/cloudflare-setup",
            },
            {
              label: "Deployment",
              slug: "features/cloud-relay/deployment",
            },
            {
              label: "Cloud Agents",
              slug: "features/cloud-relay/cloud-agents",
            },
            {
              label: "Authentication",
              slug: "features/cloud-relay/authentication",
            },
            {
              label: "Relay Troubleshooting",
              slug: "features/cloud-relay/troubleshooting",
            },
          ],
        },
        {
          label: "OAK Agents",
          items: [
            {
              label: "Overview",
              slug: "features/codebase-intelligence/agents",
            },
            {
              label: "Agent Client Protocol (ACP)",
              slug: "features/codebase-intelligence/acp",
            },
            {
              label: "Documentation Agent",
              slug: "features/codebase-intelligence/documentation-agent",
            },
            {
              label: "Analysis Agent",
              slug: "features/codebase-intelligence/analysis-agent",
            },
            {
              label: "Engineering Agent",
              slug: "features/codebase-intelligence/engineering-agent",
            },
            {
              label: "Maintenance Agent",
              slug: "features/codebase-intelligence/maintenance-agent",
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
            { label: "MCP Tools", slug: "api/mcp-tools" },
            { label: "Release Process", slug: "releasing" },
          ],
        },
        { label: "Troubleshooting", slug: "troubleshooting" },
      ],
    }),
  ],
});
