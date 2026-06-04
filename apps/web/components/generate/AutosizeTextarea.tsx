"use client";

import {
  type KeyboardEvent,
  type TextareaHTMLAttributes,
  useLayoutEffect,
  useRef
} from "react";

type AutosizeTextareaProps = Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "onKeyDown" | "onSubmit"> & {
  onSubmit?: () => void;
  onKeyDown?: (event: KeyboardEvent<HTMLTextAreaElement>) => void;
  submitOnEnter?: boolean;
};

export function AutosizeTextarea({
  onSubmit,
  submitOnEnter = true,
  onKeyDown,
  value,
  rows = 1,
  ...props
}: AutosizeTextareaProps) {
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  useLayoutEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) {
      return;
    }
    textarea.style.height = "auto";
    textarea.style.height = `${textarea.scrollHeight}px`;
  }, [value]);

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    onKeyDown?.(event);
    if (event.defaultPrevented || !submitOnEnter || event.shiftKey || event.key !== "Enter") {
      return;
    }
    if (event.nativeEvent.isComposing) {
      return;
    }
    event.preventDefault();
    onSubmit?.();
  }

  return <textarea ref={textareaRef} rows={rows} value={value} onKeyDown={handleKeyDown} {...props} />;
}
