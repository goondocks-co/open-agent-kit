import { useQuery } from "@tanstack/react-query";
import { fetchJson } from "@/lib/api";
import { API_ENDPOINTS, STATUS_POLL_INTERVAL_MS } from "@/lib/constants";

export interface IndexStats {
    files_indexed: number;
    chunks_indexed: number;
    memories_stored: number;
    memories_unembedded: number;
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

export interface EmbeddingStats {
    providers: string[];
    total_embeds: number;
}

export interface SummarizationStatus {
    enabled: boolean;
    provider: string | null;
    model: string | null;
}

export interface StorageStats {
    sqlite_size_bytes: number;
    chromadb_size_bytes: number;
    sqlite_size_mb: string;
    chromadb_size_mb: string;
    total_size_mb: string;
}

export interface BackupSummary {
    exists: boolean;
    last_backup: string | null;
    age_hours: number | null;
    size_bytes?: number;
}

export interface DaemonStatus {
    status: string;
    indexing: boolean;
    embedding_provider: string | null;
    embedding_stats: EmbeddingStats | null;
    summarization: SummarizationStatus;
    uptime_seconds: number;
    project_root: string;
    index_stats: IndexStats;
    file_watcher: {
        enabled: boolean;
        running: boolean;
        pending_changes: number;
    };
    storage: StorageStats;
    backup: BackupSummary;
}

export function useStatus() {
    return useQuery<DaemonStatus>({
        queryKey: ["status"],
        queryFn: () => fetchJson(API_ENDPOINTS.STATUS),
        refetchInterval: STATUS_POLL_INTERVAL_MS,
    });
}
