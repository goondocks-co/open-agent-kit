import { Link } from "react-router-dom";
import { Cloud, Users, ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";
import type { DaemonStatus } from "@/hooks/use-status";

interface TeamStatusBannerProps {
    status: DaemonStatus | undefined;
}

function Pill({ children, className }: { children: React.ReactNode; className?: string }) {
    return (
        <span className={cn(
            "inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full",
            className,
        )}>
            {children}
        </span>
    );
}

function StatusDot({ color }: { color: "green" | "blue" }) {
    return (
        <span className={cn(
            "w-1.5 h-1.5 rounded-full flex-shrink-0",
            color === "green" && "bg-green-500",
            color === "blue" && "bg-blue-500",
        )} />
    );
}

export function TeamStatusBanner({ status }: TeamStatusBannerProps) {
    const team = status?.team;
    const cloudRelay = status?.cloud_relay;

    const showBanner = team?.configured || cloudRelay?.connected;
    if (!showBanner) return null;

    return (
        <div className="flex items-center gap-2 px-4 py-2 rounded-lg mb-4 bg-primary/5 border border-primary/20">
            <div className="flex items-center gap-2 flex-1 flex-wrap">
                {/* Team connected pill */}
                {team?.configured && (
                    <Pill className="bg-blue-500/10 text-blue-700 dark:text-blue-400">
                        <Users className="w-3 h-3" />
                        <StatusDot color={team.connected ? "green" : "blue"} />
                        {team.connected ? "Team Connected" : "Team Configured"}
                    </Pill>
                )}

                {/* Cloud Relay pill */}
                {cloudRelay?.connected && (
                    <Pill className="bg-green-500/10 text-green-700 dark:text-green-400">
                        <Cloud className="w-3 h-3" />
                        <StatusDot color="green" />
                        Cloud Active
                    </Pill>
                )}

                {/* Members pill */}
                {team?.configured && (team?.members_online ?? 0) > 0 && (
                    <Pill className="bg-muted text-muted-foreground">
                        <Users className="w-3 h-3" />
                        {team?.members_online} {team?.members_online === 1 ? "node" : "nodes"}
                    </Pill>
                )}
            </div>

            <Link
                to="/team"
                className="text-xs text-primary hover:underline flex items-center gap-1 flex-shrink-0"
            >
                Team
                <ArrowRight className="w-3 h-3" />
            </Link>
        </div>
    );
}
