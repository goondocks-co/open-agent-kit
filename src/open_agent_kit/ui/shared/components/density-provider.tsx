import { createContext, useContext, useEffect, useState, useCallback } from "react"

// ---------------------------------------------------------------------------
// Density definitions
// ---------------------------------------------------------------------------

export const DENSITY_OPTIONS = [
    { id: "compact", label: "Compact", scale: 0.85 },
    { id: "normal", label: "Normal", scale: 1.0 },
    { id: "comfy", label: "Comfy", scale: 1.2 },
] as const

export type DensityId = typeof DENSITY_OPTIONS[number]["id"]

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

interface DensityProviderState {
    density: DensityId
    setDensity: (density: DensityId) => void
}

const initialState: DensityProviderState = {
    density: "normal",
    setDensity: () => null,
}

const DensityProviderContext = createContext<DensityProviderState>(initialState)

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

interface DensityProviderProps {
    children: React.ReactNode
    defaultDensity?: DensityId
    storageKey?: string
}

export function DensityProvider({
    children,
    defaultDensity = "normal",
    storageKey = "oak-ui-density",
}: DensityProviderProps) {
    const [density, setDensityState] = useState<DensityId>(
        () => (localStorage.getItem(storageKey) as DensityId) || defaultDensity
    )

    useEffect(() => {
        const option = DENSITY_OPTIONS.find((o) => o.id === density)
        if (!option) return
        document.documentElement.style.setProperty("--density", String(option.scale))
    }, [density])

    const setDensity = useCallback(
        (newDensity: DensityId) => {
            localStorage.setItem(storageKey, newDensity)
            setDensityState(newDensity)
        },
        [storageKey]
    )

    return (
        <DensityProviderContext.Provider value={{ density, setDensity }}>
            {children}
        </DensityProviderContext.Provider>
    )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useDensity() {
    const context = useContext(DensityProviderContext)
    if (context === undefined) {
        throw new Error("useDensity must be used within a DensityProvider")
    }
    return context
}
