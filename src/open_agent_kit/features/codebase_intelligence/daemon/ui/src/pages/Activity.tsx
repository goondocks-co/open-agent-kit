import { Link, Outlet, useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";
import { FolderGit2, FileText, Cpu } from "lucide-react";

export default function Activity() {
    const location = useLocation();
    const currentPath = location.pathname;

    const tabs = [
        { id: "sessions", label: "Sessions", path: "/activity/sessions", icon: FolderGit2 },
        { id: "plans", label: "Plans", path: "/activity/plans", icon: FileText },
        { id: "memories", label: "Memories", path: "/activity/memories", icon: Cpu },
    ];

    return (
        <div className="space-y-6">
            <div className="flex flex-col gap-2">
                <h1 className="text-3xl font-bold tracking-tight">Activity</h1>
                <p className="text-muted-foreground">Browse sessions, plans, and memories.</p>
            </div>

            <div className="flex items-center border-b">
                {tabs.map(tab => (
                    <Link
                        key={tab.id}
                        to={tab.path}
                        className={cn(
                            "px-4 py-2 text-sm font-medium border-b-2 transition-colors flex items-center gap-2",
                            currentPath.startsWith(tab.path)
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
    )
}
