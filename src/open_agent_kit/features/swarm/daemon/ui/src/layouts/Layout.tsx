import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import {
    LayoutDashboard,
    Search,
    Network,
    Hexagon,
    Rocket,
    Bot,
    ScrollText,
    PanelLeftClose,
    PanelLeft,
    Sun,
    Moon,
    Monitor,
    RotateCcw,
} from "lucide-react";
import { Button } from "@oak/ui/components/ui/button";
import { useTheme } from "@oak/ui/components/theme-provider";
import { useSwarmStatus } from "@/hooks/use-swarm-status";
import { useRestart } from "@/hooks/use-restart";

const NAV_ITEMS = [
    { to: "/", icon: LayoutDashboard, label: "Dashboard", end: true },
    { to: "/search", icon: Search, label: "Search" },
    { to: "/nodes", icon: Network, label: "Nodes" },
    { to: "/deploy", icon: Rocket, label: "Deploy" },
    { to: "/agents", icon: Bot, label: "Agents" },
    { to: "/logs", icon: ScrollText, label: "Logs" },
] as const;

export default function Layout() {
    const [collapsed, setCollapsed] = useState(() =>
        localStorage.getItem("swarm-sidebar-collapsed") === "true"
    );
    const { theme, setTheme } = useTheme();
    const { data: swarmStatus } = useSwarmStatus();
    const { restart, isRestarting, error: restartError } = useRestart();

    const toggleCollapse = () => {
        const next = !collapsed;
        setCollapsed(next);
        localStorage.setItem("swarm-sidebar-collapsed", String(next));
    };

    return (
        <div className="flex h-screen">
            {/* Sidebar */}
            <aside
                className={`flex flex-col border-r bg-card transition-all ${
                    collapsed ? "w-16" : "w-56"
                }`}
            >
                {/* Header */}
                <div className="flex items-center gap-2 border-b px-4 py-3">
                    <Hexagon className="h-5 w-5 text-primary shrink-0" />
                    {!collapsed && (
                        <span className="font-semibold text-sm truncate">
                            {swarmStatus?.swarm_id || "Oak Swarm"}
                        </span>
                    )}
                </div>

                {/* Swarm ID */}
                {!collapsed && swarmStatus?.swarm_id && (
                    <div className="px-4 py-2 text-xs text-muted-foreground truncate border-b">
                        {swarmStatus.swarm_id}
                    </div>
                )}

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
                <div className="border-t p-2 space-y-2">
                    {/* Theme switcher */}
                    <div className="flex justify-center gap-1">
                        <Button
                            variant={theme === "light" ? "secondary" : "ghost"}
                            size="icon"
                            className="h-7 w-7"
                            onClick={() => setTheme("light")}
                        >
                            <Sun className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                            variant={theme === "system" ? "secondary" : "ghost"}
                            size="icon"
                            className="h-7 w-7"
                            onClick={() => setTheme("system")}
                        >
                            <Monitor className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                            variant={theme === "dark" ? "secondary" : "ghost"}
                            size="icon"
                            className="h-7 w-7"
                            onClick={() => setTheme("dark")}
                        >
                            <Moon className="h-3.5 w-3.5" />
                        </Button>
                    </div>

                    {/* Restart error */}
                    {restartError && (
                        <p className="text-xs text-destructive px-1 truncate" title={restartError}>
                            {restartError}
                        </p>
                    )}

                    {/* Restart + Collapse */}
                    <div className="flex justify-between">
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7"
                            onClick={() => restart()}
                            disabled={isRestarting}
                            title="Restart daemon"
                        >
                            <RotateCcw className={`h-3.5 w-3.5 ${isRestarting ? "animate-spin" : ""}`} />
                        </Button>
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7"
                            onClick={toggleCollapse}
                        >
                            {collapsed ? (
                                <PanelLeft className="h-3.5 w-3.5" />
                            ) : (
                                <PanelLeftClose className="h-3.5 w-3.5" />
                            )}
                        </Button>
                    </div>
                </div>
            </aside>

            {/* Main content */}
            <main className="flex-1 overflow-auto p-6">
                <Outlet />
            </main>
        </div>
    );
}
