type PerfEvent = {
  schema_version: 1;
  event_type: string;
  trace_id?: string | null;
  request_id?: string | null;
  scenario_id?: string | null;
  run_id?: string | null;
  cold_or_warm?: string | null;
  component: "web" | "bff";
  operation: string;
  started_at: string;
  duration_ms: number;
  status: string;
  metadata: Record<string, unknown>;
};

declare global {
  interface Window {
    __easyadsPerfEvents?: PerfEvent[];
  }
}

export function perfTraceEnabled() {
  return process.env.NEXT_PUBLIC_EASYADS_PERF_TRACE === "1";
}

export function nowIso() {
  return new Date().toISOString();
}

export function estimateJsonSizeBytes(value: unknown): number | null {
  try {
    return new TextEncoder().encode(JSON.stringify(value)).length;
  } catch {
    return null;
  }
}

export function recordWebPerfEvent(event: PerfEvent) {
  if (!perfTraceEnabled() || typeof window === "undefined") {
    return;
  }
  window.__easyadsPerfEvents ??= [];
  window.__easyadsPerfEvents.push(event);
}

export async function measureWebPerf<T>(
  eventType: string,
  operation: string,
  fn: () => Promise<T>,
  metadata: Record<string, unknown> = {},
  component: "web" | "bff" = "web"
): Promise<T> {
  const startedAt = nowIso();
  const started = performance.now();
  try {
    const result = await fn();
    recordWebPerfEvent({
      schema_version: 1,
      event_type: eventType,
      component,
      operation,
      started_at: startedAt,
      duration_ms: Math.max(0, performance.now() - started),
      status: "ok",
      metadata
    });
    return result;
  } catch (error) {
    recordWebPerfEvent({
      schema_version: 1,
      event_type: eventType,
      component,
      operation,
      started_at: startedAt,
      duration_ms: Math.max(0, performance.now() - started),
      status: "error",
      metadata: {
        ...metadata,
        exception_type: error instanceof Error ? error.name : "Error"
      }
    });
    throw error;
  }
}
