import { useState, useRef, useEffect } from "react"
import { useFont, FONT_OPTIONS, type FontId } from "../font-provider"

interface FontSelectorProps {
    collapsed?: boolean
}

export function FontSelector({ collapsed = false }: FontSelectorProps) {
    const { font, setFont } = useFont()
    const [open, setOpen] = useState(false)
    const ref = useRef<HTMLDivElement>(null)

    // Close on outside click
    useEffect(() => {
        if (!open) return
        function handleClick(e: MouseEvent) {
            if (ref.current && !ref.current.contains(e.target as Node)) {
                setOpen(false)
            }
        }
        document.addEventListener("mousedown", handleClick)
        return () => document.removeEventListener("mousedown", handleClick)
    }, [open])

    // Close on Escape
    useEffect(() => {
        if (!open) return
        function handleKey(e: KeyboardEvent) {
            if (e.key === "Escape") setOpen(false)
        }
        document.addEventListener("keydown", handleKey)
        return () => document.removeEventListener("keydown", handleKey)
    }, [open])

    const currentLabel = FONT_OPTIONS.find((o) => o.id === font)?.label ?? "System"

    return (
        <div ref={ref} className="relative">
            <button
                onClick={() => setOpen(!open)}
                title="Change font"
                aria-label="Change font"
                aria-expanded={open}
                className={`flex items-center gap-2 w-full px-3 py-2 rounded-md transition-colors text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground ${
                    collapsed ? "justify-center px-2" : ""
                }`}
            >
                <svg
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={2}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className="w-4 h-4 flex-shrink-0"
                >
                    <path d="M4 7V4h16v3" />
                    <path d="M9 20h6" />
                    <path d="M12 4v16" />
                </svg>
                {!collapsed && (
                    <span className="truncate">{currentLabel}</span>
                )}
            </button>

            {open && (
                <div
                    className={`absolute z-50 border rounded-lg bg-popover text-popover-foreground shadow-lg py-1 min-w-[180px] ${
                        collapsed ? "left-full ml-2 bottom-0" : "bottom-full mb-1 left-0"
                    }`}
                >
                    <div className="px-3 py-1.5 text-xs font-medium text-muted-foreground">
                        Font
                    </div>
                    {FONT_OPTIONS.map((option) => (
                        <button
                            key={option.id}
                            onClick={() => {
                                setFont(option.id as FontId)
                                setOpen(false)
                            }}
                            className={`flex items-center gap-2 w-full px-3 py-1.5 text-sm transition-colors hover:bg-accent hover:text-accent-foreground ${
                                font === option.id
                                    ? "bg-accent text-accent-foreground font-medium"
                                    : ""
                            }`}
                        >
                            <span
                                className="w-4 text-center text-xs"
                                aria-hidden="true"
                            >
                                {font === option.id ? "\u2713" : ""}
                            </span>
                            <span>{option.label}</span>
                        </button>
                    ))}
                </div>
            )}
        </div>
    )
}
