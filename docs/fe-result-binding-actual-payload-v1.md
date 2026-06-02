# FE Result Binding Actual Payload v1

## 1. Purpose

This pass hardens the frontend result UX for actual `GenerationJob.result_payload` responses. Actual generation can complete with local runtime artifact paths while public `final_image_url` and `download_url` are still null because static serving, R2 upload, and signed URL support are not implemented yet.

## 2. ResultArtifactPayload Policy

The frontend accepts the backend snake_case payload as-is. Important fields are:

- `final_image_url`
- `download_url`
- `preview_image_url`
- `copy_visual_preview_url`
- `final_image_path`
- `download_path`
- `output_dir`
- `prompt_summary`
- `validation_summary`
- `copy_summary`
- `layout_summary`
- `render_summary`

The frontend does not convert local artifact paths into browser URLs.

## 3. Preview Policy

Preview image URL priority:

1. `result_payload.final_image_url`
2. `result_payload.preview_image_url`
3. `result_payload.copy_visual_preview_url`
4. `result_payload.download_url`
5. `null`

`final_image_path`, `download_path`, and `job.output_path` are not used as `img src` values.

## 4. Download Policy

Download URL priority:

1. `result_payload.download_url`
2. `result_payload.final_image_url`
3. `result_payload.preview_image_url`
4. `result_payload.copy_visual_preview_url`
5. `null`

The download button is enabled only when one of those public URLs exists.

## 5. Local Path Handling

The frontend treats these as local artifact paths and never uses them as public `href` or `src` values:

- `data/outputs/`
- `data/logs/`
- `./data/`
- `../data/`
- Windows drive paths such as `C:\...`
- `/home/...`
- `/tmp/...`

In development mode, local paths may appear only inside debug details. They are not copied as user-facing result text.

## 6. Result States

- `queued` / `running`: show in-progress notice; preview and download remain disabled.
- `done` + public URL: show preview, enable download, allow result summary copy.
- `done` + local path only: show a completion notice plus "browser-displayable URL not connected yet"; do not show preview; keep download disabled; allow summary copy.
- `done` + no payload: show warning that result details are empty.
- `failed`: show error notice and keep preview/download disabled.

## 7. Copy Summary Policy

The result summary copy includes job id, status, engine/run-mode details, public image/download URLs when available, and sanitized summaries. It does not include local `data/outputs` paths, raw prompts, API keys, tokens, or secret-like fields.

## 8. Follow-up

Next implementation should decide between backend static serving, Cloudflare R2 upload, or signed URL generation so `final_image_url` and `download_url` can be populated for browser preview and download.
