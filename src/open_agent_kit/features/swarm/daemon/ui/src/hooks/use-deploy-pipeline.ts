/**
 * Chains scaffold -> install -> deploy into a single mutation.
 * Tracks currentStep (1/2/3) for progress display.
 */

import { useState, useCallback } from "react";
import { useDeployScaffold, useDeployInstall, useDeployRun } from "@/hooks/use-deploy";
import { useQueryClient } from "@tanstack/react-query";

interface DeployPipelineResult {
    mutate: (options?: { force?: boolean }) => void;
    isPending: boolean;
    currentStep: number;
    error: string | null;
}

export function useDeployPipeline(): DeployPipelineResult {
    const queryClient = useQueryClient();
    const scaffoldMutation = useDeployScaffold();
    const installMutation = useDeployInstall();
    const deployMutation = useDeployRun();

    const [currentStep, setCurrentStep] = useState(0);
    const [error, setError] = useState<string | null>(null);

    const invalidate = useCallback(() => {
        queryClient.invalidateQueries({ queryKey: ["deploy"] });
    }, [queryClient]);

    const mutate = useCallback((options?: { force?: boolean }) => {
        setError(null);
        setCurrentStep(1);

        // Step 1: Scaffold (force=true when re-deploying with template updates)
        scaffoldMutation.mutate(
            { force: options?.force ?? false },
            {
                onSuccess: (data) => {
                    if (data.error) {
                        setError(data.error);
                        setCurrentStep(0);
                        return;
                    }
                    invalidate();
                    setCurrentStep(2);

                    // Step 2: Install
                    installMutation.mutate(undefined, {
                        onSuccess: (installData) => {
                            if (!installData.success) {
                                setError(installData.output);
                                setCurrentStep(0);
                                return;
                            }
                            invalidate();
                            setCurrentStep(3);

                            // Step 3: Deploy
                            deployMutation.mutate(undefined, {
                                onSuccess: (deployData) => {
                                    if (!deployData.success) {
                                        setError(deployData.output);
                                    }
                                    invalidate();
                                    setCurrentStep(0);
                                },
                                onError: (err) => {
                                    setError(err.message);
                                    setCurrentStep(0);
                                },
                            });
                        },
                        onError: (err) => {
                            setError(err.message);
                            setCurrentStep(0);
                        },
                    });
                },
                onError: (err) => {
                    setError(err.message);
                    setCurrentStep(0);
                },
            }
        );
    }, [scaffoldMutation, installMutation, deployMutation, invalidate]);

    const isPending = currentStep > 0;

    return { mutate, isPending, currentStep, error };
}
