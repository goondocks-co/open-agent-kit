/**
 * Groups search results by project, with collapsible overflow.
 */

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@oak/ui/components/ui/card";
import { Button } from "@oak/ui/components/ui/button";
import { ChevronDown, ChevronUp } from "lucide-react";
import type { ProjectResult } from "@/hooks/use-swarm-search";
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

    return (
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
                            <SearchResultCard key={j} match={match} />
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
    );
}
