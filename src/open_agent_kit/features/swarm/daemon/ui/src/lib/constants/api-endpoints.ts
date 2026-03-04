export const API_ENDPOINTS = {
    // Swarm
    SWARM_STATUS: "/api/swarm/status",
    SWARM_NODES: "/api/swarm/nodes",
    SWARM_SEARCH: "/api/swarm/search",

    // Agents
    AGENTS: "/api/agents",
    AGENTS_RELOAD: "/api/agents/reload",
    AGENTS_TASK_RUN: "/api/agents/tasks/:taskName/run",
    AGENTS_RUNS: "/api/agents/runs",
    AGENTS_RUN_DETAIL: "/api/agents/runs/:runId",

    // Node management
    SWARM_NODE_REMOVE: "/api/swarm/nodes/remove",

    // Deploy
    DEPLOY_STATUS: "/api/deploy/status",
    DEPLOY_AUTH: "/api/deploy/auth",
    DEPLOY_SCAFFOLD: "/api/deploy/scaffold",
    DEPLOY_INSTALL: "/api/deploy/install",
    DEPLOY_RUN: "/api/deploy/run",

    // System
    HEALTH: "/api/health",
    RESTART: "/api/restart",
    LOGS: "/api/logs",
} as const;
