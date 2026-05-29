import type { ChatBrief, CopyOption, InferredContext } from "@/types/marketing";

const BFF_BASE_URL = process.env.NEXT_PUBLIC_BFF_BASE_URL || "http://127.0.0.1:4000";

export type ChatStartResponse = {
  jobId: string;
  threadId: string;
  status: string;
  context: InferredContext;
  copyCandidates: CopyOption[];
  recommendedCopyId?: string | null;
};

export type ChatBriefResponse = {
  jobId: string;
  threadId: string;
  status: string;
  brief: ChatBrief;
};

async function postJson<TResponse>(path: string, body: unknown): Promise<TResponse> {
  const response = await fetch(`${BFF_BASE_URL}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body)
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload?.message || payload?.error || "API request failed");
  }
  return payload as TResponse;
}

export function startChatGeneration(userInput: string): Promise<ChatStartResponse> {
  return postJson<ChatStartResponse>("/api/generate/chat/start", {
    userInput,
    adFormat: "instagram_feed"
  });
}

export function createChatBrief(input: {
  jobId: string;
  threadId: string;
  selectedCopyId: string;
  selectedChannelId: string;
  selectedTone: string;
  customDirection: string;
}): Promise<ChatBriefResponse> {
  return postJson<ChatBriefResponse>("/api/generate/chat/brief", input);
}
