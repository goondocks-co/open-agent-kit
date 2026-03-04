import { useEffect, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@oak/ui/components/ui/card";
import { useLogs } from "@/hooks/use-logs";

export default function Logs() {
    const { data } = useLogs(200);
    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (containerRef.current) {
            containerRef.current.scrollTop = containerRef.current.scrollHeight;
        }
    }, [data?.lines]);

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold">Logs</h1>
                <p className="text-muted-foreground text-sm mt-1">
                    Daemon log output {data?.path && <span className="font-mono">({data.path})</span>}
                </p>
            </div>

            <Card>
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium">
                        {data?.total_lines !== undefined ? `${data.total_lines} total lines` : "Log output"}
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div
                        ref={containerRef}
                        className="font-mono text-xs bg-muted/50 rounded-md p-4 max-h-[600px] overflow-auto"
                    >
                        {data?.lines?.length ? (
                            data.lines.map((line, i) => (
                                <div key={i} className="whitespace-pre-wrap py-0.5 hover:bg-muted/80">
                                    {line}
                                </div>
                            ))
                        ) : (
                            <p className="text-muted-foreground">No log output</p>
                        )}
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
