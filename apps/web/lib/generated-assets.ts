const GENERATED_OUTPUT_MARKER = "data/outputs/";

export function normalizeGeneratedOutputPath(path: string | null | undefined): string | null {
  if (!path) {
    return null;
  }

  const normalized = path.replace(/\\/g, "/");
  const markerIndex = normalized.indexOf(GENERATED_OUTPUT_MARKER);
  if (markerIndex < 0) {
    return null;
  }

  const outputPath = normalized.slice(markerIndex);
  if (outputPath.includes("..")) {
    return null;
  }

  return outputPath;
}

export function buildGeneratedAssetUrl(path: string | null | undefined): string | null {
  const outputPath = normalizeGeneratedOutputPath(path);
  if (!outputPath) {
    return null;
  }

  return `/api/generated-assets?path=${encodeURIComponent(outputPath)}`;
}
