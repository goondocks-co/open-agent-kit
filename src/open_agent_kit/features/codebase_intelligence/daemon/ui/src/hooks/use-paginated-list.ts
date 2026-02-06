import { useState, useCallback } from "react";

/**
 * Reusable hook for "load more" paginated lists.
 *
 * Manages offset, accumulated items, and provides helpers for
 * load-more, reset, and has-more checks.
 */
export function usePaginatedList<T>(pageSize: number) {
    const [offset, setOffset] = useState(0);
    const [loadedItems, setLoadedItems] = useState<T[]>([]);

    const handleLoadMore = useCallback((currentPageItems: T[]) => {
        setLoadedItems(prev => [...prev, ...currentPageItems]);
        setOffset(prev => prev + pageSize);
    }, [pageSize]);

    const reset = useCallback(() => {
        setLoadedItems([]);
        setOffset(0);
    }, []);

    const hasMore = useCallback((currentPageItems: T[]) => {
        return currentPageItems.length === pageSize;
    }, [pageSize]);

    return { offset, loadedItems, setLoadedItems, handleLoadMore, hasMore, reset };
}
