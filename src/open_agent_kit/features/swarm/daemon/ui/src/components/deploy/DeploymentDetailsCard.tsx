/**
 * Collapsible card showing prerequisite status for deployment.
 */

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@oak/ui/components/ui/card";
import { CheckCircle, XCircle, ChevronDown, ChevronRight } from "lucide-react";

export interface DeploymentDetailsCardProps {
    wranglerAvailable: boolean;
    authenticated: boolean;
    accountName: string | null;
    scaffolded: boolean;
    depsInstalled: boolean;
    defaultCollapsed?: boolean;
}

function StepStatus({ done, label }: { done: boolean; label: string }) {
    return (
        <div className="flex items-center gap-2 text-sm">
            {done ? (
                <CheckCircle className="h-4 w-4 text-green-500 shrink-0" />
            ) : (
                <XCircle className="h-4 w-4 text-muted-foreground shrink-0" />
            )}
            <span className={done ? "text-foreground" : "text-muted-foreground"}>{label}</span>
        </div>
    );
}

export function DeploymentDetailsCard({
    wranglerAvailable,
    authenticated,
    accountName,
    scaffolded,
    depsInstalled,
    defaultCollapsed = false,
}: DeploymentDetailsCardProps) {
    const [collapsed, setCollapsed] = useState(defaultCollapsed);
    const allGreen = wranglerAvailable && authenticated && scaffolded && depsInstalled;

    return (
        <Card>
            <CardHeader
                className="cursor-pointer select-none"
                onClick={() => setCollapsed(!collapsed)}
            >
                <CardTitle className="flex items-center gap-2 text-base">
                    {collapsed ? (
                        <ChevronRight className="h-4 w-4" />
                    ) : (
                        <ChevronDown className="h-4 w-4" />
                    )}
                    Deployment Details
                    {allGreen && (
                        <CheckCircle className="h-4 w-4 text-green-500 ml-auto" />
                    )}
                </CardTitle>
            </CardHeader>
            {!collapsed && (
                <CardContent className="space-y-2 pt-0">
                    <StepStatus done={wranglerAvailable} label="Wrangler available" />
                    <StepStatus
                        done={authenticated}
                        label={`Cloudflare authenticated${accountName ? ` (${accountName})` : ""}`}
                    />
                    <StepStatus done={scaffolded} label="Worker scaffolded" />
                    <StepStatus done={depsInstalled} label="Dependencies installed" />
                </CardContent>
            )}
        </Card>
    );
}
