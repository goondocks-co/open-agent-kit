import { useDeployStatus, useDeployAuth } from "@/hooks/use-deploy";
import { useDeployPipeline } from "@/hooks/use-deploy-pipeline";
import { useSwarmStatus } from "@/hooks/use-swarm-status";
import { SwarmConnectionCard } from "@/components/deploy/SwarmConnectionCard";
import { CustomDomainCard } from "@/components/deploy/CustomDomainCard";
import { DeploymentDetailsCard } from "@/components/deploy/DeploymentDetailsCard";

export default function Deploy() {
    const { data: status } = useDeployStatus();
    const { data: auth } = useDeployAuth();
    const { data: swarmStatus } = useSwarmStatus();
    const pipeline = useDeployPipeline();

    const isDeployed = !!status?.worker_url;
    const workerUrl = status?.worker_url ?? null;
    const swarmId = swarmStatus?.swarm_id ?? status?.swarm_id ?? null;

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold">Deploy</h1>
                <p className="text-muted-foreground text-sm mt-1">
                    Deploy or manage the Swarm Worker on Cloudflare
                </p>
            </div>

            {/* Main state machine card */}
            <SwarmConnectionCard
                isDeployed={isDeployed}
                isDeploying={pipeline.isPending}
                currentStep={pipeline.currentStep}
                workerUrl={workerUrl}
                swarmId={swarmId}
                error={pipeline.error}
                updateAvailable={status?.update_available ?? false}
                onDeploy={() => pipeline.mutate()}
                onRedeploy={() => pipeline.mutate({ force: true })}
            />

            {/* Custom domain */}
            <CustomDomainCard
                currentDomain={status?.custom_domain ?? null}
                workerName={status?.worker_name ?? null}
                isDeployed={isDeployed}
            />

            {/* Deployment details (collapsed when deployed) */}
            <DeploymentDetailsCard
                wranglerAvailable={auth?.wrangler_available ?? false}
                authenticated={auth?.authenticated ?? false}
                accountName={auth?.account_name ?? null}
                scaffolded={status?.scaffolded ?? false}
                depsInstalled={status?.node_modules_installed ?? false}
                defaultCollapsed={isDeployed}
            />
        </div>
    );
}
