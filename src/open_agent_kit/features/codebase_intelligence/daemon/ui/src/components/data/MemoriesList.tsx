import { useMemories } from "@/hooks/use-memories";
import { Link } from "react-router-dom";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { formatDate } from "@/lib/utils";
import { BrainCircuit } from "lucide-react";

export default function MemoriesList() {
    const { data, isLoading } = useMemories();

    if (isLoading) return <div>Loading memories...</div>;

    if (!data?.memories || data.memories.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center p-8 text-center border-2 border-dashed rounded-lg border-muted-foreground/25 bg-muted/5">
                <BrainCircuit className="w-10 h-10 text-muted-foreground mb-4 opacity-50" />
                <h3 className="text-lg font-medium">No memories found</h3>
                <p className="text-sm text-muted-foreground max-w-sm mt-2 mb-4">
                    The agent hasn't stored any memories yet. Memories are created when the agent discovers new information about the codebase.
                </p>
                <Link to="/config" className="text-sm font-medium text-primary hover:underline underline-offset-4">
                    Check Configuration &rarr;
                </Link>
            </div>
        );
    }

    return (
        <div className="grid gap-4 md:grid-cols-2">
            {data?.memories.map((mem) => (
                <Card key={mem.id} className="overflow-hidden">
                    <CardHeader className="py-3 bg-muted/30">
                        <CardTitle className="text-sm font-medium flex items-center justify-between">
                            <span className="flex items-center gap-2">
                                <BrainCircuit className="w-4 h-4 text-primary" />
                                <span className="capitalize">{mem.memory_type}</span>
                            </span>
                            <span className="text-xs text-muted-foreground">{formatDate(mem.created_at)}</span>
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="p-4 text-sm">
                        {mem.observation}
                        {mem.tags.length > 0 && (
                            <div className="mt-2 flex gap-1 flex-wrap">
                                {mem.tags.map(tag => (
                                    <span key={tag} className="text-xs px-2 py-0.5 rounded-full bg-secondary text-secondary-foreground font-mono">
                                        #{tag}
                                    </span>
                                ))}
                            </div>
                        )}
                    </CardContent>
                </Card>
            ))}
        </div>
    )
}
