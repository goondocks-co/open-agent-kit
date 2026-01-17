import { useSessions } from "@/hooks/use-activity";
import { Link } from "react-router-dom";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDate } from "@/lib/utils";
import { Terminal, Activity, Calendar, ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";

export default function SessionList() {
    const { data, isLoading } = useSessions();

    if (isLoading) {
        return <div>Loading sessions...</div>;
    }

    return (
        <div className="space-y-4">
            {data?.sessions.map((session) => (
                <Link key={session.id} to={`/data/sessions/${session.id}`}>
                    <Card className="hover:bg-accent/5 transition-colors cursor-pointer group">
                        <CardHeader className="py-4">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <div className={cn("p-2 rounded-md", session.status === "active" ? "bg-green-500/10 text-green-500" : "bg-muted text-muted-foreground")}>
                                        <Terminal className="w-4 h-4" />
                                    </div>
                                    <div>
                                        <CardTitle className="text-base font-medium flex items-center gap-2">
                                            Session {session.id.slice(0, 8)}...
                                            <span className={cn("text-xs px-2 py-0.5 rounded-full border",
                                                session.status === "active" ? "border-green-500/50 text-green-500" : "border-muted-foreground/30 text-muted-foreground")}>
                                                {session.status}
                                            </span>
                                        </CardTitle>
                                        <div className="text-xs text-muted-foreground mt-1 flex items-center gap-3">
                                            <span className="flex items-center gap-1"><Calendar className="w-3 h-3" /> {formatDate(session.started_at)}</span>
                                            <span className="flex items-center gap-1"><Activity className="w-3 h-3" /> {session.activity_count} activities</span>
                                        </div>
                                    </div>
                                </div>
                                <ArrowRight className="w-4 h-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                            </div>
                        </CardHeader>
                    </Card>
                </Link>
            ))}
            {data?.sessions.length === 0 && (
                <div className="text-center py-12 text-muted-foreground border border-dashed rounded-lg">
                    No sessions found. Start using 'agent' to generate activity.
                </div>
            )}
        </div>
    );
}
