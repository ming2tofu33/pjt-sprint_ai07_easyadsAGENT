import { Suspense } from "react";
import { ChatGenerateClient } from "./ChatGenerateClient";

export default function ChatGeneratePage() {
  return (
    <Suspense fallback={null}>
      <ChatGenerateClient />
    </Suspense>
  );
}
