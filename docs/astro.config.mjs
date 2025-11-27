import { defineConfig } from "astro/config";
import starlight from "@astrojs/starlight";
import starlightClientMermaid from "@pasqal-io/starlight-client-mermaid";

export default defineConfig({
  site: "https://oak.goondocks.co",
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
              label: "Teams",
              slug: "features/codebase-intelligence/teams",
            },
            {
              label: "Configuration",
              slug: "features/codebase-intelligence/configuration",
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
          label: "OAK Agents",
          items: [
            {
              label: "Overview",
              slug: "features/codebase-intelligence/agents",
            },
            {
              label: "Documentation Agent",
              slug: "features/codebase-intelligence/documentation-agent",
            },
            {
              label: "Analysis Agent",
              slug: "features/codebase-intelligence/analysis-agent",
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
          ],
        },
        { label: "Troubleshooting", slug: "troubleshooting" },
      ],
    }),
  ],
});
