/**
 * Custom domain configuration card for the Swarm Worker.
 * Mirrors the team relay DeploymentCard custom domain section.
 */

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@oak/ui/components/ui/card";
import { Button } from "@oak/ui/components/ui/button";
import { Globe, Loader2, CheckCircle2, AlertCircle } from "lucide-react";
import { useDeploySettings } from "@/hooks/use-deploy";

export interface CustomDomainCardProps {
    currentDomain: string | null;
    workerName: string | null;
    isDeployed: boolean;
}

export function CustomDomainCard({ currentDomain, workerName, isDeployed }: CustomDomainCardProps) {
    const updateSettings = useDeploySettings();

    const [domain, setDomain] = useState(currentDomain ?? "");
    const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

    useEffect(() => { setDomain(currentDomain ?? ""); }, [currentDomain]);

    const hasChanged = domain !== (currentDomain ?? "");
    const trimmedDomain = domain.trim();
    const derivedSubdomain = trimmedDomain && workerName ? `${workerName}.${trimmedDomain}` : null;

    const handleSave = () => {
        setMessage(null);
        updateSettings.mutate(
            { custom_domain: trimmedDomain || null },
            {
                onSuccess: () => setMessage({ type: "success", text: "Custom domain saved." }),
                onError: (err) => setMessage({ type: "error", text: err.message }),
            },
        );
    };

    return (
        <Card>
            <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                    <Globe className="h-4 w-4" />
                    Custom Domain
                </CardTitle>
                <CardDescription>
                    Route the Swarm Worker through your own domain via Cloudflare Custom Domains.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
                <div className="flex items-center gap-2">
                    <input
                        type="text"
                        value={domain}
                        onChange={(e) => setDomain(e.target.value)}
                        placeholder="example.com"
                        className="flex-1 rounded-md border bg-background px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring"
                        disabled={updateSettings.isPending}
                    />
                    <Button onClick={handleSave} disabled={!hasChanged || updateSettings.isPending} size="sm">
                        {updateSettings.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Save"}
                    </Button>
                </div>
                {derivedSubdomain && (
                    <p className="text-xs text-muted-foreground">
                        Worker endpoint: <code className="bg-muted px-1 rounded">{derivedSubdomain}</code>
                    </p>
                )}
                {isDeployed && hasChanged && (
                    <p className="text-xs text-muted-foreground">
                        Re-deploy after saving to apply the custom domain route on Cloudflare.
                    </p>
                )}
                {message && (
                    <div className={`flex items-center gap-2 text-sm ${message.type === "success" ? "text-green-600" : "text-red-600"}`}>
                        {message.type === "success"
                            ? <CheckCircle2 className="h-4 w-4" />
                            : <AlertCircle className="h-4 w-4" />}
                        {message.text}
                    </div>
                )}
                {currentDomain && (
                    <button
                        onClick={() => {
                            setDomain("");
                            updateSettings.mutate({ custom_domain: null });
                        }}
                        disabled={updateSettings.isPending}
                        className="text-xs text-muted-foreground underline hover:text-foreground"
                    >
                        Clear custom domain
                    </button>
                )}
            </CardContent>
        </Card>
    );
}
