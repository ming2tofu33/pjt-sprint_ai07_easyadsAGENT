# Chat Fresh Start Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent stale chat-thread restore requests from overwriting a newly opened chat start screen or attaching a new prompt to the previous thread.

**Architecture:** Keep the fix inside `ChatGenerateClient` because the bug is a client lifecycle race between route restore and fresh-chat start. Add a monotonically increasing lifecycle token that is captured by async restore flows and invalidated by fresh starts; use that token to suppress stale dispatches and force the next prompt to create a new thread. Add focused regression tests around the existing chat client test harness.

**Tech Stack:** Next.js App Router client component, React hooks/refs, Vitest, Testing Library, TypeScript.

---

## File Structure

- Modify `apps/web/app/generate/chat/ChatGenerateClient.tsx`
  - Add a fresh-chat lifecycle ref.
  - Invalidate route/thread restore flows when the user opens a fresh chat.
  - Prevent the next prompt after a fresh-start action from using stale `threadIdParam` or `state.threadId`.
  - Guard async `threadIdParam` restore continuations with the captured lifecycle token.
- Modify `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`
  - Add a regression test for stale thread restore resolving after a fresh-chat click.
  - Verify the new prompt creates a new thread with `continuationMode: "new_thread"` and without `threadId`.

---

### Task 1: Reproduce Stale Thread Reuse On Fresh Start

**Files:**
- Modify: `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`
- Test: `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`

- [ ] **Step 1: Write the failing test**

Add this test near the existing chat-start/restore tests after `starts reference requests as a fresh chat instead of restoring the previous snapshot`:

```tsx
  it("opens a fresh studio chat without reusing a stale query thread id", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.createGenerationJob).mockClear();
    searchParamsMock.value = new URLSearchParams("threadId=thread_stale_query");
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="studio" />);

    fireEvent.click(screen.getByText("대화로 시작하기"));
    expect(screen.getByText("대화로 찰떡 이미지 만들기")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("광고 요청 입력"), {
      target: { value: "새로운 프리미엄 뷰티살롱 홍보 포스터 만들어줘" }
    });
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    await waitFor(() =>
      expect(api.createGenerationJob).toHaveBeenCalledWith(
        expect.objectContaining({
          userInput: "새로운 프리미엄 뷰티살롱 홍보 포스터 만들어줘",
          continuationMode: "new_thread"
        })
      )
    );
    const [payload] = vi.mocked(api.createGenerationJob).mock.calls[0];
    expect(payload.threadId).toBeUndefined();
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd apps/web && npx vitest run app/generate/chat/ChatGenerateClient.test.tsx -t "opens a fresh studio chat without reusing a stale query thread id"
```

Expected: FAIL because the new generation payload still carries the old query `threadId` and uses `continuationMode: "new_turn"`.

- [ ] **Step 3: Commit the failing test**

```bash
git add apps/web/app/generate/chat/ChatGenerateClient.test.tsx
git commit -m "test(web): reproduce stale chat restore race"
```

---

### Task 2: Add Fresh Chat Lifecycle Guard

**Files:**
- Modify: `apps/web/app/generate/chat/ChatGenerateClient.tsx`
- Test: `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`

- [ ] **Step 1: Add lifecycle refs**

In `ChatGenerateClient`, next to the existing refs:

```tsx
  const activeThreadRef = useRef({ threadId: "", conversationMessageCount: 0 });
  const freshChatSessionRef = useRef(0);
  const forceNextPromptNewThreadRef = useRef(false);
  const finalGenerationJobIdsRef = useRef<Set<string>>(new Set());
```

- [ ] **Step 2: Guard the `threadIdParam` restore effect**

Inside the `if (threadIdParam) { ... }` block, immediately after the early active-thread return, capture the current token:

```tsx
      const restoreSession = freshChatSessionRef.current;
      let isActive = true;
```

Replace stale checks inside that block with this condition:

```tsx
        if (!isActive || restoreSession !== freshChatSessionRef.current) {
          return;
        }
        if (activeThreadRef.current.threadId && threadIdParam !== activeThreadRef.current.threadId) {
          return;
        }
```

Use the same `restoreSession !== freshChatSessionRef.current` guard after each awaited `getGenerationJob(...)` call in the `view_result`, `answer_pending_job`, and `locked_running` branches.

- [ ] **Step 3: Invalidate restore work when opening a fresh chat**

Replace `handleOpenFreshChat()` with:

```tsx
  function handleOpenFreshChat() {
    freshChatSessionRef.current += 1;
    forceNextPromptNewThreadRef.current = true;
    activeThreadRef.current = { threadId: "", conversationMessageCount: 0 };
    clearChatFlowSnapshot();
    clearChatTurnSnapshot();
    clearGenerationFailureSnapshot();
    clearGenerationDraftPrompt();
    dispatch({ type: "reset" });
    setCurrentThreadIsArchived(false);
    setShowHistory(false);
    setGenerationStage("brief");
    lastPrimedStageRef.current = "start";
    navigateTo("chat", "start");
  }
```

- [ ] **Step 4: Force the next fresh prompt to create a new thread**

In `handleSubmitPrompt()`, replace:

```tsx
      const activeThreadId = toGenerationJobThreadId(threadIdParam || state.threadId);
```

with:

```tsx
      const forceNewThread = forceNextPromptNewThreadRef.current;
      const activeThreadId = forceNewThread ? null : toGenerationJobThreadId(threadIdParam || state.threadId);
```

After `createGenerationJob(...)` resolves, before any branch returns, add:

```tsx
      forceNextPromptNewThreadRef.current = false;
```

The request payload remains:

```tsx
        threadId: activeThreadId,
        continuationMode: activeThreadId ? "new_turn" : "new_thread",
```

Because the shared `compactPayload` removes the `null` top-level `threadId`, the API receives a new-thread request.

- [ ] **Step 5: Run the focused test**

Run:

```bash
cd apps/web && npx vitest run app/generate/chat/ChatGenerateClient.test.tsx -t "opens a fresh studio chat without reusing a stale query thread id"
```

Expected: PASS.

- [ ] **Step 6: Commit implementation**

```bash
git add apps/web/app/generate/chat/ChatGenerateClient.tsx
git commit -m "fix(web): isolate fresh chat starts from stale restores"
```

---

### Task 3: Regression Verification

**Files:**
- Test: `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`
- Test: `apps/web/lib/api-client.test.ts`

- [ ] **Step 1: Run focused chat client tests**

Run:

```bash
cd apps/web && npx vitest run app/generate/chat/ChatGenerateClient.test.tsx
```

Expected: PASS. Existing React `act(...)` warnings may appear from old tests, but no test should fail.

- [ ] **Step 2: Run API client tests**

Run:

```bash
cd apps/web && npx vitest run lib/api-client.test.ts
```

Expected: PASS.

- [ ] **Step 3: Run TypeScript check**

Run:

```bash
cd apps/web && npx tsc --noEmit
```

Expected: PASS.

- [ ] **Step 4: Check diff hygiene**

Run:

```bash
git diff --check origin/main..HEAD
```

Expected: no new whitespace errors from this branch. If the command reports whitespace already present from `origin/main`, confirm `git diff --check HEAD~2..HEAD` for only this fix.

---

## Self-Review

- Spec coverage: The plan covers stale restore cancellation, fresh chat isolation, preventing old `threadId` reuse, and regression verification.
- Placeholder scan: No placeholder tasks or undefined functions are required.
- Type consistency: The plan uses existing `ChatGenerateClient`, `createGenerationJob`, `getChatThreadState`, `threadId`, and `continuationMode` names already present in the codebase.
