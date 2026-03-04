/**
 * Leave Team section — destructive action with confirmation dialog.
 */

import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@oak/ui/components/ui/card";
import { Button } from "@oak/ui/components/ui/button";
import { ConfirmDialog } from "@oak/ui/components/ui/confirm-dialog";
import { LogOut, Loader2 } from "lucide-react";

export function LeaveTeamSection({ onLeave, isLeaving }: { onLeave: () => void; isLeaving: boolean }) {
    const [confirmOpen, setConfirmOpen] = useState(false);
    return (
        <Card className="border-destructive/30">
            <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base text-destructive">
                    <LogOut className="h-4 w-4" />
                    Leave Team
                </CardTitle>
                <CardDescription>
                    Disconnect from the relay and clear your team credentials.
                    Your local data stays intact. You can rejoin by re-entering the relay URL and token.
                </CardDescription>
            </CardHeader>
            <CardContent>
                <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => setConfirmOpen(true)}
                    disabled={isLeaving}
                >
                    {isLeaving
                        ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Leaving...</>
                        : <><LogOut className="h-4 w-4 mr-2" />Leave Team</>
                    }
                </Button>
                <ConfirmDialog
                    open={confirmOpen}
                    onOpenChange={setConfirmOpen}
                    title="Leave the team?"
                    description="This will disconnect your daemon from the relay and clear your relay credentials. Your local data (sessions, memories, observations) is not deleted. You can rejoin anytime."
                    confirmLabel="Leave Team"
                    loadingLabel="Leaving..."
                    onConfirm={onLeave}
                    isLoading={isLeaving}
                />
            </CardContent>
        </Card>
    );
}
