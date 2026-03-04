import { Link, Outlet, useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";
import { ScrollText, ListChecks } from "lucide-react";

export default function Governance() {
    const location = useLocation();
    const currentPath = location.pathname;

    const tabs = [
        { id: "audit", label: "Audit Log", path: "/governance/audit", icon: ScrollText },
        { id: "rules", label: "Rules", path: "/governance/rules", icon: ListChecks },
    ];

    return (
        <div className="space-y-6">
            <div className="flex flex-col gap-2">
                <h1 className="text-3xl font-bold tracking-tight">Governance</h1>
                <p className="text-muted-foreground">
                    Monitor and control what your AI agents are allowed to do.
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
