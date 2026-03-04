/**
 * Deployment card — prerequisites, re-deploy, and custom domain management.
 */

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@oak/ui/components/ui/card";
import { Button } from "@oak/ui/components/ui/button";
import { CommandBlock } from "@oak/ui/components/ui/command-block";
import { Settings, Loader2, RefreshCw, Check, X, CheckCircle2, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { useCloudRelayPreflight, useCloudRelayUpdateSettings } from "@/hooks/use-cloud-relay";

interface PrerequisiteItemProps { label: string; satisfied: boolean }

function PrerequisiteItem({ label, satisfied }: PrerequisiteItemProps) {
    return (
        <div className="flex items-center gap-2 text-sm">
            {satisfied
                ? <Check className="h-4 w-4 text-green-500 flex-shrink-0" />
                : <X className="h-4 w-4 text-muted-foreground flex-shrink-0" />}
            <span className={cn(satisfied ? "text-foreground" : "text-muted-foreground")}>{label}</span>
        </div>
    );
}

export interface DeploymentCardProps {
    isDeployed: boolean;
    isStarting: boolean;
    isToggling: boolean;
    currentDomain: string | null;
    workerName: string | null;
    onRedeploy: () => void;
}

export function DeploymentCard({
    isDeployed, isStarting, isToggling,
    currentDomain, workerName, onRedeploy,
}: DeploymentCardProps) {
    const { data: preflight } = useCloudRelayPreflight();
    const updateSettings = useCloudRelayUpdateSettings();

    const [domain, setDomain] = useState(currentDomain ?? "");
    const [domainMessage, setDomainMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

    useEffect(() => { setDomain(currentDomain ?? ""); }, [currentDomain]);

    const hasChanged = domain !== (currentDomain ?? "");
    const trimmedDomain = domain.trim();
    const derivedSubdomain = trimmedDomain && workerName ? `${workerName}.${trimmedDomain}` : null;

    const handleSaveDomain = () => {
        setDomainMessage(null);
        updateSettings.mutate(
            { custom_domain: trimmedDomain || null },
            {
                onSuccess: () => setDomainMessage({ type: "success", text: "Custom domain saved." }),
                onError: (err) => setDomainMessage({ type: "error", text: err.message }),
            },
        );
    };

    return (
        <Card>
            <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                    <Settings className="h-4 w-4" />
                    Deployment
                </CardTitle>
                <CardDescription>
                    Manage the Cloudflare Worker deployment.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
                {/* Prerequisites */}
                {preflight && (
                    <div className="space-y-2">
                        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Prerequisites</p>
                        <div className="space-y-1.5">
                            <PrerequisiteItem label="Node.js / npm available" satisfied={preflight.npm_available} />
                            <PrerequisiteItem label="Wrangler CLI available" satisfied={preflight.wrangler_available} />
                            <PrerequisiteItem label="Wrangler authenticated" satisfied={preflight.wrangler_authenticated} />
                            {preflight.cf_account_name && (
                                <p className="text-xs text-muted-foreground pl-6">Account: {preflight.cf_account_name}</p>
                            )}
                        </div>
                        {!preflight.wrangler_available && (
                            <CommandBlock command="npm install -g wrangler && wrangler login" label="Install and authenticate" />
                        )}
                        {preflight.wrangler_available && !preflight.wrangler_authenticated && (
                            <CommandBlock command="wrangler login" label="Authenticate with Cloudflare" />
                        )}
                    </div>
                )}

                {/* Re-deploy */}
                {isDeployed && (
                    <div className="space-y-2 pt-1 border-t">
                        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Re-deploy</p>
                        <p className="text-xs text-muted-foreground">
                            Pushes the latest Worker code to Cloudflare. Required after config changes or OAK updates.
                        </p>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={onRedeploy}
                            disabled={isToggling}
                        >
                            {isStarting
                                ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Deploying...</>
                                : <><RefreshCw className="h-4 w-4 mr-2" />Re-deploy Worker</>
                            }
                        </Button>
                    </div>
                )}

                {/* Custom domain */}
                <div className="space-y-2 pt-1 border-t">
                    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Custom Domain</p>
                    <div className="flex items-center gap-2">
                        <input
                            type="text"
                            value={domain}
                            onChange={(e) => setDomain(e.target.value)}
                            placeholder="example.com"
                            className="flex-1 rounded-md border bg-background px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring"
                            disabled={updateSettings.isPending}
                        />
                        <Button onClick={handleSaveDomain} disabled={!hasChanged || updateSettings.isPending} size="sm">
                            {updateSettings.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Save"}
                        </Button>
                    </div>
                    {derivedSubdomain && (
                        <p className="text-xs text-muted-foreground">
                            MCP endpoint: <code className="bg-muted px-1 rounded">{derivedSubdomain}/mcp</code>
                        </p>
                    )}
                    {domainMessage && (
                        <div className={cn(
                            "flex items-center gap-2 text-sm",
                            domainMessage.type === "success" ? "text-green-600" : "text-red-600",
                        )}>
                            {domainMessage.type === "success"
                                ? <CheckCircle2 className="h-4 w-4" />
                                : <AlertCircle className="h-4 w-4" />}
                            {domainMessage.text}
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
                </div>
            </CardContent>
        </Card>
    );
}
