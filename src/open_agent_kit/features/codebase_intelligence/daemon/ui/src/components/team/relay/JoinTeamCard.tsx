/**
 * Join a Team card — consumer input form for connecting via relay URL + token.
 */

import { useState } from "react";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Link2, Loader2, AlertCircle, CheckCircle2, Cloud } from "lucide-react";

export interface JoinTeamCardProps {
    onJoin: (url: string, token: string) => void;
    isSaving: boolean;
    isConnecting: boolean;
    joinError: string | null;
    joinSuccess: boolean;
}

export function JoinTeamCard({ onJoin, isSaving, isConnecting, joinError, joinSuccess }: JoinTeamCardProps) {
    const [url, setUrl] = useState("");
    const [token, setToken] = useState("");

    const isBusy = isSaving || isConnecting;

    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    <Link2 className="h-5 w-5" />
                    Join a Team
                </CardTitle>
                <CardDescription>
                    Enter the relay URL and token shared by your team member to start syncing.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                <div className="space-y-1.5">
                    <label className="text-sm font-medium">Relay URL</label>
                    <input
                        type="url"
                        value={url}
                        onChange={(e) => setUrl(e.target.value)}
                        placeholder="https://oak-relay-yourteam.workers.dev"
                        className="w-full rounded-md border bg-background px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring"
                        disabled={isBusy}
                    />
                </div>
                <div className="space-y-1.5">
                    <label className="text-sm font-medium">Relay Token</label>
                    <input
                        type="password"
                        value={token}
                        onChange={(e) => setToken(e.target.value)}
                        placeholder="Shared relay token"
                        className="w-full rounded-md border bg-background px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring"
                        disabled={isBusy}
                    />
                </div>

                {joinError && (
                    <Alert variant="destructive">
                        <AlertCircle className="h-4 w-4" />
                        <AlertDescription>{joinError}</AlertDescription>
                    </Alert>
                )}

                {joinSuccess && (
                    <div className="flex items-center gap-2 text-sm text-green-600">
                        <CheckCircle2 className="h-4 w-4" />
                        Connected to relay. Syncing observations automatically.
                    </div>
                )}
            </CardContent>
            <CardFooter>
                <Button
                    onClick={() => onJoin(url.trim(), token.trim())}
                    disabled={!url.trim() || !token.trim() || isBusy}
                    size="sm"
                >
                    {isBusy
                        ? <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        : <Cloud className="h-4 w-4 mr-2" />
                    }
                    {isSaving ? "Saving..." : isConnecting ? "Connecting..." : "Connect"}
                </Button>
            </CardFooter>
        </Card>
    );
}
