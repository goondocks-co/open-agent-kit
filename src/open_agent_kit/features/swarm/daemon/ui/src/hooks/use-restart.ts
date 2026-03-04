import { useMutation } from "@tanstack/react-query";
import { postJson } from "@/lib/api";
import { API_ENDPOINTS } from "@/lib/constants";

export function useRestart() {
    return useMutation<{ status: string }, Error, void>({
        mutationFn: () => postJson(API_ENDPOINTS.RESTART, {}),
    });
}
