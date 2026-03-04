import { Card, CardContent, CardHeader, CardTitle } from "@oak/ui/components/ui/card";
import { Bot } from "lucide-react";
import { useAgents } from "@/hooks/use-agents";

export default function Agents() {
    const { data, isLoading } = useAgents();

    const sessions = data?.sessions ? Object.entries(data.sessions) : [];

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold">Agents</h1>
                <p className="text-muted-foreground text-sm mt-1">
                    Active agent sessions
                </p>
            </div>

            {isLoading && <p className="text-sm text-muted-foreground">Loading...</p>}

            {sessions.length === 0 && !isLoading && (
                <Card>
                    <CardContent className="pt-6 text-center py-12">
                        <Bot className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                        <p className="text-muted-foreground">No active agent sessions</p>
                    </CardContent>
                </Card>
            )}

            <div className="grid gap-4">
                {sessions.map(([id, session]) => (
                    <Card key={id}>
                        <CardHeader className="pb-3">
                            <CardTitle className="text-base font-mono text-sm">{id}</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <pre className="text-xs text-muted-foreground whitespace-pre-wrap">
                                {JSON.stringify(session, null, 2)}
                            </pre>
                        </CardContent>
                    </Card>
                ))}
            </div>
        </div>
    );
}
