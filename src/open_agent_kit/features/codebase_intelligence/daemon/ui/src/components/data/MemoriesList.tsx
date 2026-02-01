import { useState } from "react";
import { useMemories, useMemoryTags, useArchiveMemory, useUnarchiveMemory, useBulkMemories } from "@/hooks/use-memories";
import { useDeleteMemory } from "@/hooks/use-delete";
import { Link } from "react-router-dom";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { ConfirmDialog, useConfirmDialog } from "@/components/ui/confirm-dialog";
import { ContentDialog, useContentDialog } from "@/components/ui/content-dialog";
import { Markdown } from "@/components/ui/markdown";
import { formatDate } from "@/lib/utils";
import { BrainCircuit, Trash2, Filter, Tag, Calendar, Archive, ArchiveRestore, CheckSquare, Square, X, Plus, Minus, Maximize2 } from "lucide-react";
import {
    DELETE_CONFIRMATIONS,
    MEMORY_TYPE_FILTER_OPTIONS,
    MEMORY_TYPE_BADGE_CLASSES,
    MEMORY_TYPE_LABELS,
    DATE_RANGE_OPTIONS,
    getDateRangeStart,
    BULK_ACTIONS,
    MEMORY_OBSERVATION_TRUNCATION_LIMIT,
    MEMORY_TYPES,
} from "@/lib/constants";
import type { MemoryTypeFilter, MemoryType, DateRangePreset, BulkAction } from "@/lib/constants";

import type { MemoryListItem } from "@/hooks/use-memories";

const MEMORIES_PAGE_SIZE = 20;

