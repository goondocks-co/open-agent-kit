export const API_ENDPOINTS = {
    // Swarm
    SWARM_STATUS: "/api/swarm/status",
    SWARM_CREDENTIALS: "/api/swarm/credentials",
    SWARM_NODES: "/api/swarm/nodes",
    SWARM_SEARCH: "/api/swarm/search",
    SWARM_FETCH: "/api/swarm/fetch",

    // Node management
    SWARM_NODE_REMOVE: "/api/swarm/nodes/remove",
    SWARM_HEALTH_CHECK: "/api/swarm/health-check",

    // Deploy
    DEPLOY_STATUS: "/api/deploy/status",
    DEPLOY_AUTH: "/api/deploy/auth",
    DEPLOY_SCAFFOLD: "/api/deploy/scaffold",
    DEPLOY_INSTALL: "/api/deploy/install",
    DEPLOY_RUN: "/api/deploy/run",
    DEPLOY_SETTINGS: "/api/deploy/settings",

    // Channel
    CHANNEL: "/api/channel",
    CHANNEL_SWITCH: "/api/channel/switch",

    // System
    HEALTH: "/api/health",
    RESTART: "/api/restart",
    CONFIG: "/api/config",
    CONFIG_MCP: "/api/config/mcp",
    CONFIG_MIN_OAK_VERSION: "/api/config/min-oak-version",
    LOGS: "/api/logs",
} as const;
