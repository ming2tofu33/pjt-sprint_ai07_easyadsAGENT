const DEFAULT_BFF_BASE_URL = "http://127.0.0.1:4000";

function configuredBffOrigin(): string | null {
  try {
    return new URL(process.env.NEXT_PUBLIC_BFF_BASE_URL || DEFAULT_BFF_BASE_URL).origin;
  } catch {
    return null;
  }
}

export function shouldUseNextImageOptimization(src: string | null | undefined): boolean {
  const normalizedSrc = src?.toLowerCase();
  if (!src || normalizedSrc?.startsWith("data:") || normalizedSrc?.startsWith("blob:")) {
    return false;
  }
  if (src.startsWith("/") && !src.startsWith("//")) {
    return true;
  }
  try {
    return new URL(src).origin === configuredBffOrigin();
  } catch {
    return false;
  }
}
