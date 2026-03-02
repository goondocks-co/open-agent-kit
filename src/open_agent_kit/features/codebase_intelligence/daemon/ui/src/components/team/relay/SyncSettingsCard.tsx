/**
 * Sync Settings card — auto-sync toggle and interval slider.
 */

import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { RefreshCw, Loader2, CheckCircle2, AlertCircle, Save } from "lucide-react";
import { cn } from "@/lib/utils";
import { SYNC_INTERVAL_MIN, SYNC_INTERVAL_MAX } from "@/lib/constants";

export interface SyncSettingsCardProps {
    autoSync: boolean;
    syncInterval: number;
    keepRelayAlive: boolean;
    isSaving: boolean;
    isDirty: boolean;
    message: { type: "success" | "error"; text: string } | null;
    onAutoSyncChange: (v: boolean) => void;
    onIntervalChange: (v: number) => void;
    onKeepRelayAliveChange: (v: boolean) => void;
    onSave: () => void;
}

export function SyncSettingsCard({
    autoSync, syncInterval, keepRelayAlive, isSaving, isDirty, message,
    onAutoSyncChange, onIntervalChange, onKeepRelayAliveChange, onSave,
}: SyncSettingsCardProps) {
    return (
        <Card>
            <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                    <RefreshCw className="h-4 w-4" />
                    Sync Settings
                </CardTitle>
                <CardDescription>
                    Control when this daemon syncs observations with the team.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                <div className="flex items-center gap-3">
                    <input
                        type="checkbox"
                        id="relay_auto_sync"
                        checked={autoSync}
                        onChange={(e) => onAutoSyncChange(e.target.checked)}
                        className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                    />
                    <label htmlFor="relay_auto_sync" className="text-sm font-medium">
                        Auto-sync observations
                    </label>
                </div>
                <div className="space-y-2">
                    <div className="flex items-center justify-between">
                        <label className="text-sm font-medium">Sync interval</label>
                        <span className="text-sm text-muted-foreground">{syncInterval}s</span>
                    </div>
                    <input
                        type="range"
                        min={SYNC_INTERVAL_MIN}
                        max={SYNC_INTERVAL_MAX}
                        value={syncInterval}
                        onChange={(e) => onIntervalChange(Number(e.target.value))}
                        className="w-full"
                        disabled={!autoSync}
                    />
                    <div className="flex justify-between text-xs text-muted-foreground">
                        <span>{SYNC_INTERVAL_MIN}s</span>
                        <span>{SYNC_INTERVAL_MAX}s</span>
                    </div>
                </div>
                <div className="flex items-start gap-3 pt-2 border-t">
                    <input
                        type="checkbox"
                        id="keep_relay_alive"
                        checked={keepRelayAlive}
                        onChange={(e) => onKeepRelayAliveChange(e.target.checked)}
                        className="h-4 w-4 mt-0.5 rounded border-gray-300 text-primary focus:ring-primary"
                    />
                    <div>
                        <label htmlFor="keep_relay_alive" className="text-sm font-medium">
                            Keep relay alive during idle
                        </label>
                        <p className="text-xs text-muted-foreground mt-0.5">
                            Prevents the relay and sync worker from suspending when the daemon is idle.
                            Enable this if teammates need to reach your daemon at all times.
                        </p>
                    </div>
                </div>
            </CardContent>
            <CardFooter className="bg-muted/30 py-3 border-t flex items-center justify-between">
                {message ? (
                    <div className={cn(
                        "flex items-center gap-2 text-sm",
                        message.type === "success" ? "text-green-600" : "text-red-600",
                    )}>
                        {message.type === "success"
                            ? <CheckCircle2 className="h-4 w-4" />
                            : <AlertCircle className="h-4 w-4" />}
                        {message.text}
                    </div>
                ) : (
                    <p className="text-xs text-muted-foreground">Changes take effect after save.</p>
                )}
                <Button onClick={onSave} disabled={!isDirty || isSaving} size="sm">
                    {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    <Save className="mr-2 h-4 w-4" /> Save
                </Button>
            </CardFooter>
        </Card>
    );
}
