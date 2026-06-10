"use client";

import React, {
  type ClipboardEvent,
  type KeyboardEvent,
  type ReactNode,
  useCallback,
  useLayoutEffect,
  useRef
} from "react";
import styles from "./generate.module.css";

type SmartChatInputProps = {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  ariaLabel: string;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  leftControl?: ReactNode;
  rightControl: ReactNode;
  maxRows?: number;
};

function readEditableText(element: HTMLElement) {
  return element.innerText ?? element.textContent ?? "";
}

export function SmartChatInput({
  value,
  onChange,
  onSubmit,
  ariaLabel,
  placeholder = "",
  disabled = false,
  className = "",
  leftControl,
  rightControl,
  maxRows = 4
}: SmartChatInputProps) {
  const editorRef = useRef<HTMLDivElement | null>(null);
  const surfaceRef = useRef<HTMLDivElement | null>(null);

  const syncMetrics = useCallback(() => {
    const editor = editorRef.current;
    const surface = surfaceRef.current;
    if (!editor || !surface || typeof window === "undefined") {
      return;
    }

    const stylesForEditor = window.getComputedStyle(editor);
    const lineHeight = Number.parseFloat(stylesForEditor.lineHeight) || 22;
    const paddingTop = Number.parseFloat(stylesForEditor.paddingTop) || 0;
    const paddingBottom = Number.parseFloat(stylesForEditor.paddingBottom) || 0;
    const maxHeight = lineHeight * maxRows + paddingTop + paddingBottom;
    const editorHeight = Math.max(42, Math.min(editor.scrollHeight || 42, maxHeight));

    surface.style.setProperty("--smart-chat-editor-height", `${editorHeight}px`);
    surface.style.setProperty("--smart-chat-max-height", `${maxHeight}px`);
  }, [maxRows]);

  useLayoutEffect(() => {
    const editor = editorRef.current;
    if (!editor) {
      return;
    }
    if (readEditableText(editor) !== value) {
      editor.textContent = value;
    }
    editor.dataset.empty = value.length === 0 ? "true" : "false";
    syncMetrics();
  }, [syncMetrics, value]);

  useLayoutEffect(() => {
    const editor = editorRef.current;
    if (!editor) {
      return;
    }

    Object.defineProperty(editor, "value", {
      configurable: true,
      get() {
        return readEditableText(editor);
      },
      set(nextValue) {
        editor.textContent = String(nextValue ?? "");
      }
    });
  }, []);

  const emitChange = useCallback(() => {
    const editor = editorRef.current;
    if (!editor) {
      return;
    }
    const nextValue = readEditableText(editor);
    editor.dataset.empty = nextValue.length === 0 ? "true" : "false";
    onChange(nextValue);
    if (typeof window.requestAnimationFrame === "function") {
      window.requestAnimationFrame(syncMetrics);
    } else {
      syncMetrics();
    }
  }, [onChange, syncMetrics]);

  useLayoutEffect(() => {
    const editor = editorRef.current;
    if (!editor) {
      return undefined;
    }
    editor.addEventListener("change", emitChange);
    return () => editor.removeEventListener("change", emitChange);
  }, [emitChange]);

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.defaultPrevented || event.shiftKey || event.key !== "Enter") {
      return;
    }
    if (event.nativeEvent.isComposing) {
      return;
    }
    event.preventDefault();
    onSubmit();
  }

  function handlePaste(event: ClipboardEvent<HTMLDivElement>) {
    const text = event.clipboardData.getData("text/plain");
    if (!text) {
      return;
    }
    event.preventDefault();
    document.execCommand("insertText", false, text);
    emitChange();
  }

  return (
    <div className={`${styles.inputCard} ${styles.smartChatInput} ${className}`}>
      <div className={styles.smartChatSurface} ref={surfaceRef}>
        {leftControl ? (
          <>
            <span className={`${styles.smartChatFloatPush} ${styles.smartChatFloatLeft}`} aria-hidden="true" />
            <span className={`${styles.smartChatFloatReserve} ${styles.smartChatFloatLeft} ${styles.smartChatFloatReserveLeft}`} aria-hidden="true" />
          </>
        ) : null}
        <span className={`${styles.smartChatFloatPush} ${styles.smartChatFloatRight}`} aria-hidden="true" />
        <span className={`${styles.smartChatFloatReserve} ${styles.smartChatFloatRight} ${styles.smartChatFloatReserveRight}`} aria-hidden="true" />
        <div
          ref={editorRef}
          aria-disabled={disabled || undefined}
          aria-label={ariaLabel}
          aria-multiline="true"
          className={styles.smartChatEditor}
          contentEditable={disabled ? false : "plaintext-only"}
          data-empty={value.length === 0 ? "true" : "false"}
          data-placeholder={placeholder}
          role="textbox"
          suppressContentEditableWarning
          tabIndex={disabled ? -1 : 0}
          onChange={emitChange}
          onInput={emitChange}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
        />
      </div>
      {leftControl ? <div className={styles.smartChatLeftControl}>{leftControl}</div> : null}
      <div className={styles.smartChatRightControl}>{rightControl}</div>
    </div>
  );
}
