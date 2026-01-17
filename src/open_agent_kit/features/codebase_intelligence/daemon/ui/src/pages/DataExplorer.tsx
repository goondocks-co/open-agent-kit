import { Link, Outlet, useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";
import { FolderGit2, Cpu } from "lucide-react";

export default function DataExplorer() {
    const location = useLocation();
    const currentPath = location.pathname;

    const tabs = [
        { id: "sessions", label: "Sessions", path: "/data/sessions", icon: FolderGit2 },
        { id: "memories", label: "Memories", path: "/data/memories", icon: Cpu },
    ];

    return (
        <div className="space-y-6">
            <div className="flex flex-col gap-2">
                <h1 className="text-3xl font-bold tracking-tight">Data Explorer</h1>
                <p className="text-muted-foreground">Inspect raw data stored in SQLite.</p>
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
