function requestIdFrom(request) {
  const raw = request?.headers?.["x-request-id"] || request?.headers?.["x-easyads-trace-id"];
  return typeof raw === "string" && raw.trim() ? raw.trim() : `req_${crypto.randomUUID().replace(/-/g, "")}`;
}

export function registerErrorHandler(app) {
  app.setErrorHandler((error, request, reply) => {
    const requestId = requestIdFrom(request);
    if (error.statusCode >= 500) {
      request.log.error({
        request_id: requestId,
        error_code: error.errorCode ?? "upstream_error",
        upstream: error.upstream,
        message: error.message
      }, "BFF upstream request failed");
    }
    reply.code(error.statusCode || 502).send({
      error: error.errorCode ?? "upstream_error",
      error_code: error.errorCode ?? "upstream_error",
      message: error.message,
      request_id: requestId
    });
  });
}
