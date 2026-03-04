import { createApiClient } from "@oak/ui/lib/api";

export const { fetchJson, postJson, patchJson, deleteJson } = createApiClient(
    "http://localhost:38900"
);
