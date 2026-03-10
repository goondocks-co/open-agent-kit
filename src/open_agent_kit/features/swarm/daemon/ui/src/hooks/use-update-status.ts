import {
    useUpdateStatus as useUpdateStatusShared,
    useUpdateCheck as useUpdateCheckShared,
    useUpdateApply as useUpdateApplyShared,
    useUpdateChannel as useUpdateChannelShared,
} from "@oak/ui/hooks/use-update-status";
import { fetchJson, postJson, putJson } from "@/lib/api";
import { API_ENDPOINTS } from "@/lib/constants";

export type { UpdateStatus, StagedUpdate, LastCheck, CheckResult } from "@oak/ui/hooks/use-update-status";

export function useUpdateStatus() {
    return useUpdateStatusShared(
        API_ENDPOINTS.UPDATE_STATUS,
        fetchJson as (url: string, init?: RequestInit) => Promise<unknown>,
    );
}

export function useUpdateCheck() {
    return useUpdateCheckShared(
        API_ENDPOINTS.UPDATE_CHECK,
        postJson as (url: string, body: unknown) => Promise<unknown>,
    );
}

export function useUpdateApply() {
    return useUpdateApplyShared(
        API_ENDPOINTS.UPDATE_APPLY,
        postJson as (url: string, body: unknown) => Promise<unknown>,
    );
}

export function useUpdateChannel() {
    return useUpdateChannelShared(
        API_ENDPOINTS.UPDATE_CHANNEL,
        putJson as (url: string, body: unknown) => Promise<unknown>,
    );
}
