"use client";

import { Check, Eye, ImagePlus, Loader2, UploadCloud } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  createAdminReferenceTemplate,
  listAdminReferenceTemplates,
  publishAdminReferenceTemplate,
  uploadReferenceImageToR2,
  type AdminReferenceTemplate,
  type AssetUploadResponse
} from "@/lib/api-client";
import styles from "../admin.module.css";

function splitTerms(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function aspectRatio(width?: number | null, height?: number | null): string {
  if (!width || !height) {
    return "1:1";
  }
  const divisor = gcd(width, height);
  return `${Math.round(width / divisor)}:${Math.round(height / divisor)}`;
}

function gcd(left: number, right: number): number {
  let a = Math.abs(left);
  let b = Math.abs(right);
  while (b) {
    const next = a % b;
    a = b;
    b = next;
  }
  return a || 1;
}

export function AdminReferenceUploadClient() {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [asset, setAsset] = useState<AssetUploadResponse | null>(null);
  const [items, setItems] = useState<AdminReferenceTemplate[]>([]);
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("cafe");
  const [description, setDescription] = useState("");
  const [tags, setTags] = useState("");
  const [businessTypes, setBusinessTypes] = useState("cafe");
  const [styleKeywords, setStyleKeywords] = useState("");
  const [colorPalette, setColorPalette] = useState("");
  const [layoutHint, setLayoutHint] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const detectedAspectRatio = useMemo(() => aspectRatio(asset?.width, asset?.height), [asset?.width, asset?.height]);

  useEffect(() => {
    void refreshItems();
  }, []);

  useEffect(() => {
    if (!file) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  async function refreshItems() {
    try {
      const templates = await listAdminReferenceTemplates();
      setItems(templates);
    } catch {
      setItems([]);
    }
  }

  async function handleUpload() {
    if (!file) {
      setErrorMessage("이미지 파일을 선택해 주세요.");
      return;
    }
    setErrorMessage(null);
    setMessage(null);
    setIsUploading(true);
    try {
      const uploaded = await uploadReferenceImageToR2(file);
      setAsset(uploaded);
      setMessage("업로드가 완료됐어요.");
      if (!title) {
        setTitle(file.name.replace(/\.[^.]+$/, ""));
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "업로드에 실패했어요.");
    } finally {
      setIsUploading(false);
    }
  }

  async function handleSave(status: "draft" | "active") {
    if (!asset?.assetId) {
      setErrorMessage("업로드 완료 후 저장할 수 있어요.");
      return;
    }
    setErrorMessage(null);
    setMessage(null);
    setIsSaving(true);
    try {
      await createAdminReferenceTemplate({
        assetId: asset.assetId,
        title,
        description: description || null,
        category,
        tags: splitTerms(tags),
        businessTypes: splitTerms(businessTypes),
        adFormats: ["instagram_feed"],
        platforms: ["instagram"],
        aspectRatio: detectedAspectRatio,
        styleKeywords: splitTerms(styleKeywords),
        colorPalette: splitTerms(colorPalette),
        layoutHint: layoutHint || null,
        status,
        licenseNote: "owned or licensed reference image for EasyAds service",
        metadata: {
          uploaded_from: "admin_references_page",
          original_filename: file?.name ?? null
        }
      });
      setMessage(status === "active" ? "게시됐어요." : "초안으로 저장됐어요.");
      setAsset(null);
      setFile(null);
      setTitle("");
      setDescription("");
      await refreshItems();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "저장에 실패했어요.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handlePublish(templateId: string) {
    setErrorMessage(null);
    try {
      await publishAdminReferenceTemplate(templateId);
      await refreshItems();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "게시 상태를 바꾸지 못했어요.");
    }
  }

  return (
    <div className={styles.adminStack}>
      <section className={styles.uploadPanel}>
        <label className={styles.fileDrop}>
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            onChange={(event) => {
              setFile(event.target.files?.[0] ?? null);
              setAsset(null);
            }}
          />
          {previewUrl ? <img src={previewUrl} alt="선택한 레퍼런스" /> : <ImagePlus size={30} aria-hidden="true" />}
        </label>
        <button className={styles.primaryButton} type="button" onClick={handleUpload} disabled={!file || isUploading}>
          {isUploading ? <Loader2 size={18} aria-hidden="true" /> : <UploadCloud size={18} aria-hidden="true" />}
          {isUploading ? "업로드 중" : "이미지 업로드"}
        </button>
        {asset ? (
          <dl className={styles.metaGrid}>
            <div><dt>상태</dt><dd>{asset.status}</dd></div>
            <div><dt>크기</dt><dd>{asset.width ?? "-"} x {asset.height ?? "-"}</dd></div>
            <div><dt>형식</dt><dd>{asset.mimeType ?? "-"}</dd></div>
            <div><dt>비율</dt><dd>{detectedAspectRatio}</dd></div>
          </dl>
        ) : null}
      </section>

      <section className={styles.formPanel}>
        <label>제목<input value={title} onChange={(event) => setTitle(event.target.value)} /></label>
        <label>카테고리<input value={category} onChange={(event) => setCategory(event.target.value)} /></label>
        <label>설명<textarea value={description} onChange={(event) => setDescription(event.target.value)} /></label>
        <label>태그<input value={tags} onChange={(event) => setTags(event.target.value)} placeholder="음료, 여름" /></label>
        <label>업종<input value={businessTypes} onChange={(event) => setBusinessTypes(event.target.value)} placeholder="cafe, restaurant" /></label>
        <label>스타일<input value={styleKeywords} onChange={(event) => setStyleKeywords(event.target.value)} placeholder="clean, premium" /></label>
        <label>색상<input value={colorPalette} onChange={(event) => setColorPalette(event.target.value)} placeholder="#F5F0E7, #2A2724" /></label>
        <label>레이아웃<input value={layoutHint} onChange={(event) => setLayoutHint(event.target.value)} /></label>
        <div className={styles.buttonRow}>
          <button className={styles.secondaryButton} type="button" disabled={isSaving || !asset} onClick={() => handleSave("draft")}>
            <Check size={16} aria-hidden="true" />초안 저장
          </button>
          <button className={styles.primaryButton} type="button" disabled={isSaving || !asset} onClick={() => handleSave("active")}>
            <Eye size={16} aria-hidden="true" />게시
          </button>
        </div>
        {message ? <p className={styles.successText}>{message}</p> : null}
        {errorMessage ? <p className={styles.errorText}>{errorMessage}</p> : null}
      </section>

      <section className={styles.referenceList} aria-label="등록된 샘플">
        {items.map((item) => (
          <article className={styles.referenceRow} key={item.templateId}>
            {item.previewUrl ? <img src={item.previewUrl} alt="" /> : <span aria-hidden="true"><ImagePlus size={18} /></span>}
            <div>
              <strong>{item.title}</strong>
              <small>{item.category} · {item.status ?? "draft"}</small>
            </div>
            {item.status !== "active" ? (
              <button type="button" onClick={() => handlePublish(item.templateId)}>게시</button>
            ) : null}
          </article>
        ))}
      </section>
    </div>
  );
}
