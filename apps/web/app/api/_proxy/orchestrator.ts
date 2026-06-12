import { NextRequest, NextResponse } from "next/server";

type ProxyMethod = "GET" | "POST" | "PATCH" | "DELETE";
export type PrincipalQueryKeys = {
  userKey: string;
  accountKey: string;
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

function unavailableResponse() {
  return NextResponse.json(
    {
      success: false,
      error_code: "orchestrator_unavailable",
      message: "Orchestrator API is unavailable.",
      detail: "Failed to reach the orchestrator backend from the BFF proxy."
    },
    { status: 502 }
  );
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
  targetUrl.searchParams.delete(keys.accountKey);
  if (!principal) {
    return;
  }
  targetUrl.searchParams.set(keys.userKey, principal.userId);
  targetUrl.searchParams.set(keys.accountKey, principal.accountType);
}

export async function proxyOrchestratorJson(
  request: NextRequest,
  method: ProxyMethod,
  path: string,
  bodyTransform?: (body: unknown) => unknown,
  options: ProxyOptions = {}
) {
  const headers = buildInternalHeaders("application/json");
  const init: RequestInit = {
    method,
    headers,
    cache: "no-store"
  };

  try {
    let verifiedPrincipalPromise: Promise<SupabasePrincipal | null> | null = null;
    const getVerifiedPrincipal = () => {
      verifiedPrincipalPromise ??= resolveSupabasePrincipal(request);
      return verifiedPrincipalPromise;
    };

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

    const targetUrl = buildTargetUrl(path, request);
    if (options.injectVerifiedUserIdQuery) {
      const principal = await getVerifiedPrincipal();
      applyPrincipalQueryParams(targetUrl, options.injectVerifiedUserIdQuery, principal);
    }

    const response = await fetch(targetUrl.toString(), init);
    const payload = await response.json().catch(() => ({}));
    return NextResponse.json(payload, { status: response.ok && options.successStatus ? options.successStatus : response.status });
  } catch (error) {
    const statusCode = (error as ProxyError).statusCode;
    const errorCode = (error as ProxyError).errorCode;
    if (statusCode) {
      return NextResponse.json(
        {
          success: false,
          error_code: errorCode || "orchestrator_proxy_error",
          message: error instanceof Error ? error.message : "Proxy request failed."
        },
        { status: statusCode }
      );
    }
    return unavailableResponse();
  }
}

export async function proxyOrchestratorBinary(request: NextRequest, path: string, cacheControl?: string) {
  const headers = buildInternalHeaders();
  const targetUrl = buildTargetUrl(path, request);

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

    return new Response(await response.arrayBuffer(), {
      status: response.status,
      headers: responseHeaders
    });
  } catch {
    return unavailableResponse();
  }
}
