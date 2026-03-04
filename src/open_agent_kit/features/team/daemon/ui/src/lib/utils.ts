import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"
import { SESSION_TITLE_MAX_LENGTH } from "./constants"

export function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs))
}

export function formatDate(dateString: string | null | undefined) {
    if (!dateString) return "-";
    return new Date(dateString).toLocaleString(undefined, {
        month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit'
    });
}

/**
 * Generate a display title for a session using the fallback chain:
 * title → first_prompt_preview (truncated) → partial ID.
 */
export function getSessionTitle(session: {
    title?: string | null;
    first_prompt_preview?: string | null;
    id: string;
}): string {
    if (session.title) return session.title;
    if (session.first_prompt_preview) {
        return session.first_prompt_preview.length > SESSION_TITLE_MAX_LENGTH
            ? session.first_prompt_preview.slice(0, SESSION_TITLE_MAX_LENGTH) + "..."
            : session.first_prompt_preview;
    }
    return `Session ${session.id.slice(0, 8)}...`;
}
