import { NextRequest, NextResponse } from "next/server";

type ProxyMethod = "GET" | "POST" | "PATCH";
type ProxyOptions = {
  injectVerifiedUserId?: boolean;
  injectVerifiedUserIdHeader?: boolean;
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

function buildTargetUrl(path: string, request: NextRequest): string {
  const target = new URL(path, getOrchestratorBaseUrl());
  request.nextUrl.searchParams.forEach((value, key) => {
    target.searchParams.append(key, value);
  });
  return target.toString();
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

export async function proxyOrchestratorJson(
  request: NextRequest,
  method: ProxyMethod,
  path: string,
  bodyTransform?: (body: unknown) => unknown,
  options: ProxyOptions = {}
) {
  const headers: Record<string, string> = { "content-type": "application/json" };
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
      if (body) {
        const rawPayload = bodyTransform ? bodyTransform(JSON.parse(body)) : JSON.parse(body);
        const payload =
          rawPayload && typeof rawPayload === "object" && !Array.isArray(rawPayload)
            ? { ...(rawPayload as Record<string, unknown>) }
            : rawPayload;
        if (options.injectVerifiedUserId && payload && typeof payload === "object" && !Array.isArray(payload)) {
          delete (payload as Record<string, unknown>).user_id;
          delete (payload as Record<string, unknown>).userId;
          delete (payload as Record<string, unknown>).account_type;
          delete (payload as Record<string, unknown>).accountType;
          const principal = await getVerifiedPrincipal();
          if (principal) {
            (payload as Record<string, unknown>).userId = principal.userId;
            (payload as Record<string, unknown>).accountType = principal.accountType;
          }
        }
        init.body = JSON.stringify(payload);
      }
    }

    const response = await fetch(buildTargetUrl(path, request), init);
    const payload = await response.json().catch(() => ({}));
    return NextResponse.json(payload, { status: response.status });
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
}
