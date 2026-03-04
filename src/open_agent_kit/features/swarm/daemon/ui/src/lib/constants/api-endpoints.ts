export const API_ENDPOINTS = {
    // Swarm
    SWARM_STATUS: "/api/swarm/status",
    SWARM_NODES: "/api/swarm/nodes",
    SWARM_SEARCH: "/api/swarm/search",

    // Agents
    AGENTS: "/api/agents",

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
