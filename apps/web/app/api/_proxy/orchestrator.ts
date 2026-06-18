import { NextRequest, NextResponse } from "next/server";

type ProxyMethod = "GET" | "POST" | "PATCH" | "DELETE";
export type PrincipalQueryKeys = {
  userKey: string;
  accountKey?: string;
};
type BodySchemaResult = { success: true; data?: unknown } | { success: false; error?: unknown };
export type BodySchema = {
  safeParse: (body: unknown) => BodySchemaResult;
};
type ProxyOptions = {
  injectVerifiedUserId?: boolean;
  injectVerifiedUserIdSnakeBody?: boolean;
  injectVerifiedUserIdHeader?: boolean;
  injectVerifiedUserIdQuery?: PrincipalQueryKeys;
  requireNonGuestUser?: boolean;
  bodySchema?: BodySchema;
  successStatus?: number;
};
type ProxyError = Error & {
  statusCode?: number;
  errorCode?: string;
};
type SupabasePrincipal = {
  userId: string;
  accountType: "guest" | "user";
};
type ProxyAuthDiagnostics = {
  header_present: boolean;
  principal_resolved: boolean;
  account_type: "guest" | "user" | null;
};

function perfEnabled() {
  return process.env.EASYADS_PERF_TRACE === "1";
}

function canonicalTraceId(value: string | null): string {
  return value && /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value)
    ? value
    : crypto.randomUUID();
}

function getOrchestratorBaseUrl(): string {
  return process.env.ORCHESTRATOR_BASE_URL || "http://localhost:8000";
}

function buildTargetUrl(path: string, request: NextRequest): URL {
  const target = new URL(path, getOrchestratorBaseUrl());
  request.nextUrl.searchParams.forEach((value, key) => {
    target.searchParams.append(key, value);
  });
  return target;
}

function sanitizedUpstream(targetUrl: URL | null) {
  return {
    host: targetUrl?.host ?? null,
    path: targetUrl?.pathname ?? null
  };
}

function errorCodeFromPayload(payload: unknown): string | null {
  if (!payload || typeof payload !== "object") {
    return null;
  }
  const record = payload as Record<string, unknown>;
  if (typeof record.error_code === "string") {
    return record.error_code;
  }
  const detail = record.detail;
  if (detail && typeof detail === "object") {
    const detailRecord = detail as Record<string, unknown>;
    if (typeof detailRecord.error_code === "string") {
      return detailRecord.error_code;
    }
  }
  return null;
}

function buildInternalHeaders(contentType?: string): Record<string, string> {
  const headers: Record<string, string> = {};
  if (contentType) {
    headers["content-type"] = contentType;
  }
  const internalSecret = process.env.EASYADS_INTERNAL_API_SECRET;
  if (internalSecret) {
    headers["X-EasyAds-Internal-Secret"] = internalSecret;
  }
  return headers;
}

function proxyError(message: string, statusCode: number, errorCode: string): ProxyError {
  const error = new Error(message) as ProxyError;
  error.statusCode = statusCode;
  error.errorCode = errorCode;
  return error;
}

function normalizeBearerHeader(value: string | null): string | null {
  if (!value) {
    return null;
  }
  const normalized = value.trim();
  if (!normalized) {
    return null;
  }
  if (!normalized.toLowerCase().startsWith("bearer ")) {
    throw proxyError("Invalid authorization header.", 401, "invalid_authorization_header");
  }
  return normalized;
}

async function resolveSupabasePrincipal(request: NextRequest): Promise<SupabasePrincipal | null> {
  const authorization = normalizeBearerHeader(request.headers.get("authorization"));
  if (!authorization) {
    return null;
  }

  const supabaseUrl = process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseAnonKey = process.env.SUPABASE_ANON_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!supabaseUrl || !supabaseAnonKey) {
    throw proxyError("Supabase auth configuration is missing.", 503, "supabase_auth_configuration_missing");
  }

  const response = await fetch(`${supabaseUrl.replace(/\/+$/, "")}/auth/v1/user`, {
    method: "GET",
    headers: {
      accept: "application/json",
      apikey: supabaseAnonKey,
      authorization
    }
  });
  if (!response.ok) {
    throw proxyError("Invalid or expired session.", 401, "invalid_or_expired_session");
  }

  const payload = await response.json().catch(() => ({}));
  if (!payload?.id) {
    throw proxyError("Invalid or expired session.", 401, "invalid_or_expired_session");
  }
  return {
    userId: String(payload.id),
    accountType: payload.is_anonymous ? "guest" : "user"
  };
}

