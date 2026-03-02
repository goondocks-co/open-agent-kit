/**
 * Error card for displaying cloud relay start errors with expandable detail.
 */

import { useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle, ChevronDown, ChevronRight } from "lucide-react";
import type { CloudRelayStartResponse } from "@/hooks/use-cloud-relay";

export function ErrorCard({ response }: { response: CloudRelayStartResponse }) {
    const [showDetail, setShowDetail] = useState(false);
    return (
        <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription className="space-y-2">
                <p>{response.error}</p>
                {response.suggestion && (
                    <p className="text-sm opacity-80">{response.suggestion}</p>
                )}
                {response.detail && (
                    <div>
                        <button
                            onClick={() => setShowDetail(!showDetail)}
                            className="flex items-center gap-1 text-xs underline opacity-70 hover:opacity-100"
                        >
                            {showDetail ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                            {showDetail ? "Hide details" : "Show details"}
                        </button>
                        {showDetail && (
                            <pre className="mt-2 rounded-md bg-background/50 p-3 text-xs font-mono overflow-x-auto whitespace-pre-wrap border">
                                {response.detail}
                            </pre>
                        )}
                    </div>
                )}
            </AlertDescription>
        </Alert>
    );
}
