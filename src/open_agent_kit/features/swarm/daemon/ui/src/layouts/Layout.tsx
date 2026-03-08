import { useState, useMemo } from "react";
import { NavLink, Outlet } from "react-router-dom";
import {
    LayoutDashboard,
    Search,
    Network,
    Plug,
    Rocket,
    ScrollText,
    Settings,
    PanelLeftClose,
    PanelLeft,
    Sun,
    Moon,
    Laptop,
    RefreshCw,
    Info,
} from "lucide-react";
import { cn, humanizeSlug } from "@oak/ui/lib/utils";
import { useTheme } from "@oak/ui/components/theme-provider";
import { FontSelector } from "@oak/ui/components/ui/font-selector";
import { DensitySelector } from "@oak/ui/components/ui/density-selector";
import { AboutDialog } from "@oak/ui/components/ui/about-dialog";
import type { AboutDialogConfig } from "@oak/ui/components/ui/about-dialog";
import { useSwarmStatus } from "@/hooks/use-swarm-status";
import { useRestart } from "@/hooks/use-restart";
import { useChannel } from "@/hooks/use-channel";
import { fetchJson } from "@/lib/api";
import { API_ENDPOINTS, RESTART_POLL_INTERVAL_MS, RESTART_TIMEOUT_MS } from "@/lib/constants";

const ABOUT_CONFIG: AboutDialogConfig = {
    title: "Oak Swarm",
    logoSrc: "/favicon.svg",
    channelEndpoint: API_ENDPOINTS.CHANNEL,
    channelSwitchEndpoint: API_ENDPOINTS.CHANNEL_SWITCH,
    healthEndpoint: API_ENDPOINTS.HEALTH,
    startCommand: "swarm start",
    restartPollIntervalMs: RESTART_POLL_INTERVAL_MS,
    restartTimeoutMs: RESTART_TIMEOUT_MS,
};

const NAV_ITEMS = [
    { to: "/", icon: LayoutDashboard, label: "Dashboard", end: true },
    { to: "/search", icon: Search, label: "Search" },
    { to: "/nodes", icon: Network, label: "Nodes" },
    { to: "/connect", icon: Plug, label: "Connect" },
    { to: "/deploy", icon: Rocket, label: "Deploy" },
    { to: "/logs", icon: ScrollText, label: "Logs" },
    { to: "/config", icon: Settings, label: "Settings" },
] as const;