function unavailableResponse(input?: { requestId?: string; targetUrl?: URL | null }) {
  return NextResponse.json(
    {
      success: false,
      error_code: "upstream_orchestrator_unavailable",
      message: "Orchestrator API is unavailable.",
      detail: "Failed to reach the orchestrator backend from the BFF proxy.",
      request_id: input?.requestId ?? null
    },
    { status: 502 }
  );
}

function logUpstreamUnavailable(input?: {
  requestId?: string;
  targetUrl?: URL | null;
  auth?: ProxyAuthDiagnostics;
}) {
  console.error("Next BFF upstream request failed", {
    request_id: input?.requestId ?? null,
    error_code: "upstream_orchestrator_unavailable",
    upstream: sanitizedUpstream(input?.targetUrl ?? null),
    auth: input?.auth ?? null
  });
}

function logUpstreamResponseFailure(input: {
  requestId: string;
  path: string;
  status: number;
  payload: unknown;
  auth: ProxyAuthDiagnostics;
}) {
  console.warn("Next BFF upstream response failed", {
    request_id: input.requestId,
    path: input.path,
    status: input.status,
    error_code: errorCodeFromPayload(input.payload),
    auth: input.auth
  });
}

function invalidRequestResponse(detail: unknown) {
  return NextResponse.json(
    {
      success: false,
      error: "invalid_request",
      error_code: "invalid_request",
      message: "Invalid request body.",
      detail
    },
    { status: 400 }
  );
}

function injectPrincipalBodyFields(
  payload: Record<string, unknown>,
  principal: SupabasePrincipal | null,
  useSnakeCase: boolean
) {
  delete payload.user_id;
  delete payload.userId;
  delete payload.account_type;
  delete payload.accountType;
  if (!principal) {
    return;
  }
  if (useSnakeCase) {
    payload.user_id = principal.userId;
    payload.account_type = principal.accountType;
    return;
  }
  payload.userId = principal.userId;
  payload.accountType = principal.accountType;
}

function applyPrincipalQueryParams(targetUrl: URL, keys: PrincipalQueryKeys, principal: SupabasePrincipal | null) {
  targetUrl.searchParams.delete(keys.userKey);
  if (keys.accountKey) {
    targetUrl.searchParams.delete(keys.accountKey);
  }
  if (!principal) {
    return;
  }
  targetUrl.searchParams.set(keys.userKey, principal.userId);
  if (keys.accountKey) {
    targetUrl.searchParams.set(keys.accountKey, principal.accountType);
  }
}

