/**
 * Agents layout with tabs for Agents and Run History.
 *
 * Similar to DataExplorer, this provides a tabbed interface
 * for managing agents and viewing run history.
 */

import { Link, Outlet, useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";
import { Bot, Calendar, History } from "lucide-react";

export default function AgentsLayout() {
    const location = useLocation();
    const currentPath = location.pathname;

    const tabs = [
        { id: "list", label: "Agents", path: "/agents", icon: Bot, exact: true },
        { id: "runs", label: "Run History", path: "/agents/runs", icon: History },
        { id: "schedules", label: "Schedules", path: "/agents/schedules", icon: Calendar },
    ];

    const isActive = (tab: typeof tabs[0]) => {
        if (tab.exact) {
            return currentPath === tab.path;
        }
        return currentPath.startsWith(tab.path);
    };

    return (
        <div className="space-y-6">
            <div className="flex flex-col gap-2">
                <h1 className="text-3xl font-bold tracking-tight">Agents</h1>
                <p className="text-muted-foreground">
                    Autonomous agents powered by Claude Code SDK
                </p>
            </div>

            <div className="flex items-center border-b">
                {tabs.map((tab) => (
                    <Link
                        key={tab.id}
                        to={tab.path}
                        className={cn(
                            "px-4 py-2 text-sm font-medium border-b-2 transition-colors flex items-center gap-2",
                            isActive(tab)
                                ? "border-primary text-foreground"
                                : "border-transparent text-muted-foreground hover:text-foreground hover:border-muted"
                        )}
                    >
                        <tab.icon className="w-4 h-4" />
                        {tab.label}
                    </Link>
                ))}
            </div>

            <Outlet />
        </div>
    );
}
