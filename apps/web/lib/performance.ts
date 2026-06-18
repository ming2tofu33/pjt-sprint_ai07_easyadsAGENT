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
    __easyadsPerfContext?: Partial<PerfEvent>;
    __EASYADS_PERF_TRACE__?: {
      snapshot: () => PerfEvent[];
      exportJson: () => string;
      clear: () => void;
    };
  }
}

const MAX_EVENTS = 5000;

export function perfTraceEnabled() {
  if (process.env.NEXT_PUBLIC_EASYADS_PERF_TRACE === "1") return true;
  if (typeof window === "undefined") return false;
  return new URLSearchParams(window.location.search).get("perfTrace") === "1" || window.localStorage.getItem("easyads.perfTrace") === "1";
}

export function getOrCreateTraceId() {
  if (typeof window === "undefined") return null;
  const current = window.__easyadsPerfContext?.trace_id;
  if (typeof current === "string" && /^[0-9a-f-]{36}$/i.test(current)) return current;
  const traceId = crypto.randomUUID();
  setWebPerfContext({ ...window.__easyadsPerfContext, trace_id: traceId });
  installPerfTraceExport();
  return traceId;
}

export function traceHeaders(): Record<string, string> {
  const traceId = getOrCreateTraceId();
  return traceId ? { "X-EasyAds-Trace-Id": traceId } : {};
}

function installPerfTraceExport() {
  if (typeof window === "undefined" || !perfTraceEnabled() || window.__EASYADS_PERF_TRACE__) return;
  window.__EASYADS_PERF_TRACE__ = {
    snapshot: exportWebPerfEvents,
    exportJson: () => JSON.stringify(exportWebPerfEvents(), null, 2),
    clear: resetWebPerfEvents
  };
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
  const context = window.__easyadsPerfContext ?? {};
  window.__easyadsPerfEvents.push({
    ...context,
    ...event,
    metadata: {
      ...(context.metadata ?? {}),
      ...event.metadata
    }
  } as PerfEvent);
  if (window.__easyadsPerfEvents.length > MAX_EVENTS) {
    window.__easyadsPerfEvents.splice(0, window.__easyadsPerfEvents.length - MAX_EVENTS);
  }
  installPerfTraceExport();
}

export function resetWebPerfEvents() {
  if (typeof window === "undefined") {
    return;
  }
  window.__easyadsPerfEvents = [];
}

export function exportWebPerfEvents(): PerfEvent[] {
  if (typeof window === "undefined") {
    return [];
  }
  return [...(window.__easyadsPerfEvents ?? [])];
}

export function setWebPerfContext(context: Partial<PerfEvent>) {
  if (typeof window === "undefined") {
    return;
  }
  window.__easyadsPerfContext = context;
}

export async function measureWebPerf<T>(
  eventType: string,
  operation: string,
  fn: (span: { addMetadata: (metadata: Record<string, unknown>) => void }) => Promise<T>,
  metadata: Record<string, unknown> = {},
  component: "web" | "bff" = "web"
): Promise<T> {
  const startedAt = nowIso();
  const started = performance.now();
  const spanMetadata = { ...metadata };
  const span = {
    addMetadata(nextMetadata: Record<string, unknown>) {
      Object.assign(spanMetadata, nextMetadata);
    }
  };
  try {
    const result = await fn(span);
    recordWebPerfEvent({
      schema_version: 1,
      event_type: eventType,
      component,
      operation,
      started_at: startedAt,
      duration_ms: Math.max(0, performance.now() - started),
      status: "ok",
      metadata: spanMetadata
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
        ...spanMetadata,
        exception_type: error instanceof Error ? error.name : "Error"
      }
    });
    throw error;
  }
}
