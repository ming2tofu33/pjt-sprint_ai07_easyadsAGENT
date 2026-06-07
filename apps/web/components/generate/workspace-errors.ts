export function workspaceLoadErrorMessage(error: unknown): string {
  const message = error instanceof Error ? error.message : "";
  if (message.includes("Supabase") || message.includes("로그인") || message.includes("session")) {
    return "로그인 상태를 확인하지 못했어요. 다시 로그인한 뒤 작업방을 불러와 주세요.";
  }
  if (message.includes("Failed to fetch")) {
    return "작업방 서버에 연결하지 못했어요. 잠시 후 다시 시도해 주세요.";
  }
  return "작업방 정보를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.";
}