export async function proxyOrchestratorJson(
  request: NextRequest,
  method: ProxyMethod,
  path: string,
  bodyTransform?: (body: unknown) => unknown,
  options: ProxyOptions = {}
) {
  const headers = buildInternalHeaders("application/json");
  const started = Date.now();
  const traceId = canonicalTraceId(request.headers.get("X-EasyAds-Trace-Id"));
  const requestId = request.headers.get("X-Request-Id") || `req_${crypto.randomUUID().replace(/-/g, "")}`;
  const authDiagnostics: ProxyAuthDiagnostics = {
    header_present: Boolean(request.headers.get("authorization")?.trim()),
    principal_resolved: false,
    account_type: null
  };
  let targetUrl: URL | null = null;
  let authCallRequestedCount = 0;
  let authNetworkRequestCount = 0;
  let authDedupHitCount = 0;
  let authDurationMs = 0;
  const init: RequestInit = {
    method,
    headers,
    cache: "no-store"
  };

  try {
    let verifiedPrincipalPromise: Promise<SupabasePrincipal | null> | null = null;
    const getVerifiedPrincipal = () => {
      authCallRequestedCount += 1;
      if (verifiedPrincipalPromise) {
        authDedupHitCount += 1;
        return verifiedPrincipalPromise;
      }
      const authStarted = Date.now();
      authNetworkRequestCount += 1;
      verifiedPrincipalPromise = resolveSupabasePrincipal(request)
        .then((principal) => {
          authDiagnostics.principal_resolved = Boolean(principal);
          authDiagnostics.account_type = principal?.accountType ?? null;
          return principal;
        })
        .finally(() => {
          authDurationMs += Date.now() - authStarted;
        });
      return verifiedPrincipalPromise;
    };

    if (options.requireNonGuestUser) {
      const principal = await getVerifiedPrincipal();
      if (!principal || principal.accountType === "guest") {
        throw proxyError("Admin session required.", 401, "admin_session_required");
      }
    }

    if (options.injectVerifiedUserIdHeader) {
      const principal = await getVerifiedPrincipal();
      if (principal) {
        headers["X-EasyAds-User-Id"] = principal.userId;
        headers["X-EasyAds-Account-Type"] = principal.accountType;
      }
    }
    if (method !== "GET") {
      const body = await request.text();
      if (body || options.bodySchema) {
        let parsedBody: unknown = undefined;
        if (body) {
          try {
            parsedBody = JSON.parse(body);
          } catch (error) {
            return invalidRequestResponse({
              reason: "malformed_json",
              message: error instanceof Error ? error.message : "Request body must be valid JSON."
            });
          }
        }
        const rawPayload = bodyTransform && body ? bodyTransform(parsedBody) : parsedBody;
        const schemaResult = options.bodySchema?.safeParse(rawPayload);
        if (schemaResult && !schemaResult.success) {
          return invalidRequestResponse(schemaResult.error);
        }
        const validatedPayload =
          schemaResult?.success && Object.prototype.hasOwnProperty.call(schemaResult, "data")
            ? schemaResult.data
            : rawPayload;
        const payload =
          validatedPayload && typeof validatedPayload === "object" && !Array.isArray(validatedPayload)
            ? { ...(validatedPayload as Record<string, unknown>) }
            : validatedPayload;
        if (
          (options.injectVerifiedUserId || options.injectVerifiedUserIdSnakeBody) &&
          payload &&
          typeof payload === "object" &&
          !Array.isArray(payload)
        ) {
          const principal = await getVerifiedPrincipal();
          injectPrincipalBodyFields(
            payload as Record<string, unknown>,
            principal,
            Boolean(options.injectVerifiedUserIdSnakeBody)
          );
        }
        init.body = JSON.stringify(payload);
      }
    }

    targetUrl = buildTargetUrl(path, request);
    headers["X-EasyAds-Trace-Id"] = traceId;
    headers["X-Request-Id"] = requestId;
    if (options.injectVerifiedUserIdQuery) {
      const principal = await getVerifiedPrincipal();
      applyPrincipalQueryParams(targetUrl, options.injectVerifiedUserIdQuery, principal);
    }

    const upstreamStarted = Date.now();
    const response = await fetch(targetUrl.toString(), init);
    const upstreamDuration = Date.now() - upstreamStarted;
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      logUpstreamResponseFailure({
        requestId,
        path,
        status: response.status,
        payload,
        auth: authDiagnostics
      });
    }
    const nextResponse = NextResponse.json(payload, { status: response.ok && options.successStatus ? options.successStatus : response.status });
    nextResponse.headers.set("X-EasyAds-Trace-Id", traceId);
    nextResponse.headers.set("X-Request-Id", requestId);
    if (perfEnabled()) {
      const totalDuration = Date.now() - started;
      console.info(JSON.stringify({ event_type: "latency_span", trace_id: traceId, request_id: requestId, layer: "bff", operation: "bff_request_total", phase: "response", wall_time_utc: new Date().toISOString(), duration_ms: totalDuration, status: response.ok ? "ok" : "error", measurement_source: "actual", http_status: response.status }));
      console.info(JSON.stringify({ event_type: "latency_span", trace_id: traceId, request_id: requestId, layer: "bff", operation: "bff_auth", phase: "auth", wall_time_utc: new Date().toISOString(), duration_ms: authDurationMs, status: "ok", measurement_source: "actual" }));
      console.info(JSON.stringify({ event_type: "latency_span", trace_id: traceId, request_id: requestId, layer: "bff", operation: "bff_orchestrator_upstream", phase: "upstream", wall_time_utc: new Date().toISOString(), duration_ms: upstreamDuration, status: response.ok ? "ok" : "error", measurement_source: "actual", http_status: response.status }));
      nextResponse.headers.set(
        "Server-Timing",
        `auth;dur=${authDurationMs}, upstream;dur=${upstreamDuration}, total;dur=${totalDuration}`
      );
      nextResponse.headers.set("X-EasyAds-Bff-Perf", String(totalDuration));
      nextResponse.headers.set("X-EasyAds-Bff-Auth-Calls", String(authCallRequestedCount));
      nextResponse.headers.set("X-EasyAds-Bff-Auth-Network", String(authNetworkRequestCount));
      nextResponse.headers.set("X-EasyAds-Bff-Auth-Dedup-Hits", String(authDedupHitCount));
    }
    return nextResponse;
  } catch (error) {
    const statusCode = (error as ProxyError).statusCode;
    const errorCode = (error as ProxyError).errorCode;
    if (statusCode) {
      const errorResponse = NextResponse.json(
        {
          success: false,
          error_code: errorCode || "orchestrator_proxy_error",
          message: error instanceof Error ? error.message : "Proxy request failed."
        },
        { status: statusCode }
      );
      errorResponse.headers.set("X-EasyAds-Trace-Id", traceId);
      return errorResponse;
    }
    logUpstreamUnavailable({ requestId, targetUrl, auth: authDiagnostics });
    const errorResponse = unavailableResponse({ requestId, targetUrl });
    errorResponse.headers.set("X-EasyAds-Trace-Id", traceId);
    return errorResponse;
  }
}

