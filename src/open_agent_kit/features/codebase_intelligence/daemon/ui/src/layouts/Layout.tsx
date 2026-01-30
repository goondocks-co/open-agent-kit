import { Link, useLocation, Outlet } from "react-router-dom";
import { LayoutDashboard, Search, Activity, FileTerminal, Settings, Sun, Moon, Laptop, Wrench, Folder, HelpCircle, Users, Bot } from "lucide-react";
import { cn } from "@/lib/utils";
import { useTheme } from "@/components/theme-provider";
import { useStatus } from "@/hooks/use-status";

import type { LucideIcon } from "lucide-react";

const NavItem = ({ to, icon: Icon, label, active }: { to: string; icon: LucideIcon; label: string; active: boolean }) => (
    <Link
        to={to}
        className={cn(
            "flex items-center gap-3 px-3 py-2 rounded-md transition-colors text-sm font-medium",
            active
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-muted hover:text-foreground"
        )}
    >
        <Icon className="w-4 h-4" />
        {label}
    </Link>
);

export function Layout() {
    const location = useLocation();
    const { setTheme, theme } = useTheme();
    const { data: status } = useStatus();

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
        { to: "/help", icon: HelpCircle, label: "Setup Guide" },
        { to: "/devtools", icon: Wrench, label: "DevTools" },
    ];

    return (
        <div className="flex h-screen bg-background text-foreground overflow-hidden font-sans">
            {/* Sidebar */}
            <aside className="w-64 border-r bg-card flex flex-col">
                <div className="p-6 border-b">
                    <div className="flex items-center gap-2 mb-3">
                        <div className="w-8 h-8 flex items-center justify-center">
                            <img src="/logo.png" alt="Oak CI" className="w-8 h-8 object-contain" />
                        </div>
                        <span className="font-bold text-lg tracking-tight">Oak CI</span>
                    </div>
                    {projectName && (
                        <div className="flex items-center gap-2 text-xs text-muted-foreground px-1">
                            <Folder className="w-3 h-3 flex-shrink-0" />
                            <span className="truncate" title={status?.project_root}>{projectName}</span>
                        </div>
                    )}
                </div>

                <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
                    {navItems.map((item) => (
                        <NavItem
                            key={item.to}
                            {...item}
                            active={location.pathname === item.to || (item.to !== "/" && location.pathname.startsWith(item.to))}
                        />
                    ))}
                </nav>

                <div className="p-4 border-t">
                    <div className="flex items-center justify-between px-2 py-1 rounded-md bg-muted/50">
                        <button onClick={() => setTheme("light")} className={cn("p-1.5 rounded-sm transition-all", theme === "light" && "bg-background shadow-sm")}>
                            <Sun className="w-4 h-4" />
                        </button>
                        <button onClick={() => setTheme("system")} className={cn("p-1.5 rounded-sm transition-all", theme === "system" && "bg-background shadow-sm")}>
                            <Laptop className="w-4 h-4" />
                        </button>
                        <button onClick={() => setTheme("dark")} className={cn("p-1.5 rounded-sm transition-all", theme === "dark" && "bg-background shadow-sm")}>
                            <Moon className="w-4 h-4" />
                        </button>
                    </div>
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