export default function MemoriesList() {
    const [loadedMemories, setLoadedMemories] = useState<MemoryListItem[]>([]);
    const [offset, setOffset] = useState(0);
    const [memoryType, setMemoryType] = useState<MemoryTypeFilter>("all");
    const [selectedTag, setSelectedTag] = useState<string>("");
    const [dateRange, setDateRange] = useState<DateRangePreset>("all");
    const [includeArchived, setIncludeArchived] = useState(false);
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const [bulkTagInput, setBulkTagInput] = useState("");
    const [showTagInput, setShowTagInput] = useState<"add" | "remove" | null>(null);

    const startDate = getDateRangeStart(dateRange);

    const { data, isLoading, isFetching } = useMemories({
        limit: MEMORIES_PAGE_SIZE,
        offset,
        memoryType,
        tag: selectedTag,
        startDate,
        includeArchived,
    });
    const { data: tagsData } = useMemoryTags();
    const deleteMemory = useDeleteMemory();
    const archiveMemory = useArchiveMemory();
    const unarchiveMemory = useUnarchiveMemory();
    const bulkMemories = useBulkMemories();
    const { isOpen, setIsOpen, itemToDelete, openDialog, closeDialog } = useConfirmDialog();
    const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);
    const { isOpen: isContentOpen, setIsOpen: setContentOpen, dialogContent, openDialog: openContentDialog } = useContentDialog();

    /** Check if observation content is truncated */
    const isContentTruncated = (observation: string): boolean => {
        return observation.length > MEMORY_OBSERVATION_TRUNCATION_LIMIT;
    };

    /** Get truncated observation text */
    const getTruncatedObservation = (observation: string): string => {
        if (observation.length <= MEMORY_OBSERVATION_TRUNCATION_LIMIT) {
            return observation;
        }
        return observation.slice(0, MEMORY_OBSERVATION_TRUNCATION_LIMIT) + "...";
    };

    /** Get display label for memory type */
    const getMemoryTypeLabel = (type: string): string => {
        return MEMORY_TYPE_LABELS[type as MemoryType] || type.replace(/_/g, " ");
    };

    const handleLoadMore = () => {
        // Add current page memories to loaded memories
        setLoadedMemories(prev => [...prev, ...(data?.memories || [])]);
        setOffset(prev => prev + MEMORIES_PAGE_SIZE);
    };

    const handleFilterChange = (newFilter: MemoryTypeFilter) => {
        setMemoryType(newFilter);
        // Reset pagination when filter changes
        setOffset(0);
        setLoadedMemories([]);
    };

    const handleTagFilterChange = (newTag: string) => {
        setSelectedTag(newTag);
        // Reset pagination when filter changes
        setOffset(0);
        setLoadedMemories([]);
    };

    const handleDateRangeChange = (newRange: DateRangePreset) => {
        setDateRange(newRange);
        // Reset pagination when filter changes
        setOffset(0);
        setLoadedMemories([]);
    };

    const handleArchiveToggle = () => {
        setIncludeArchived(prev => !prev);
        setOffset(0);
        setLoadedMemories([]);
    };

    const handleArchiveClick = async (e: React.MouseEvent, memoryId: string) => {
        e.preventDefault();
        e.stopPropagation();
        await archiveMemory.mutateAsync(memoryId);
        setOffset(0);
        setLoadedMemories([]);
    };

    const handleUnarchiveClick = async (e: React.MouseEvent, memoryId: string) => {
        e.preventDefault();
        e.stopPropagation();
        await unarchiveMemory.mutateAsync(memoryId);
        setOffset(0);
        setLoadedMemories([]);
    };

    const clearAllFilters = () => {
        setMemoryType("all");
        setSelectedTag("");
        setDateRange("all");
        setIncludeArchived(false);
        setOffset(0);
        setLoadedMemories([]);
    };

    const hasActiveFilters = memoryType !== "all" || selectedTag !== "" || dateRange !== "all" || includeArchived;

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

    // Bulk selection handlers (defined after allMemories)
    const toggleSelection = (memoryId: string) => {
        setSelectedIds(prev => {
            const next = new Set(prev);
            if (next.has(memoryId)) {
                next.delete(memoryId);
            } else {
                next.add(memoryId);
            }
            return next;
        });
    };

    const selectAll = () => {
        const allIds = allMemories.map((m: { id: string }) => m.id);
        setSelectedIds(new Set(allIds));
    };

    const deselectAll = () => {
        setSelectedIds(new Set());
    };

    const handleBulkAction = async (action: BulkAction, tag?: string) => {
        if (selectedIds.size === 0) return;

        try {
            await bulkMemories.mutateAsync({
                memory_ids: Array.from(selectedIds),
                action,
                tag,
            });
            setSelectedIds(new Set());
            setBulkTagInput("");
            setShowTagInput(null);
            setOffset(0);
            setLoadedMemories([]);
        } catch (error) {
            console.error("Bulk operation failed:", error);
        }
    };

    const handleBulkDelete = async () => {
        await handleBulkAction(BULK_ACTIONS.DELETE);
        setBulkDeleteOpen(false);
    };

    // Helper to get badge class for memory type
    const getMemoryTypeBadgeClass = (type: string): string => {
        return MEMORY_TYPE_BADGE_CLASSES[type as MemoryType] || "bg-gray-500/10 text-gray-600";
    };

    if (allMemories.length === 0) {
        return (
            <div className="space-y-4">
                {/* Filter bar - always visible */}
                <div className="flex items-center gap-3">
                    <Filter className="w-4 h-4 text-muted-foreground" />
                    <select
                        className="bg-background border border-input rounded-md px-3 py-1.5 text-sm font-medium"
                        value={memoryType}
                        onChange={(e) => handleFilterChange(e.target.value as MemoryTypeFilter)}
                        title="Filter by memory type"
                    >
                        {MEMORY_TYPE_FILTER_OPTIONS.map((option) => (
                            <option key={option.value} value={option.value}>{option.label}</option>
                        ))}
                    </select>
                    <Tag className="w-4 h-4 text-muted-foreground ml-2" />
                    <select
                        className="bg-background border border-input rounded-md px-3 py-1.5 text-sm font-medium"
                        value={selectedTag}
                        onChange={(e) => handleTagFilterChange(e.target.value)}
                        title="Filter by tag"
                    >
                        <option value="">All Tags</option>
                        {tagsData?.tags.map((tag) => (
                            <option key={tag} value={tag}>{tag}</option>
                        ))}
                    </select>
                    <Calendar className="w-4 h-4 text-muted-foreground ml-2" />
                    <select
                        className="bg-background border border-input rounded-md px-3 py-1.5 text-sm font-medium"
                        value={dateRange}
                        onChange={(e) => handleDateRangeChange(e.target.value as DateRangePreset)}
                        title="Filter by date range"
                    >
                        {DATE_RANGE_OPTIONS.map((option) => (
                            <option key={option.value} value={option.value}>{option.label}</option>
                        ))}
                    </select>
                    <label className="flex items-center gap-1.5 ml-2 text-sm cursor-pointer">
                        <input
                            type="checkbox"
                            checked={includeArchived}
                            onChange={handleArchiveToggle}
                            className="rounded border-input"
                        />
                        <Archive className="w-3.5 h-3.5 text-muted-foreground" />
                        <span className="text-muted-foreground">Archived</span>
                    </label>
                    {hasActiveFilters && (
                        <button
                            onClick={clearAllFilters}
                            className="text-xs text-muted-foreground hover:text-foreground"
                        >
                            Clear all
                        </button>
                    )}
                </div>

                <div className="flex flex-col items-center justify-center p-8 text-center border-2 border-dashed rounded-lg border-muted-foreground/25 bg-muted/5">
                    <BrainCircuit className="w-10 h-10 text-muted-foreground mb-4 opacity-50" />
                    <h3 className="text-lg font-medium">
                        {hasActiveFilters ? "No matching memories" : "No memories found"}
                    </h3>
                    <p className="text-sm text-muted-foreground max-w-sm mt-2 mb-4">
                        {hasActiveFilters
                            ? "No memories match your current filters. Try adjusting or clearing filters."
                            : "The agent hasn't stored any memories yet. Memories are created when the agent discovers new information about the codebase."}
                    </p>
                    {hasActiveFilters ? (
                        <button
                            onClick={clearAllFilters}
                            className="text-sm font-medium text-primary hover:underline underline-offset-4"
                        >
                            Clear filters &rarr;
                        </button>
                    ) : (
                        <Link to="/config" className="text-sm font-medium text-primary hover:underline underline-offset-4">
                            Check Configuration &rarr;
                        </Link>
                    )}
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-4">
            {/* Filter bar */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <Filter className="w-4 h-4 text-muted-foreground" />
                    <select
                        className="bg-background border border-input rounded-md px-3 py-1.5 text-sm font-medium"
                        value={memoryType}
                        onChange={(e) => handleFilterChange(e.target.value as MemoryTypeFilter)}
                        title="Filter by memory type"
                    >
                        {MEMORY_TYPE_FILTER_OPTIONS.map((option) => (
                            <option key={option.value} value={option.value}>{option.label}</option>
                        ))}
                    </select>
                    <Tag className="w-4 h-4 text-muted-foreground ml-2" />
                    <select
                        className="bg-background border border-input rounded-md px-3 py-1.5 text-sm font-medium"
                        value={selectedTag}
                        onChange={(e) => handleTagFilterChange(e.target.value)}
                        title="Filter by tag"
                    >
                        <option value="">All Tags</option>
                        {tagsData?.tags.map((tag) => (
                            <option key={tag} value={tag}>{tag}</option>
                        ))}
                    </select>
                    <Calendar className="w-4 h-4 text-muted-foreground ml-2" />
                    <select
                        className="bg-background border border-input rounded-md px-3 py-1.5 text-sm font-medium"
                        value={dateRange}
                        onChange={(e) => handleDateRangeChange(e.target.value as DateRangePreset)}
                        title="Filter by date range"
                    >
                        {DATE_RANGE_OPTIONS.map((option) => (
                            <option key={option.value} value={option.value}>{option.label}</option>
                        ))}
                    </select>
                    <label className="flex items-center gap-1.5 ml-2 text-sm cursor-pointer">
                        <input
                            type="checkbox"
                            checked={includeArchived}
                            onChange={handleArchiveToggle}
                            className="rounded border-input"
                        />
                        <Archive className="w-3.5 h-3.5 text-muted-foreground" />
                        <span className="text-muted-foreground">Archived</span>
                    </label>
                    {hasActiveFilters && (
                        <button
                            onClick={clearAllFilters}
                            className="text-xs text-muted-foreground hover:text-foreground"
                        >
                            Clear all
                        </button>
                    )}
                </div>
                <span className="text-xs text-muted-foreground">
                    {data?.total || allMemories.length} memories
                </span>
            </div>

            {/* Bulk action bar - shown when items are selected */}
            {selectedIds.size > 0 && (
                <div className="flex items-center gap-3 p-3 bg-muted/50 rounded-lg border">
                    <div className="flex items-center gap-2">
                        <button
                            onClick={deselectAll}
                            className="p-1 rounded hover:bg-background"
                            title="Clear selection"
                        >
                            <X className="w-4 h-4" />
                        </button>
                        <span className="text-sm font-medium">
                            {selectedIds.size} selected
                        </span>
                    </div>
                    <div className="h-4 w-px bg-border" />
                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => handleBulkAction(BULK_ACTIONS.ARCHIVE)}
                            disabled={bulkMemories.isPending}
                            className="flex items-center gap-1 px-2 py-1 text-xs rounded bg-amber-500/10 text-amber-600 hover:bg-amber-500/20"
                        >
                            <Archive className="w-3 h-3" />
                            Archive
                        </button>
                        <button
                            onClick={() => handleBulkAction(BULK_ACTIONS.UNARCHIVE)}
                            disabled={bulkMemories.isPending}
                            className="flex items-center gap-1 px-2 py-1 text-xs rounded bg-primary/10 text-primary hover:bg-primary/20"
                        >
                            <ArchiveRestore className="w-3 h-3" />
                            Unarchive
                        </button>
                        <div className="relative">
                            {showTagInput === "add" ? (
                                <div className="flex items-center gap-1">
                                    <input
                                        type="text"
                                        value={bulkTagInput}
                                        onChange={(e) => setBulkTagInput(e.target.value)}
                                        placeholder="Tag name..."
                                        className="w-24 px-2 py-1 text-xs rounded border bg-background"
                                        autoFocus
                                        onKeyDown={(e) => {
                                            if (e.key === "Enter" && bulkTagInput.trim()) {
                                                handleBulkAction(BULK_ACTIONS.ADD_TAG, bulkTagInput.trim());
                                            } else if (e.key === "Escape") {
                                                setShowTagInput(null);
                                                setBulkTagInput("");
                                            }
                                        }}
                                    />
                                    <button
                                        onClick={() => { setShowTagInput(null); setBulkTagInput(""); }}
                                        className="p-1 rounded hover:bg-muted"
                                    >
                                        <X className="w-3 h-3" />
                                    </button>
                                </div>
                            ) : (
                                <button
                                    onClick={() => setShowTagInput("add")}
                                    disabled={bulkMemories.isPending}
                                    className="flex items-center gap-1 px-2 py-1 text-xs rounded bg-green-500/10 text-green-600 hover:bg-green-500/20"
                                >
                                    <Plus className="w-3 h-3" />
                                    Add Tag
                                </button>
                            )}
                        </div>
                        <div className="relative">
                            {showTagInput === "remove" ? (
                                <div className="flex items-center gap-1">
                                    <select
                                        value={bulkTagInput}
                                        onChange={(e) => {
                                            if (e.target.value) {
                                                handleBulkAction(BULK_ACTIONS.REMOVE_TAG, e.target.value);
                                            }
                                        }}
                                        className="w-24 px-2 py-1 text-xs rounded border bg-background"
                                        autoFocus
                                    >
                                        <option value="">Select tag...</option>
                                        {tagsData?.tags.map((tag) => (
                                            <option key={tag} value={tag}>{tag}</option>
                                        ))}
                                    </select>
                                    <button
                                        onClick={() => { setShowTagInput(null); setBulkTagInput(""); }}
                                        className="p-1 rounded hover:bg-muted"
                                    >
                                        <X className="w-3 h-3" />
                                    </button>
                                </div>
                            ) : (
                                <button
                                    onClick={() => setShowTagInput("remove")}
                                    disabled={bulkMemories.isPending}
                                    className="flex items-center gap-1 px-2 py-1 text-xs rounded bg-orange-500/10 text-orange-600 hover:bg-orange-500/20"
                                >
                                    <Minus className="w-3 h-3" />
                                    Remove Tag
                                </button>
                            )}
                        </div>
                        <button
                            onClick={() => setBulkDeleteOpen(true)}
                            disabled={bulkMemories.isPending}
                            className="flex items-center gap-1 px-2 py-1 text-xs rounded bg-red-500/10 text-red-600 hover:bg-red-500/20"
                        >
                            <Trash2 className="w-3 h-3" />
                            Delete
                        </button>
                    </div>
                    <div className="ml-auto">
                        <button
                            onClick={selectAll}
                            className="text-xs text-muted-foreground hover:text-foreground"
                        >
                            Select all ({allMemories.length})
                        </button>
                    </div>
                </div>
            )}

            <div className="grid gap-4 md:grid-cols-2">
                {allMemories.map((mem) => (
                    <Card key={mem.id} className={`overflow-hidden group relative ${mem.archived ? "opacity-60" : ""} ${selectedIds.has(mem.id) ? "ring-2 ring-primary" : ""}`}>
                        <CardHeader className="py-3 bg-muted/30">
                            <CardTitle className="text-sm font-medium flex items-center justify-between">
                                <span className="flex items-center gap-2">
                                    <button
                                        onClick={() => toggleSelection(mem.id)}
                                        className="p-0.5 rounded hover:bg-muted"
                                        title={selectedIds.has(mem.id) ? "Deselect" : "Select"}
                                    >
                                        {selectedIds.has(mem.id) ? (
                                            <CheckSquare className="w-4 h-4 text-primary" />
                                        ) : (
                                            <Square className="w-4 h-4 text-muted-foreground" />
                                        )}
                                    </button>
                                    <BrainCircuit className="w-4 h-4 text-primary" />
                                    <span className={`text-xs px-2 py-0.5 rounded-full ${getMemoryTypeBadgeClass(mem.memory_type)}`}>
                                        {mem.memory_type.replace(/_/g, " ")}
                                    </span>
                                    {mem.archived && (
                                        <span className="text-xs px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
                                            archived
                                        </span>
                                    )}
                                </span>
                                <div className="flex items-center gap-2">
                                    <span className="text-xs text-muted-foreground">{formatDate(mem.created_at)}</span>
                                    {mem.archived ? (
                                        <button
                                            onClick={(e) => handleUnarchiveClick(e, mem.id)}
                                            className="p-1 rounded text-muted-foreground hover:text-primary hover:bg-primary/10 opacity-0 group-hover:opacity-100 transition-all"
                                            title="Unarchive memory"
                                            disabled={unarchiveMemory.isPending}
                                        >
                                            <ArchiveRestore className="w-3 h-3" />
                                        </button>
                                    ) : (
                                        <button
                                            onClick={(e) => handleArchiveClick(e, mem.id)}
                                            className="p-1 rounded text-muted-foreground hover:text-amber-500 hover:bg-amber-500/10 opacity-0 group-hover:opacity-100 transition-all"
                                            title="Archive memory"
                                            disabled={archiveMemory.isPending}
                                        >
                                            <Archive className="w-3 h-3" />
                                        </button>
                                    )}
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
                            {mem.memory_type === MEMORY_TYPES.SESSION_SUMMARY ? (
                                <Markdown content={getTruncatedObservation(mem.observation)} />
                            ) : (
                                <div className="whitespace-pre-wrap">
                                    {getTruncatedObservation(mem.observation)}
                                </div>
                            )}
                            {isContentTruncated(mem.observation) && (
                                <button
                                    onClick={() => openContentDialog(
                                        `${getMemoryTypeLabel(mem.memory_type)} Memory`,
                                        mem.observation,
                                        mem.context || undefined,
                                        mem.memory_type === MEMORY_TYPES.SESSION_SUMMARY
                                    )}
                                    className="mt-2 flex items-center gap-1 text-xs text-primary hover:underline"
                                >
                                    <Maximize2 className="w-3 h-3" />
                                    View Full Memory
                                </button>
                            )}
                            {mem.tags.length > 0 && (
                                <div className="mt-2 flex gap-1 flex-wrap">
                                    {mem.tags.map((tag: string) => (
                                        <button
                                            key={tag}
                                            onClick={() => handleTagFilterChange(tag)}
                                            className={`text-xs px-2 py-0.5 rounded-full font-mono transition-colors ${
                                                selectedTag === tag
                                                    ? "bg-primary text-primary-foreground"
                                                    : "bg-secondary text-secondary-foreground hover:bg-secondary/80"
                                            }`}
                                            title={`Filter by #${tag}`}
                                        >
                                            #{tag}
                                        </button>
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

            <ConfirmDialog
                open={bulkDeleteOpen}
                onOpenChange={setBulkDeleteOpen}
                title={`Delete ${selectedIds.size} Memories`}
                description={`This will permanently delete ${selectedIds.size} selected memories. This action cannot be undone.`}
                onConfirm={handleBulkDelete}
                isLoading={bulkMemories.isPending}
            />

            {dialogContent && (
                <ContentDialog
                    open={isContentOpen}
                    onOpenChange={setContentOpen}
                    title={dialogContent.title}
                    subtitle={dialogContent.subtitle}
                    content={dialogContent.content}
                    icon={<BrainCircuit className="h-5 w-5 text-primary" />}
                    renderMarkdown={dialogContent.renderMarkdown}
                />
            )}
        </div>
    );
}
