export type ExceptionStateKind = "searchEmpty" | "archiveEmpty" | "uploadFailed" | "generationFailed";

const exceptionStateHrefs: Record<ExceptionStateKind, string> = {
  searchEmpty: "/reference/empty",
  archiveEmpty: "/ads/empty",
  uploadFailed: "/generate/photo/upload-failed",
  generationFailed: "/generate/chat/failed"
};

export function buildExceptionStateHref(kind: ExceptionStateKind): string {
  return exceptionStateHrefs[kind];
}
