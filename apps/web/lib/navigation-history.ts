type BackNavigationRouter = {
  back: () => void;
  push: (href: string) => void;
};

function browserHistoryLength(): number {
  if (typeof window === "undefined") {
    return 0;
  }

  return window.history.length;
}

export function shouldUseHistoryBack(historyLength = browserHistoryLength()): boolean {
  return historyLength > 1;
}

export function goBackOrPush(router: BackNavigationRouter, fallbackHref: string, historyLength = browserHistoryLength()): void {
  if (shouldUseHistoryBack(historyLength)) {
    router.back();
    return;
  }

  router.push(fallbackHref);
}
