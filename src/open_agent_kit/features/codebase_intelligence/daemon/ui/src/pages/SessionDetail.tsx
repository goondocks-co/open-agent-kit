import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useSession } from "@/hooks/use-activity";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { PromptBatchActivities } from "@/components/data/PromptBatchActivities";
import { formatDate } from "@/lib/utils";
import { ArrowLeft, Terminal, MessageSquare, Clock, ChevronDown, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

export default function SessionDetail() {
    const { id } = useParams();
    const { data, isLoading } = useSession(id);
    const [expandedBatches, setExpandedBatches] = useState<Record<string, boolean>>({});

    const toggleBatch = (batchId: string) => {
        setExpandedBatches(prev => ({ ...prev, [batchId]: !prev[batchId] }));
    };

    if (isLoading) return <div>Loading session details...</div>;
    if (!data) return <div>Session not found</div>;

    const { session, prompt_batches } = data;

    return (
        <div className="space-y-6">
            <div className="flex items-center gap-4">
                <Link to="/data/sessions" className="p-2 hover:bg-accent rounded-full">
                    <ArrowLeft className="w-5 h-5" />
                </Link>
                <h1 className="text-2xl font-bold tracking-tight">Session {session.id.slice(0, 8)}</h1>
            </div>

            <div className="grid gap-4 md:grid-cols-4">
                <Card>
                    <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Status</CardTitle></CardHeader>
                    <CardContent>
                        <div className="flex items-center gap-2">
                            <span className={cn("w-2 h-2 rounded-full", session.status === "active" ? "bg-green-500" : "bg-muted-foreground")} />
                            <span className="capitalize font-medium">{session.status}</span>
                        </div>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Started</CardTitle></CardHeader>
                    <CardContent className="text-sm">{formatDate(session.started_at)}</CardContent>
                </Card>
                <Card>
                    <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Prompts</CardTitle></CardHeader>
                    <CardContent className="text-2xl font-bold">{session.prompt_batch_count}</CardContent>
                </Card>
                <Card>
                    <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Activities</CardTitle></CardHeader>
                    <CardContent className="text-2xl font-bold">{session.activity_count}</CardContent>
                </Card>
            </div>

            <div className="space-y-6">
                <h2 className="text-xl font-semibold">Timeline</h2>
                <div className="relative border-l ml-4 space-y-8 pl-8 pb-8">
                    {prompt_batches.map((batch) => (
                        <div key={batch.id} className="relative">
                            <span className="absolute -left-[41px] bg-background p-1 border rounded-full">
                                <MessageSquare className="w-4 h-4 text-muted-foreground" />
                            </span>
                            <div className="mb-2">
                                <p className="font-medium text-sm text-muted-foreground mb-1">Prompt #{batch.prompt_number}</p>
                                <div className="p-4 bg-muted/30 rounded-lg border text-sm whitespace-pre-wrap">
                                    {batch.user_prompt || "No prompt text provided"}
                                </div>
                            </div>

                            {/* We could list activities here if we had them in the batch object, 
                                seeing as the API returns them separately, we might need to fetch them or user `recent_activities` 
                                For now, we show the batch info */}
                            <div className="text-xs text-muted-foreground flex items-center gap-4 mt-2">
                                <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> {formatDate(batch.started_at)}</span>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-6 gap-1 text-xs"
                                    onClick={() => toggleBatch(batch.id)}
                                >
                                    {expandedBatches[batch.id] ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                                    <Terminal className="w-3 h-3" /> {batch.activity_count > 0 ? `${batch.activity_count} activities` : "View activities"}
                                </Button>
                            </div>

                            {expandedBatches[batch.id] && (
                                <PromptBatchActivities batchId={batch.id} />
                            )}
                        </div>
                    ))}
                </div>
            </div>
        </div>
    )
}
