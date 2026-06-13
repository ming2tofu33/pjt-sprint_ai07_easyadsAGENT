# BFF Route Parity Inventory

Date: 2026-06-12

## Purpose

This document tracks the migration from the Fastify BFF (`apps/bff`) to Next Route Handlers (`apps/web/app/api`). It exists so the team can see which browser-facing `/api/*` paths are safe on Vercel/same-origin and which still depend on the separate Fastify server.

## Already Present In Next Route Handlers

- `/api/account/delete`
- `/api/brand-kits`
- `/api/brand-kits/current`
- `/api/brand-kits/[brandKitId]`
- `/api/generated-assets`
- `/api/generation-jobs`
- `/api/generation-jobs/[jobId]`
- `/api/generation-jobs/[jobId]/answer`
- `/api/references`
- `/api/references/[templateId]`
- `/api/references/[templateId]/similar`

## Missing From Next Route Handlers

- `/api/generate/chat/start`
- `/api/generate/chat/brief`
- `/api/generate/chat/answer`
- `/api/generate/photo/upload`
- `/api/generate/photo/start`
- `/api/assets/uploads/presign`
- `/api/assets/uploads/[assetId]/complete`
- `/api/assets/[assetId]`
- `/api/chat-threads`
- `/api/chat-threads/[threadId]`
- `/api/chat-threads/[threadId]/messages`
- `/api/chat-threads/[threadId]/state`
- `/api/chat-threads/[threadId]/archive`
- `/api/archive/items`
- `/api/archive/items/[archiveItemId]`
- `/api/admin/references`
- `/api/admin/references/[templateId]`
- `/api/admin/references/[templateId]/publish`
- `/api/admin/references/[templateId]/unpublish`
- `/api/references/temp-assets/[removalGroup]/[filename]`

## Migration Rule

Do not change `NEXT_PUBLIC_BFF_BASE_URL` to same-origin until `apps/web/app/api/_proxy/route-parity.test.ts` is green.