export default function Layout() {
    const [collapsed, setCollapsed] = useState(() =>
        localStorage.getItem("swarm-sidebar-collapsed") === "true"
    );
    const [aboutOpen, setAboutOpen] = useState(false);
    const { theme, setTheme } = useTheme();
    const { data: swarmStatus } = useSwarmStatus();
    const { restart, isRestarting, error: restartError } = useRestart();
    const { data: channelData } = useChannel();

    const swarmDisplayName = useMemo(
        () => swarmStatus?.swarm_id ? humanizeSlug(swarmStatus.swarm_id) : "Oak Swarm",
        [swarmStatus?.swarm_id],
    );

    const toggleCollapse = () => {
        const next = !collapsed;
        setCollapsed(next);
        localStorage.setItem("swarm-sidebar-collapsed", String(next));
    };

    return (
        <div className="flex h-screen bg-background text-foreground overflow-hidden font-sans">
            <AboutDialog
                open={aboutOpen}
                onOpenChange={setAboutOpen}
                config={ABOUT_CONFIG}
                channelData={channelData}
                fetchJson={fetchJson as (url: string, init?: RequestInit) => Promise<unknown>}
            />
            {/* Sidebar */}
            <aside
                className={`flex flex-col border-r bg-card transition-all ${
                    collapsed ? "w-16" : "w-56"
                }`}
            >
                {/* Header */}
                <div className={cn("border-b", collapsed ? "p-3" : "px-4 py-3")}>
                    <div className={cn("flex items-center", collapsed ? "justify-center" : "gap-2")}>
                        <div className="w-6 h-6 flex items-center justify-center flex-shrink-0">
                            <img src="/favicon.svg" alt="Oak Swarm" className="w-6 h-6 object-contain" />
                        </div>
                        {!collapsed && (
                            <div className="min-w-0">
                                <div className="flex items-center gap-2">
                                    <span className="font-semibold text-sm truncate">
                                        {swarmDisplayName}
                                    </span>
                                    {channelData?.current_channel === "beta" && (
                                        <span className="px-1.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30 flex-shrink-0">
                                            Beta
                                        </span>
                                    )}
                                </div>
                                {swarmStatus?.swarm_id && (
                                    <span className="text-xs text-muted-foreground truncate block">
                                        {swarmStatus.swarm_id}
                                    </span>
                                )}
                            </div>
                        )}
                    </div>
                </div>

                {/* Nav */}
                <nav className="flex-1 py-2 space-y-1 px-2">
                    {NAV_ITEMS.map(({ to, icon: Icon, label, ...rest }) => (
                        <NavLink
                            key={to}
                            to={to}
                            end={"end" in rest}
                            className={({ isActive }) =>
                                `flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors ${
                                    isActive
                                        ? "bg-accent text-accent-foreground font-medium"
                                        : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                                }`
                            }
                        >
                            <Icon className="h-4 w-4 shrink-0" />
                            {!collapsed && <span>{label}</span>}
                        </NavLink>
                    ))}
                </nav>

                {/* Footer */}
                <div className={cn("border-t", collapsed ? "p-2" : "p-4")}>
                    {/* About button */}
                    <button
                        onClick={() => setAboutOpen(true)}
                        title="About Oak Swarm"
                        aria-label="About Oak Swarm"
                        className={cn(
                            "flex items-center gap-2 w-full px-3 py-2 rounded-md transition-colors text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground mb-2",
                            collapsed && "justify-center px-2",
                        )}
                    >
                        <Info className="w-4 h-4 flex-shrink-0" />
                        {!collapsed && <span>About</span>}
                    </button>

                    {/* Restart daemon button */}
                    <button
                        onClick={() => restart()}
                        disabled={isRestarting}
                        title="Restart daemon"
                        aria-label="Restart daemon"
                        className={cn(
                            "flex items-center gap-2 w-full px-3 py-2 rounded-md transition-colors text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground mb-2",
                            collapsed && "justify-center px-2",
                            "disabled:opacity-50 disabled:cursor-not-allowed"
                        )}
                    >
                        <RefreshCw className={cn("w-4 h-4 flex-shrink-0", isRestarting && "animate-spin")} />
                        {!collapsed && <span>{isRestarting ? "Restarting..." : "Restart"}</span>}
                    </button>

                    {/* Restart error */}
                    {restartError && (
                        <p className="text-xs text-destructive px-1 truncate mb-2" title={restartError}>
                            {restartError}
                        </p>
                    )}

                    {/* Theme switcher */}
                    <div className={cn(
                        "flex items-center rounded-md bg-muted/50 mb-2",
                        collapsed ? "flex-col gap-1 px-1 py-2" : "justify-between px-2 py-1"
                    )}>
                        <button
                            onClick={() => setTheme("light")}
                            title="Light theme"
                            aria-label="Light theme"
                            className={cn("p-1.5 rounded-sm transition-all", theme === "light" && "bg-background shadow-sm")}
                        >
                            <Sun className="w-4 h-4" />
                        </button>
                        <button
                            onClick={() => setTheme("system")}
                            title="System theme"
                            aria-label="System theme"
                            className={cn("p-1.5 rounded-sm transition-all", theme === "system" && "bg-background shadow-sm")}
                        >
                            <Laptop className="w-4 h-4" />
                        </button>
                        <button
                            onClick={() => setTheme("dark")}
                            title="Dark theme"
                            aria-label="Dark theme"
                            className={cn("p-1.5 rounded-sm transition-all", theme === "dark" && "bg-background shadow-sm")}
                        >
                            <Moon className="w-4 h-4" />
                        </button>
                    </div>

                    {/* Density selector */}
                    <DensitySelector collapsed={collapsed} />

                    {/* Font selector */}
                    <FontSelector collapsed={collapsed} />

                    {/* Collapse toggle */}
                    <button
                        onClick={toggleCollapse}
                        title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
                        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
                        className={cn(
                            "flex items-center gap-2 w-full px-3 py-2 rounded-md transition-colors text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground",
                            collapsed && "justify-center px-2"
                        )}
                    >
                        {collapsed ? (
                            <PanelLeft className="w-4 h-4" />
                        ) : (
                            <>
                                <PanelLeftClose className="w-4 h-4" />
                                <span>Collapse</span>
                            </>
                        )}
                    </button>
                </div>
            </aside>

            {/* Main content */}
            <main className="flex-1 overflow-auto p-6">
                <Outlet />
            </main>
        </div>
    );
}
