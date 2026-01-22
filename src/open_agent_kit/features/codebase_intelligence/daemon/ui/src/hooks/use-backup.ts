/**
 * React Query hooks for database backup and restore operations.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchJson } from "@/lib/api";
import { API_ENDPOINTS } from "@/lib/constants";

/** Backup status response from API */
interface BackupStatus {
    backup_exists: boolean;
    backup_path: string;
    backup_size_bytes?: number;
    last_modified?: string;
}

/** Request to create a backup */
interface BackupRequest {
    include_activities?: boolean;
    output_path?: string;
}

/** Request to restore from backup */
interface RestoreRequest {
    input_path?: string;
}

/** Response from backup/restore operations */
interface BackupResponse {
    status: string;
    message: string;
    backup_path: string;
    record_count: number;
}

/** Polling interval for backup status (5 seconds) */
const BACKUP_STATUS_REFETCH_INTERVAL_MS = 5000;

/**
 * Hook to get current backup file status.
 */
export function useBackupStatus() {
    return useQuery<BackupStatus>({
        queryKey: ["backup-status"],
        queryFn: () => fetchJson(API_ENDPOINTS.BACKUP_STATUS),
        refetchInterval: BACKUP_STATUS_REFETCH_INTERVAL_MS,
    });
}

/**
 * Hook to create a database backup.
 */
export function useCreateBackup() {
    const queryClient = useQueryClient();
    return useMutation<BackupResponse, Error, BackupRequest>({
        mutationFn: (request) =>
            fetchJson(API_ENDPOINTS.BACKUP_CREATE, {
                method: "POST",
                body: JSON.stringify(request),
            }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["backup-status"] });
        },
    });
}

/**
 * Hook to restore database from backup.
 */
export function useRestoreBackup() {
    const queryClient = useQueryClient();
    return useMutation<BackupResponse, Error, RestoreRequest>({
        mutationFn: (request) =>
            fetchJson(API_ENDPOINTS.BACKUP_RESTORE, {
                method: "POST",
                body: JSON.stringify(request),
            }),
        onSuccess: () => {
            // Invalidate memory stats after restore since data changed
            queryClient.invalidateQueries({ queryKey: ["memory-stats"] });
            queryClient.invalidateQueries({ queryKey: ["status"] });
        },
    });
}
