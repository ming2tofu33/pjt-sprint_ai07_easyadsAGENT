"use client";

import React, {
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
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  // Auto-expand from scrollHeight, capped at maxRows lines, then scroll.
  const resize = useCallback(() => {
    const el = textareaRef.current;
    if (!el || typeof window === "undefined") {
      return;
    }
    el.style.height = "auto";
    const computed = window.getComputedStyle(el);
    const lineHeight = Number.parseFloat(computed.lineHeight) || 22;
    const paddingTop = Number.parseFloat(computed.paddingTop) || 0;
    const paddingBottom = Number.parseFloat(computed.paddingBottom) || 0;
    const maxHeight = lineHeight * maxRows + paddingTop + paddingBottom;
    const nextHeight = Math.min(el.scrollHeight, maxHeight);
    el.style.height = `${nextHeight}px`;
    el.style.overflowY = el.scrollHeight > maxHeight ? "auto" : "hidden";
  }, [maxRows]);

  useLayoutEffect(() => {
    resize();
  }, [resize, value]);

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.defaultPrevented || event.shiftKey || event.key !== "Enter") {
      return;
    }
    if (event.nativeEvent.isComposing) {
      return;
    }
    event.preventDefault();
    onSubmit();
  }

  return (
    <div className={`${styles.inputCard} ${styles.smartChatInput} ${className}`}>
      {leftControl ? <div className={styles.smartChatLeftControl}>{leftControl}</div> : null}
      <textarea
        ref={textareaRef}
        className={styles.smartChatTextarea}
        value={value}
        aria-label={ariaLabel}
        placeholder={placeholder}
        disabled={disabled}
        rows={1}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={handleKeyDown}
      />
      <div className={styles.smartChatRightControl}>{rightControl}</div>
    </div>
  );
}
