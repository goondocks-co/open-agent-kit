import { useState, useEffect } from "react";
import { Link, useLocation, Outlet } from "react-router-dom";
import { LayoutDashboard, Search, Activity, FileTerminal, Settings, Sun, Moon, Laptop, Wrench, Folder, HelpCircle, Users, Bot, PanelLeft, PanelLeftClose } from "lucide-react";
import { cn } from "@/lib/utils";
import { useTheme } from "@/components/theme-provider";
import { useStatus } from "@/hooks/use-status";

import type { LucideIcon } from "lucide-react";

const SIDEBAR_COLLAPSED_KEY = "oak-ci-sidebar-collapsed";

const NavItem = ({ to, icon: Icon, label, active, collapsed }: { to: string; icon: LucideIcon; label: string; active: boolean; collapsed: boolean }) => (
    <Link
        to={to}
        title={collapsed ? label : undefined}
        className={cn(
            "flex items-center gap-3 px-3 py-2 rounded-md transition-colors text-sm font-medium",
            collapsed && "justify-center px-2",
            active
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-muted hover:text-foreground"
        )}
    >
        <Icon className="w-4 h-4 flex-shrink-0" />
        {!collapsed && <span>{label}</span>}
    </Link>
);

export function Layout() {
    const location = useLocation();
    const { setTheme, theme } = useTheme();
    const { data: status } = useStatus();

    const [collapsed, setCollapsed] = useState(() => {
        const saved = localStorage.getItem(SIDEBAR_COLLAPSED_KEY);
        return saved === "true";
    });

    useEffect(() => {
        localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(collapsed));
    }, [collapsed]);

    const projectName = status?.project_root
        ? status.project_root.split('/').pop()
        : null;

    const navItems = [
        { to: "/", icon: LayoutDashboard, label: "Dashboard" },
        { to: "/search", icon: Search, label: "Search" },
        { to: "/activity", icon: Activity, label: "Activity" },
        { to: "/agents", icon: Bot, label: "Agents" },
        { to: "/logs", icon: FileTerminal, label: "Logs" },
        { to: "/team", icon: Users, label: "Team" },
        { to: "/config", icon: Settings, label: "Configuration" },
        { to: "/devtools", icon: Wrench, label: "DevTools" },
        { to: "/help", icon: HelpCircle, label: "Help" },
    ];

    const toggleCollapse = () => setCollapsed(!collapsed);

    return (
        <div className="flex h-screen bg-background text-foreground overflow-hidden font-sans">
            {/* Sidebar */}
            <aside className={cn(
                "border-r bg-card flex flex-col transition-all duration-200",
                collapsed ? "w-16" : "w-64"
            )}>
                <div className={cn("border-b", collapsed ? "p-3" : "p-6")}>
                    <div className={cn("flex items-center mb-3", collapsed ? "justify-center" : "gap-2")}>
                        <div className="w-8 h-8 flex items-center justify-center flex-shrink-0">
                            <img src="/logo.png" alt="Oak CI" className="w-8 h-8 object-contain" />
                        </div>
                        {!collapsed && <span className="font-bold text-lg tracking-tight">Oak CI</span>}
                    </div>
                    {!collapsed && projectName && (
                        <div className="flex items-center gap-2 text-xs text-muted-foreground px-1">
                            <Folder className="w-3 h-3 flex-shrink-0" />
                            <span className="truncate" title={status?.project_root}>{projectName}</span>
                        </div>
                    )}
                </div>

                <nav className={cn("flex-1 space-y-1 overflow-y-auto", collapsed ? "p-2" : "p-4")}>
                    {navItems.map((item) => (
                        <NavItem
                            key={item.to}
                            {...item}
                            collapsed={collapsed}
                            active={location.pathname === item.to || (item.to !== "/" && location.pathname.startsWith(item.to))}
                        />
                    ))}
                </nav>

                <div className={cn("border-t", collapsed ? "p-2" : "p-4")}>
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

            {/* Main Content */}
            <main className="flex-1 flex flex-col overflow-hidden relative">
                <div className="flex-1 overflow-y-auto p-8 relative z-10">
                    <div className="max-w-6xl mx-auto">
                        <Outlet />
                    </div>
                </div>

                {/* Background decorative elements (Glassmorphism effect backing) */}
                <div className="absolute top-0 left-0 w-full h-full pointer-events-none z-0 overflow-hidden">
                    <div className="absolute top-[-20%] right-[-10%] w-[500px] h-[500px] bg-primary/5 rounded-full blur-[100px]" />
                    <div className="absolute bottom-[-20%] left-[-10%] w-[600px] h-[600px] bg-blue-500/5 rounded-full blur-[120px]" />
                </div>
            </main>
        </div>
    );
}
