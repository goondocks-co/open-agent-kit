/**
 * Groups search results by project, with collapsible overflow.
 * Owns a single fetch mutation shared across all cards in the group,
 * and a ContentDialog modal for viewing full content.
 */

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@oak/ui/components/ui/card";
import { ContentDialog } from "@oak/ui/components/ui/content-dialog";
import { Button } from "@oak/ui/components/ui/button";
import { ChevronDown, ChevronUp } from "lucide-react";
import type { ProjectResult, SearchMatch } from "@/hooks/use-swarm-search";
import { useSwarmFetch } from "@/hooks/use-swarm-fetch";
import { SearchResultCard } from "./SearchResultCard";
import { COLLAPSE_THRESHOLD } from "@/lib/constants";

interface ProjectResultGroupProps {
    result: ProjectResult;
}

export function ProjectResultGroup({ result }: ProjectResultGroupProps) {
    const [expanded, setExpanded] = useState(false);
    const matches = result.matches ?? [];
    const hasOverflow = matches.length > COLLAPSE_THRESHOLD;
    const visibleMatches = expanded ? matches : matches.slice(0, COLLAPSE_THRESHOLD);
    const hiddenCount = matches.length - COLLAPSE_THRESHOLD;

    // Shared fetch mutation for the group
    const fetchMutation = useSwarmFetch();

    // Modal state
    const [modalOpen, setModalOpen] = useState(false);
    const [modalTitle, setModalTitle] = useState("");
    const [modalContent, setModalContent] = useState("");
    const [fetchingId, setFetchingId] = useState<string | null>(null);
    const [fetchError, setFetchError] = useState<string | null>(null);

    async function handleViewFull(match: SearchMatch) {
        if (!match.id) return;

        setFetchingId(match.id);
        setFetchError(null);

        try {
            const data = await fetchMutation.mutateAsync({
                ids: [match.id],
                project_slug: result.project_slug,
            });
            const item = data.results[0];
            setModalTitle(match.doc_type ?? match.type ?? "Content");
            setModalContent(item?.content ?? "No content available");
            setModalOpen(true);
        } catch (err) {
            setFetchError(
                err instanceof Error ? err.message : "Fetch failed",
            );
        } finally {
            setFetchingId(null);
        }
    }

    return (
        <>
            <Card>
                <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                        <CardTitle className="text-base">{result.project_slug}</CardTitle>
                        <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
                            {matches.length} {matches.length === 1 ? "match" : "matches"}
                        </span>
                    </div>
                </CardHeader>
                <CardContent>
                    {matches.length > 0 ? (
                        <div className="space-y-3">
                            {visibleMatches.map((match, j) => (
                                <SearchResultCard
                                    key={match.id ?? j}
                                    match={match}
                                    onViewFull={match.id ? () => handleViewFull(match) : undefined}
                                    isFetching={fetchingId === match.id}
                                    fetchError={fetchingId === match.id ? fetchError : null}
                                />
                            ))}
                            {hasOverflow && (
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="w-full text-muted-foreground"
                                    onClick={() => setExpanded(!expanded)}
                                >
                                    {expanded ? (
                                        <>
                                            <ChevronUp className="h-4 w-4 mr-1" />
                                            Show less
                                        </>
                                    ) : (
                                        <>
                                            <ChevronDown className="h-4 w-4 mr-1" />
                                            Show {hiddenCount} more
                                        </>
                                    )}
                                </Button>
                            )}
                        </div>
                    ) : (
                        <p className="text-sm text-muted-foreground">No results</p>
                    )}
                </CardContent>
            </Card>

            <ContentDialog
                open={modalOpen}
                onOpenChange={setModalOpen}
                title={modalTitle}
                subtitle={result.project_slug}
                content={modalContent}
                renderMarkdown
            />
        </>
    );
}
