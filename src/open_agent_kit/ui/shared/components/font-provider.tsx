import { createContext, useContext, useEffect, useState, useCallback } from "react"

// ---------------------------------------------------------------------------
// Font definitions
// ---------------------------------------------------------------------------

export const FONT_OPTIONS = [
    {
        id: "system",
        label: "System",
        family: "ui-sans-serif, system-ui, -apple-system, sans-serif",
        stylesheet: null,
    },
    {
        id: "jetbrains-mono",
        label: "JetBrains Mono",
        family: "'JetBrains Mono', monospace",
        stylesheet: "https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&display=swap",
    },
    {
        id: "geist-mono",
        label: "Geist Mono",
        family: "'Geist Mono', monospace",
        stylesheet: "https://cdn.jsdelivr.net/npm/geist@1/dist/fonts/geist-mono/style.css",
    },
    {
        id: "ibm-plex-mono",
        label: "IBM Plex Mono",
        family: "'IBM Plex Mono', monospace",
        stylesheet: "https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500;600;700&display=swap",
    },
    {
        id: "fira-code",
        label: "Fira Code",
        family: "'Fira Code', monospace",
        stylesheet: "https://fonts.googleapis.com/css2?family=Fira+Code:wght@300;400;500;600;700&display=swap",
    },
    {
        id: "monaspace-neon",
        label: "Monaspace Neon",
        family: "'Monaspace Neon', monospace",
        stylesheet: "https://cdn.jsdelivr.net/npm/@aspect-build/monaspace@1/fonts/Monaspace-Neon.css",
    },
] as const

export type FontId = typeof FONT_OPTIONS[number]["id"]

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

interface FontProviderState {
    font: FontId
    setFont: (font: FontId) => void
}

const initialState: FontProviderState = {
    font: "system",
    setFont: () => null,
}

const FontProviderContext = createContext<FontProviderState>(initialState)

// ---------------------------------------------------------------------------
// Stylesheet loader
// ---------------------------------------------------------------------------

const LINK_ID_PREFIX = "oak-font-"

function loadStylesheet(fontId: string, url: string | null) {
    // Remove any previously loaded font stylesheet
    for (const opt of FONT_OPTIONS) {
        const existing = document.getElementById(`${LINK_ID_PREFIX}${opt.id}`)
        if (existing && opt.id !== fontId) {
            existing.remove()
        }
    }

    if (!url) return

    // Don't double-load
    if (document.getElementById(`${LINK_ID_PREFIX}${fontId}`)) return

    const link = document.createElement("link")
    link.id = `${LINK_ID_PREFIX}${fontId}`
    link.rel = "stylesheet"
    link.href = url
    link.crossOrigin = "anonymous"
    document.head.appendChild(link)
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

interface FontProviderProps {
    children: React.ReactNode
    defaultFont?: FontId
    storageKey?: string
}

export function FontProvider({
    children,
    defaultFont = "system",
    storageKey = "oak-ui-font",
}: FontProviderProps) {
    const [font, setFontState] = useState<FontId>(
        () => (localStorage.getItem(storageKey) as FontId) || defaultFont
    )

    // Apply the font to the document root whenever it changes
    useEffect(() => {
        const option = FONT_OPTIONS.find((o) => o.id === font)
        if (!option) return

        // Load the stylesheet (if needed)
        loadStylesheet(option.id, option.stylesheet)

        // Set the CSS custom property
        document.documentElement.style.setProperty("--font-ui", option.family)
    }, [font])

    const setFont = useCallback(
        (newFont: FontId) => {
            localStorage.setItem(storageKey, newFont)
            setFontState(newFont)
        },
        [storageKey]
    )

    return (
        <FontProviderContext.Provider value={{ font, setFont }}>
            {children}
        </FontProviderContext.Provider>
    )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useFont() {
    const context = useContext(FontProviderContext)
    if (context === undefined) {
        throw new Error("useFont must be used within a FontProvider")
    }
    return context
}
