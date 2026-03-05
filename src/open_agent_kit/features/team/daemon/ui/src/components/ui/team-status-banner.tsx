import { Link } from "react-router-dom";
import { Cloud, Users, ArrowRight, AlertTriangle, Info, AlertOctagon } from "lucide-react";
import { cn } from "@/lib/utils";
import type { DaemonStatus } from "@/hooks/use-status";
import { useSwarmAdvisories, type SwarmAdvisory } from "@/hooks/use-swarm";

const OAK_RELEASES_URL = "https://github.com/goondocks-co/open-agent-kit/releases";

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

const ADVISORY_STYLES: Record<SwarmAdvisory["severity"], { pill: string; icon: typeof AlertTriangle }> = {
    info: { pill: "bg-blue-500/10 text-blue-700 dark:text-blue-400", icon: Info },
    warning: { pill: "bg-amber-500/10 text-amber-700 dark:text-amber-400", icon: AlertTriangle },
    critical: { pill: "bg-red-500/10 text-red-700 dark:text-red-400", icon: AlertOctagon },
};

function AdvisoryPill({ advisory }: { advisory: SwarmAdvisory }) {
    const style = ADVISORY_STYLES[advisory.severity];
    const Icon = style.icon;

    // For version_drift, show a concise clickable pill linking to releases
    if (advisory.type === "version_drift" && advisory.metadata?.minimum) {
        return (
            <a href={OAK_RELEASES_URL} target="_blank" rel="noopener noreferrer">
                <Pill className={cn(style.pill, "cursor-pointer hover:opacity-80")}>
                    <Icon className="w-3 h-3" />
                    min {String(advisory.metadata.minimum)} recommended
                </Pill>
            </a>
        );
    }

    return (
        <Pill className={style.pill}>
            <Icon className="w-3 h-3" />
            {advisory.message}
        </Pill>
    );
}

export function TeamStatusBanner({ status }: TeamStatusBannerProps) {
    const team = status?.team;
    const cloudRelay = status?.cloud_relay;
    const { data: advisoryData } = useSwarmAdvisories();
    const advisories = advisoryData?.advisories ?? [];

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

                {/* Swarm advisories */}
                {advisories.map((advisory, i) => (
                    <AdvisoryPill key={`${advisory.type}-${i}`} advisory={advisory} />
                ))}
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
