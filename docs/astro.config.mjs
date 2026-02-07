import { defineConfig } from "astro/config";
import starlight from "@astrojs/starlight";
import starlightClientMermaid from "@pasqal-io/starlight-client-mermaid";

export default defineConfig({
  site: "https://goondocks-co.github.io",
  base: "/open-agent-kit",
  integrations: [
    starlight({
      title: "Open Agent Kit",
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
          label: "Features",
          items: [
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
                  label: "Developer API",
                  slug: "features/codebase-intelligence/developer-api",
                },
                {
                  label: "DevTools",
                  slug: "features/codebase-intelligence/devtools",
                },
                {
                  label: "Backup & Restore",
                  slug: "features/codebase-intelligence/backup",
                },
              ],
            },
            {
              label: "Rules Management",
              slug: "features/rules-management",
            },
            {
              label: "Strategic Planning",
              slug: "features/strategic-planning",
            },
          ],
        },
        {
          label: "Agents",
          items: [
            { label: "Agent Overview", slug: "agents" },
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
        { label: "Architecture", slug: "architecture" },
        {
          label: "Development",
          items: [
            { label: "Feature Development", slug: "development/features" },
            { label: "Releasing", slug: "development/releasing" },
          ],
        },
        { label: "Troubleshooting", slug: "troubleshooting" },
      ],
    }),
  ],
});
