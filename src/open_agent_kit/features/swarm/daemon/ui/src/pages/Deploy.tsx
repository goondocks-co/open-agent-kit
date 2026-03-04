import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@oak/ui/components/ui/card";
import { Button } from "@oak/ui/components/ui/button";
import { Alert, AlertDescription } from "@oak/ui/components/ui/alert";
import { CheckCircle, XCircle, Loader2 } from "lucide-react";
import { useDeployStatus, useDeployAuth, useDeployScaffold, useDeployInstall, useDeployRun } from "@/hooks/use-deploy";
import { useQueryClient } from "@tanstack/react-query";

function StepStatus({ done, label }: { done: boolean; label: string }) {
    return (
        <div className="flex items-center gap-2 text-sm">
            {done ? (
                <CheckCircle className="h-4 w-4 text-green-500" />
            ) : (
                <XCircle className="h-4 w-4 text-muted-foreground" />
            )}
            <span className={done ? "text-foreground" : "text-muted-foreground"}>{label}</span>
        </div>
    );
}

export default function Deploy() {
    const queryClient = useQueryClient();
    const { data: status } = useDeployStatus();
    const { data: auth, refetch: refetchAuth } = useDeployAuth();
    const scaffoldMutation = useDeployScaffold();
    const installMutation = useDeployInstall();
    const deployMutation = useDeployRun();

    const invalidate = () => {
        queryClient.invalidateQueries({ queryKey: ["deploy"] });
    };

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold">Deploy</h1>
                <p className="text-muted-foreground text-sm mt-1">
                    Deploy or manage the Swarm Worker on Cloudflare
                </p>
            </div>

            {/* Status overview */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base">Deployment Status</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                    <StepStatus done={auth?.wrangler_available ?? false} label="Wrangler available" />
                    <StepStatus done={auth?.authenticated ?? false} label={`Cloudflare authenticated${auth?.account_name ? ` (${auth.account_name})` : ''}`} />
                    <StepStatus done={status?.scaffolded ?? false} label="Worker scaffolded" />
                    <StepStatus done={status?.node_modules_installed ?? false} label="Dependencies installed" />
                    <StepStatus done={!!status?.worker_url} label={status?.worker_url ? `Deployed: ${status.worker_url}` : "Worker deployed"} />
                </CardContent>
            </Card>

            {/* Actions */}
            <div className="grid gap-4 md:grid-cols-2">
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base">1. Check Auth</CardTitle>
                        <CardDescription>Verify Cloudflare credentials</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <Button
                            variant="outline"
                            onClick={() => refetchAuth()}
                            className="w-full"
                        >
                            Check Authentication
                        </Button>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader>
                        <CardTitle className="text-base">2. Scaffold</CardTitle>
                        <CardDescription>Generate worker template</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-2">
                        <Button
                            variant="outline"
                            className="w-full"
                            onClick={() => scaffoldMutation.mutate({ force: false }, { onSuccess: invalidate })}
                            disabled={scaffoldMutation.isPending}
                        >
                            {scaffoldMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                            Scaffold Worker
                        </Button>
                        {scaffoldMutation.data?.error && (
                            <Alert variant="destructive"><AlertDescription>{scaffoldMutation.data.error}</AlertDescription></Alert>
                        )}
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader>
                        <CardTitle className="text-base">3. Install</CardTitle>
                        <CardDescription>Run npm install</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-2">
                        <Button
                            variant="outline"
                            className="w-full"
                            onClick={() => installMutation.mutate(undefined, { onSuccess: invalidate })}
                            disabled={installMutation.isPending || !status?.scaffolded}
                        >
                            {installMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                            Install Dependencies
                        </Button>
                        {installMutation.data && !installMutation.data.success && (
                            <Alert variant="destructive"><AlertDescription>{installMutation.data.output}</AlertDescription></Alert>
                        )}
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader>
                        <CardTitle className="text-base">4. Deploy</CardTitle>
                        <CardDescription>Deploy to Cloudflare Workers</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-2">
                        <Button
                            className="w-full"
                            onClick={() => deployMutation.mutate(undefined, { onSuccess: invalidate })}
                            disabled={deployMutation.isPending || !status?.node_modules_installed}
                        >
                            {deployMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                            Deploy Worker
                        </Button>
                        {deployMutation.data?.worker_url && (
                            <Alert><AlertDescription>Deployed to: {deployMutation.data.worker_url}</AlertDescription></Alert>
                        )}
                        {deployMutation.data && !deployMutation.data.success && (
                            <Alert variant="destructive"><AlertDescription>{deployMutation.data.output}</AlertDescription></Alert>
                        )}
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
