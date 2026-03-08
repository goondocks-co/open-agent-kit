import { useDensity, DENSITY_OPTIONS, type DensityId } from "../density-provider"

interface DensitySelectorProps {
    collapsed?: boolean
}

export function DensitySelector({ collapsed = false }: DensitySelectorProps) {
    const { density, setDensity } = useDensity()

    return (
        <div
            className={`flex items-center rounded-md bg-muted/50 ${
                collapsed ? "flex-col gap-1 px-1 py-2" : "justify-between px-2 py-1"
            }`}
        >
            {DENSITY_OPTIONS.map((option) => (
                <button
                    key={option.id}
                    onClick={() => setDensity(option.id as DensityId)}
                    title={`${option.label} density`}
                    aria-label={`${option.label} density`}
                    className={`p-1.5 rounded-sm transition-all text-xs font-medium ${
                        density === option.id ? "bg-background shadow-sm" : ""
                    }`}
                >
                    {collapsed ? option.label[0] : option.label}
                </button>
            ))}
        </div>
    )
}
