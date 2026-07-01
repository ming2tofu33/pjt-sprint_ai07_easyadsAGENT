export function createHttpError(statusCode, message, errorCode) {
  const error = new Error(message);
  error.statusCode = statusCode;
  if (errorCode) error.errorCode = errorCode;
  return error;
}

export function sanitizedUpstream(url) {
  try {
    const parsed = new URL(url);
    return { host: parsed.host, path: parsed.pathname };
  } catch {
    return { host: null, path: null };
  }
}

export function createUpstreamUnavailableError(url, cause) {
  const error = createHttpError(
    502,
    cause instanceof Error && cause.message ? cause.message : "orchestrator request failed",
    "upstream_orchestrator_unavailable"
  );
  error.upstream = sanitizedUpstream(url);
  return error;
}

export function createUpstreamResponseError(url, response, payload) {
  const message = payload?.detail?.message || payload?.detail || "orchestrator request failed";
  const error = createHttpError(
    response.status,
    typeof message === "string" ? message : JSON.stringify(message),
    payload?.error_code || payload?.detail?.error_code || "upstream_error"
  );
  error.upstream = sanitizedUpstream(url);
  return error;
}
