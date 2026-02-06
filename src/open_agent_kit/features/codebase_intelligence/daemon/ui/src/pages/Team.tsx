import { Link, Outlet, useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";
import { HardDrive, Share2 } from "lucide-react";

export default function Team() {
    const location = useLocation();
    const currentPath = location.pathname;

    const tabs = [
        { id: "backups", label: "Backups", path: "/team/backups", icon: HardDrive },
        { id: "sharing", label: "Sharing", path: "/team/sharing", icon: Share2 },
    ];

    return (
        <div className="space-y-6 max-w-4xl mx-auto">
            <div className="flex flex-col gap-2">
                <h1 className="text-3xl font-bold tracking-tight">Team</h1>
                <p className="text-muted-foreground">
                    Share session history, memories, and your dashboard with your team.
                </p>
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
    );
}
