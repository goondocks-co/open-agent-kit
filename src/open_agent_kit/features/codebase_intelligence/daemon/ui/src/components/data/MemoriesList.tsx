import { useState } from "react";
import { useMemories } from "@/hooks/use-memories";
import { useDeleteMemory } from "@/hooks/use-delete";
import { Link } from "react-router-dom";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { ConfirmDialog, useConfirmDialog } from "@/components/ui/confirm-dialog";
import { formatDate } from "@/lib/utils";
import { BrainCircuit, Trash2 } from "lucide-react";
import { DELETE_CONFIRMATIONS } from "@/lib/constants";

const MEMORIES_PAGE_SIZE = 20;

export default function MemoriesList() {
    const [loadedMemories, setLoadedMemories] = useState<any[]>([]);
    const [offset, setOffset] = useState(0);

    const { data, isLoading, isFetching } = useMemories(MEMORIES_PAGE_SIZE, offset);
    const deleteMemory = useDeleteMemory();
    const { isOpen, setIsOpen, itemToDelete, openDialog, closeDialog } = useConfirmDialog();

    const handleLoadMore = () => {
        // Add current page memories to loaded memories
        setLoadedMemories(prev => [...prev, ...(data?.memories || [])]);
        setOffset(prev => prev + MEMORIES_PAGE_SIZE);
    };

    const handleDelete = async () => {
        if (!itemToDelete) return;
        try {
            await deleteMemory.mutateAsync(itemToDelete as string);
            closeDialog();
            // Reset pagination after deletion
            setOffset(0);
            setLoadedMemories([]);
        } catch (error) {
            console.error("Failed to delete memory:", error);
        }
    };

    const handleDeleteClick = (e: React.MouseEvent, memoryId: string) => {
        e.preventDefault();
        e.stopPropagation();
        openDialog(memoryId);
    };

    if (isLoading && offset === 0) return <div>Loading memories...</div>;

    // Combine loaded memories with current page
    const allMemories = offset === 0 ? (data?.memories || []) : [...loadedMemories, ...(data?.memories || [])];
    const hasMore = data?.memories && data.memories.length === MEMORIES_PAGE_SIZE;

    if (allMemories.length === 0) {
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
        <div className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
                {allMemories.map((mem) => (
                    <Card key={mem.id} className="overflow-hidden group relative">
                        <CardHeader className="py-3 bg-muted/30">
                            <CardTitle className="text-sm font-medium flex items-center justify-between">
                                <span className="flex items-center gap-2">
                                    <BrainCircuit className="w-4 h-4 text-primary" />
                                    <span className="capitalize">{mem.memory_type}</span>
                                </span>
                                <div className="flex items-center gap-2">
                                    <span className="text-xs text-muted-foreground">{formatDate(mem.created_at)}</span>
                                    <button
                                        onClick={(e) => handleDeleteClick(e, mem.id)}
                                        className="p-1 rounded text-muted-foreground hover:text-red-500 hover:bg-red-500/10 opacity-0 group-hover:opacity-100 transition-all"
                                        title="Delete memory"
                                    >
                                        <Trash2 className="w-3 h-3" />
                                    </button>
                                </div>
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="p-4 text-sm">
                            {mem.observation}
                            {mem.tags.length > 0 && (
                                <div className="mt-2 flex gap-1 flex-wrap">
                                    {mem.tags.map((tag: string) => (
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

            {hasMore && (
                <button
                    onClick={handleLoadMore}
                    disabled={isFetching}
                    className="w-full py-3 text-sm text-muted-foreground hover:text-foreground border border-dashed rounded-lg hover:border-muted-foreground/50 transition-colors disabled:opacity-50"
                >
                    {isFetching ? "Loading..." : "Load more memories"}
                </button>
            )}

            <ConfirmDialog
                open={isOpen}
                onOpenChange={setIsOpen}
                title={DELETE_CONFIRMATIONS.MEMORY.title}
                description={DELETE_CONFIRMATIONS.MEMORY.description}
                onConfirm={handleDelete}
                isLoading={deleteMemory.isPending}
            />
        </div>
    );
}