export async function proxyOrchestratorBinary(request: NextRequest, path: string, cacheControl?: string) {
  const headers = buildInternalHeaders();
  const traceId = canonicalTraceId(request.headers.get("X-EasyAds-Trace-Id"));
  const requestId = request.headers.get("X-Request-Id") || `req_${crypto.randomUUID().replace(/-/g, "")}`;
  headers["X-EasyAds-Trace-Id"] = traceId;
  headers["X-Request-Id"] = requestId;
  const targetUrl = buildTargetUrl(path, request);
  const started = Date.now();

  try {
    const response = await fetch(targetUrl.toString(), {
      method: "GET",
      headers,
      cache: "no-store"
    });

    if (!response.ok) {
      const contentType = response.headers.get("content-type");
      const detail = contentType?.includes("application/json")
        ? await response.json().catch(() => ({ content_type: contentType }))
        : { content_type: contentType || null };
      return NextResponse.json(
        {
          success: false,
          error_code: "orchestrator_binary_proxy_error",
          message: "Orchestrator binary request failed.",
          detail
        },
        { status: response.status }
      );
    }

    const responseHeaders = new Headers();
    const contentType = response.headers.get("content-type");
    const responseCacheControl = cacheControl || response.headers.get("cache-control");
    if (contentType) {
      responseHeaders.set("content-type", contentType);
    }
    if (responseCacheControl) {
      responseHeaders.set("cache-control", responseCacheControl);
    }

    const nextResponse = new Response(await response.arrayBuffer(), {
      status: response.status,
      headers: responseHeaders
    });
    nextResponse.headers.set("X-EasyAds-Trace-Id", traceId);
    nextResponse.headers.set("X-Request-Id", requestId);
    if (perfEnabled()) {
      nextResponse.headers.set("Server-Timing", `upstream;dur=${Date.now() - started}`);
    }
    return nextResponse;
  } catch {
    logUpstreamUnavailable({ targetUrl });
    return unavailableResponse({ targetUrl });
  }
}
