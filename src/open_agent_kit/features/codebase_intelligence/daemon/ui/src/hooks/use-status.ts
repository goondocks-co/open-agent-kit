import { useQuery } from "@tanstack/react-query";
import { fetchJson } from "@/lib/api";

export interface IndexStats {
    files_indexed: number;
    chunks_indexed: number;
    memories_stored: number;
    last_indexed: string | null;
    duration_seconds: number;
    status: string;
    progress: number;
    total: number;
    ast_stats?: {
        ast_success: number;
        ast_fallback: number;
        line_based: number;
    };
}

export interface DaemonStatus {
    status: string;
    indexing: boolean;
    embedding_provider: string | null;
    uptime_seconds: number;
    project_root: string;
    index_stats: IndexStats;
    file_watcher: {
        enabled: boolean;
        running: boolean;
        pending_changes: number;
    };
}

export function useStatus() {
    return useQuery<DaemonStatus>({
        queryKey: ["status"],
        queryFn: () => fetchJson("/api/status"),
        refetchInterval: 2000, // Poll every 2s
    });
}
