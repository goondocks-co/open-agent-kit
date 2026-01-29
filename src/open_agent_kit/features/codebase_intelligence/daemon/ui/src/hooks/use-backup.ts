/**
 * React Query hooks for database backup and restore operations.
 *
 * Supports multi-machine/multi-user backups with content-based deduplication.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchJson } from "@/lib/api";
import { API_ENDPOINTS } from "@/lib/constants";

/** Info about a single backup file */
interface BackupFileInfo {
    filename: string;
    machine_id: string;
    size_bytes: number;
    last_modified: string;
}

/** Backup status response from API */
interface BackupStatus {
    backup_exists: boolean;
    backup_path: string;
    backup_size_bytes?: number;
    last_modified?: string;
    machine_id: string;
    all_backups: BackupFileInfo[];
}

/** Request to create a backup */
interface BackupRequest {
    include_activities?: boolean;
    output_path?: string;
}

/** Request to restore from backup */
interface RestoreRequest {
    input_path?: string;
    dry_run?: boolean;
}

/** Request to restore from all backups */
interface RestoreAllRequest {
    dry_run?: boolean;
}

/** Response from backup creation */
interface BackupResponse {
    status: string;
    message: string;
    backup_path: string;
    record_count: number;
    machine_id?: string;
}

/** Response from restore operations with deduplication stats */
interface RestoreResponse {
    status: string;
    message: string;
    backup_path?: string;
    sessions_imported: number;
    sessions_skipped: number;
    batches_imported: number;
    batches_skipped: number;
    observations_imported: number;
    observations_skipped: number;
    activities_imported: number;
    activities_skipped: number;
    errors: number;
    error_messages?: string[];  // Detailed error messages for debugging
}

/** Response from restore-all operations */
interface RestoreAllResponse {
    status: string;
    message: string;
    files_processed: number;
    total_imported: number;
    total_skipped: number;
    total_errors: number;
    per_file: Record<string, RestoreResponse>;
}

/** Polling interval for backup status (5 seconds) */
const BACKUP_STATUS_REFETCH_INTERVAL_MS = 5000;

/**
 * Hook to get current backup file status including all team backups.
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
 * Hook to restore database from backup with deduplication.
 */
export function useRestoreBackup() {
    const queryClient = useQueryClient();
    return useMutation<RestoreResponse, Error, RestoreRequest>({
        mutationFn: (request) =>
            fetchJson(API_ENDPOINTS.BACKUP_RESTORE, {
                method: "POST",
                body: JSON.stringify(request),
            }),
        onSuccess: () => {
            // Invalidate memory stats after restore since data changed
            queryClient.invalidateQueries({ queryKey: ["memory-stats"] });
            queryClient.invalidateQueries({ queryKey: ["status"] });
            queryClient.invalidateQueries({ queryKey: ["backup-status"] });
        },
    });
}

/**
 * Hook to restore from all backup files with deduplication.
 */
export function useRestoreAllBackups() {
    const queryClient = useQueryClient();
    return useMutation<RestoreAllResponse, Error, RestoreAllRequest>({
        mutationFn: (request) =>
            fetchJson(API_ENDPOINTS.BACKUP_RESTORE_ALL, {
                method: "POST",
                body: JSON.stringify(request),
            }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["memory-stats"] });
            queryClient.invalidateQueries({ queryKey: ["status"] });
            queryClient.invalidateQueries({ queryKey: ["backup-status"] });
        },
    });
}

// Export types for use in components
export type { BackupStatus, BackupFileInfo, RestoreResponse, RestoreAllResponse };
