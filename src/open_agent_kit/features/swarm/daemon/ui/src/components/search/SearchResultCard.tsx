/**
 * Individual search result card — shows doc type, confidence, content preview, and metadata.
 */

import type { SearchMatch } from "@/hooks/use-swarm-search";
import {
    DOC_TYPE_COLORS,
    CONFIDENCE_THRESHOLDS,
    CONFIDENCE_BADGES,
} from "@/lib/constants";

interface SearchResultCardProps {
    match: SearchMatch;
}

function getConfidenceLevel(score?: number): "high" | "medium" | "low" {
    if (score === undefined) return "low";
    if (score >= CONFIDENCE_THRESHOLDS.HIGH) return "high";
    if (score >= CONFIDENCE_THRESHOLDS.MEDIUM) return "medium";
    return "low";
}

export function SearchResultCard({ match }: SearchResultCardProps) {
    const docType = match.doc_type ?? match.type;
    const docTypeColor =
        DOC_TYPE_COLORS[docType as keyof typeof DOC_TYPE_COLORS] ??
        "bg-muted text-muted-foreground";
    const confidenceLevel = getConfidenceLevel(match.score);
    const confidenceBadge = CONFIDENCE_BADGES[confidenceLevel];
    const isCode = docType === "code";

    return (
        <div className="border rounded-md p-3 text-sm">
            <div className="flex items-center gap-2 mb-2">
                <span
                    className={`text-xs font-medium px-2 py-0.5 rounded ${docTypeColor}`}
                >
                    {docType}
                </span>
                {match.score !== undefined && (
                    <span
                        className={`text-xs font-medium px-2 py-0.5 rounded ${confidenceBadge}`}
                    >
                        {confidenceLevel} ({match.score.toFixed(2)})
                    </span>
                )}
                {match.file_path && (
                    <span className="text-xs text-muted-foreground font-mono truncate ml-auto">
                        {match.file_path}
                    </span>
                )}
            </div>
            {isCode ? (
                <pre className="whitespace-pre-wrap text-xs text-muted-foreground bg-muted/50 rounded p-2 overflow-x-auto">
                    {match.content}
                </pre>
            ) : (
                <p className="text-xs text-muted-foreground whitespace-pre-wrap">
                    {match.content}
                </p>
            )}
        </div>
    );
}
