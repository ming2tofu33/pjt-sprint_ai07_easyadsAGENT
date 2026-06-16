from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from psycopg.rows import dict_row
import psycopg


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = REPO_ROOT / "data" / "performance" / "db_runtime_v1"
SEED_VERSION = "db-runtime-v1"
RANDOM_SEED = 20260616


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url-env", default="DATABASE_URL")
    parser.add_argument("--dataset", choices=("small", "medium"), default="medium")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    parser.add_argument("--self-check", action="store_true")
    return parser.parse_args()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def deterministic_uuid(name: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"{SEED_VERSION}:{name}"))


def count_plan(dataset: str) -> dict[str, int]:
    if dataset == "small":
        return {
            "workspaces": 1,
            "profiles": 1,
            "workspace_members": 1,
            "chat_threads": 5,
            "chat_messages": 100,
            "generation_jobs": 20,
            "generation_outputs": 20,
            "archive_items": 20,
            "assets": 40,
        }
    return {
        "workspaces": 1,
        "profiles": 1,
        "workspace_members": 1,
        "chat_threads": 50,
        "chat_messages": 5000,
        "generation_jobs": 500,
        "generation_outputs": 300,
        "archive_items": 300,
        "assets": 600,
    }


def heavy_payload(label: str, scale: str) -> dict[str, Any]:
    repeat = {"small": 4, "medium": 30, "large": 90}[scale]
    text = f"{label}-" + ("payload-" * repeat)
    return {
        "schema_version": "result_artifact_v1",
        "label": label,
        "headline": f"{label} headline",
        "download_url": f"https://cdn.example.com/{label}/download.png",
        "final_image_url": f"https://cdn.example.com/{label}/final.png",
        "image_url": f"https://cdn.example.com/{label}/image.png",
        "summary": text,
        "items": [{"id": i, "text": f"{text}{i}"} for i in range(min(repeat, 20))],
        "metadata": {"note": text, "flags": ["benchmark", scale, label]},
    }


def fixture_descriptor(dataset: str) -> dict[str, Any]:
    return {
        "seed_version": SEED_VERSION,
        "random_seed": RANDOM_SEED,
        "dataset": dataset,
        "counts": count_plan(dataset),
        "payload_shapes": {
            "small": heavy_payload("small", "small"),
            "representative_medium": heavy_payload("medium", "medium"),
            "representative_large": heavy_payload("large", "large"),
        },
    }


def fixture_hash(dataset: str) -> str:
    return stable_hash(json.dumps(fixture_descriptor(dataset), ensure_ascii=False, sort_keys=True))


def database_url_from_env(env_name: str) -> str:
    value = os.getenv(env_name, "").strip()
    if not value:
        raise SystemExit(f"missing database url env: {env_name}")
    return value


def truncate_all(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            truncate table
                archive_items,
                generation_job_events,
                generation_outputs,
                generation_jobs,
                chat_message_assets,
                assets,
                chat_messages,
                chat_threads,
                brand_kits,
                projects,
                workspace_members,
                profiles,
                workspaces
            restart identity cascade
            """
        )


def insert_seed(conn: psycopg.Connection, dataset: str) -> dict[str, Any]:
    counts = count_plan(dataset)
    rng = random.Random(RANDOM_SEED)
    started_at = datetime(2026, 6, 16, 0, 0, tzinfo=UTC)
    workspace_id = deterministic_uuid("workspace")
    user_id = "perf_user_1"
    thread_ids = [deterministic_uuid(f"thread:{i}") for i in range(counts["chat_threads"])]
    job_ids = [deterministic_uuid(f"job:{i}") for i in range(counts["generation_jobs"])]
    output_ids = [deterministic_uuid(f"output:{i}") for i in range(counts["generation_outputs"])]
    asset_ids = [deterministic_uuid(f"asset:{i}") for i in range(counts["assets"])]
    archive_ids = [deterministic_uuid(f"archive:{i}") for i in range(counts["archive_items"])]

    plain_thread_public_id = "thread_perf_0000"
    linked_thread_public_id = "thread_perf_0010" if counts["chat_threads"] > 10 else "thread_perf_0001"

    with conn.cursor() as cur:
        cur.execute(
            """
            insert into profiles (id, user_id, email, display_name, metadata)
            values (%s::uuid, %s, %s, %s, %s::jsonb)
            """,
            (deterministic_uuid("profile"), user_id, "perf@example.com", "Perf User", json.dumps({"source": "benchmark"})),
        )
        cur.execute(
            """
            insert into workspaces (id, name, owner_user_id, metadata)
            values (%s::uuid, %s, %s, %s::jsonb)
            """,
            (workspace_id, "Perf Workspace", user_id, json.dumps({"source": "benchmark"})),
        )
        cur.execute(
            """
            insert into workspace_members (id, workspace_id, user_id, role)
            values (%s::uuid, %s::uuid, %s, 'owner')
            """,
            (deterministic_uuid("member"), workspace_id, user_id),
        )

        for index, thread_id in enumerate(thread_ids):
            created_at = started_at + timedelta(minutes=index)
            cur.execute(
                """
                insert into chat_threads (
                    id, public_thread_id, workspace_id, created_by, title, status,
                    final_brief, last_message_at, created_at, updated_at
                ) values (
                    %s::uuid, %s, %s::uuid, %s, %s, %s,
                    %s::jsonb, %s, %s, %s
                )
                """,
                (
                    thread_id,
                    f"thread_perf_{index:04d}",
                    workspace_id,
                    user_id,
                    f"Perf Thread {index:04d}",
                    "completed" if index % 3 else "generating",
                    json.dumps({"summary": f"thread-{index}", "payload": heavy_payload(f"thread-{index}", "small")}),
                    created_at,
                    created_at,
                    created_at,
                ),
            )

        for index, asset_id in enumerate(asset_ids):
            created_at = started_at + timedelta(seconds=index)
            thread_id = thread_ids[index % len(thread_ids)]
            cur.execute(
                """
                insert into assets (
                    id, public_asset_id, workspace_id, thread_id, created_by, kind, storage_provider,
                    bucket, object_key, mime_type, size_bytes, width, height, checksum_sha256,
                    public_url, metadata, created_at, updated_at
                ) values (
                    %s::uuid, %s, %s::uuid, %s::uuid, %s, %s, 'r2',
                    %s, %s, 'image/png', %s, %s, %s, %s,
                    %s, %s::jsonb, %s, %s
                )
                """,
                (
                    asset_id,
                    f"asset_{index:04d}",
                    workspace_id,
                    thread_id,
                    user_id,
                    "generated" if index % 2 else "source",
                    "perf-bucket",
                    f"perf/object/{index:04d}.png",
                    1024 + index,
                    1080,
                    1080,
                    stable_hash(f"asset:{index}"),
                    f"https://cdn.example.com/assets/{index:04d}.png",
                    json.dumps({"upload": {"status": "ready"}, "seed_index": index}),
                    created_at,
                    created_at,
                ),
            )

        for index, job_id in enumerate(job_ids):
            created_at = started_at + timedelta(minutes=index)
            thread_id = thread_ids[index % len(thread_ids)]
            payload_scale = "large" if index % 7 == 0 else "medium"
            cur.execute(
                """
                insert into generation_jobs (
                    id, public_job_id, workspace_id, thread_id, requested_by, status, current_stage, progress_percent,
                    attempt_no, run_mode, engine, model_provider, model_name, prompt_text, prompt_hash, prompt_preview,
                    brief, brand_kit_snapshot, params, request_payload, modal_call_id, retry_count, queued_at, started_at,
                    finished_at, output_path, result_payload, error, metadata, created_at, updated_at
                ) values (
                    %s::uuid, %s, %s::uuid, %s::uuid, %s, %s, %s, %s,
                    1, 'graph_job', 'gpt_image_2', 'openai', 'gpt-image-2', %s, %s, %s,
                    %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s, 0, %s, %s,
                    %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s
                )
                """,
                (
                    job_id,
                    f"job_perf_{index:04d}",
                    workspace_id,
                    thread_id,
                    user_id,
                    "done" if index < counts["generation_outputs"] else "running",
                    "completed" if index < counts["generation_outputs"] else "running",
                    100 if index < counts["generation_outputs"] else 60,
                    f"Prompt {index}",
                    stable_hash(f"prompt:{index}"),
                    f"Prompt preview {index}",
                    json.dumps({"item_or_service": f"Item {index}", "campaign": heavy_payload(f"brief-{index}", payload_scale)}),
                    json.dumps({"brand": f"Brand {index}", "snapshot": heavy_payload(f"brand-{index}", payload_scale)}),
                    json.dumps({"ad_format": "instagram_feed", "platform": "instagram", "extra": heavy_payload(f"params-{index}", payload_scale)}),
                    json.dumps({"ad_format": "instagram_feed", "platform": "instagram", "input": heavy_payload(f"request-{index}", payload_scale)}),
                    f"modal_{index:04d}",
                    created_at,
                    created_at + timedelta(seconds=3),
                    created_at + timedelta(seconds=8),
                    f"data/outputs/job_perf_{index:04d}/final.png",
                    json.dumps(heavy_payload(f"result-{index}", payload_scale)),
                    json.dumps({}) if index % 17 else json.dumps({"error_code": "seeded_warning", "detail": heavy_payload(f"error-{index}", "small")}),
                    json.dumps({"user_id": user_id, "ad_format": "instagram_feed", "platform": "instagram", "trace": heavy_payload(f"meta-{index}", payload_scale)}),
                    created_at,
                    created_at,
                ),
            )

        final_output_count = len(thread_ids)
        for index in range(counts["generation_outputs"]):
            created_at = started_at + timedelta(minutes=index, seconds=30)
            thread_id = thread_ids[index % len(thread_ids)]
            is_final = index < final_output_count
            cur.execute(
                """
                insert into generation_outputs (
                    id, public_output_id, workspace_id, thread_id, job_id, asset_id, thumbnail_asset_id,
                    variant_index, output_type, result_payload, is_final, metadata, created_at, updated_at
                ) values (
                    %s::uuid, %s, %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid,
                    %s, 'final_image', %s::jsonb, %s, %s::jsonb, %s, %s
                )
                """,
                (
                    output_ids[index],
                    f"output_perf_{index:04d}",
                    workspace_id,
                    thread_id,
                    job_ids[index],
                    asset_ids[index],
                    asset_ids[(index + counts["generation_outputs"]) % len(asset_ids)],
                    index % 4,
                    json.dumps(heavy_payload(f"output-{index}", "medium")),
                    is_final,
                    json.dumps({"seed_index": index}),
                    created_at,
                    created_at,
                ),
            )

        for index in range(counts["archive_items"]):
            created_at = started_at + timedelta(minutes=index, seconds=50)
            cur.execute(
                """
                insert into archive_items (
                    id, public_archive_id, workspace_id, created_by, job_id, output_id, asset_id, public_job_id,
                    title, thumbnail_url, image_url, status, ad_format, platform, source, metadata, saved_at, created_at, updated_at
                ) values (
                    %s::uuid, %s, %s::uuid, %s, %s::uuid, %s::uuid, %s::uuid, %s,
                    %s, %s, %s, 'saved', 'instagram_feed', 'instagram', 'generated', %s::jsonb, %s, %s, %s
                )
                """,
                (
                    archive_ids[index],
                    f"archive_perf_{index:04d}",
                    workspace_id,
                    user_id,
                    job_ids[index],
                    output_ids[index],
                    asset_ids[index],
                    f"job_perf_{index:04d}",
                    f"Archive {index:04d}",
                    f"https://cdn.example.com/thumb/{index:04d}.png",
                    f"https://cdn.example.com/image/{index:04d}.png",
                    json.dumps({"seed_index": index, "archive_payload": heavy_payload(f"archive-{index}", "small")}),
                    created_at,
                    created_at,
                    created_at,
                ),
            )

        for index in range(counts["chat_messages"]):
            created_at = started_at + timedelta(seconds=index)
            thread_index = index % len(thread_ids)
            thread_id = thread_ids[thread_index]
            if thread_index == 0:
                linked_job_id = None
            elif thread_index == 10:
                linked_job_id = job_ids[index % counts["generation_outputs"]]
            else:
                linked_job_id = job_ids[index % counts["generation_outputs"]] if index % 4 == 0 else None
            cur.execute(
                """
                insert into chat_messages (
                    id, workspace_id, thread_id, sequence_no, role, content, payload, created_by, generation_job_id, event_type, created_at
                ) values (
                    %s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s::jsonb, %s, %s::uuid, %s, %s
                )
                """,
                (
                    deterministic_uuid(f"message:{index}"),
                    workspace_id,
                    thread_id,
                    1 + (index // len(thread_ids)),
                    "assistant" if index % 2 else "user",
                    f"Message {index}",
                    json.dumps({"seed_index": index, "content": heavy_payload(f"message-{index}", "small")}),
                    user_id,
                    linked_job_id,
                    "job_update" if linked_job_id else None,
                    created_at,
                ),
            )

    return {
        "seed_version": SEED_VERSION,
        "random_seed": RANDOM_SEED,
        "workspace_id": workspace_id,
        "workspace_public_id": "Perf Workspace",
        "user_id": user_id,
        "dataset": dataset,
        "sample_ids": {
            "polling_job_public_id": "job_perf_0000",
            "detail_job_public_id": "job_perf_0001",
            "archive_public_id": "archive_perf_0000",
            "plain_thread_public_id": plain_thread_public_id,
            "linked_thread_public_id": linked_thread_public_id,
            "sync_job_internal_id": job_ids[0],
            "sync_output_internal_id": output_ids[0],
        },
        "small_counts": count_plan("small"),
        "medium_counts": count_plan("medium"),
        "selected_counts": counts,
        "fixture_hash": fixture_hash(dataset),
    }


def run_self_check() -> dict[str, Any]:
    payload = fixture_descriptor("medium")
    assert payload["counts"]["chat_messages"] == 5000
    manifest = {
        "seed_version": SEED_VERSION,
        "random_seed": RANDOM_SEED,
        "fixture_hash": fixture_hash("medium"),
    }
    assert len(manifest["fixture_hash"]) == 16
    return {"status": "ok", "checked": ["counts", "fixture_hash"]}


def main() -> None:
    args = parse_args()
    if args.self_check:
        print(json.dumps(run_self_check(), ensure_ascii=False))
        return
    database_url = database_url_from_env(args.database_url_env)
    output_dir = Path(args.output_dir)
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        truncate_all(conn)
        manifest = insert_seed(conn, args.dataset)
        conn.commit()
    write_json(output_dir / "seed_manifest.json", manifest)
    write_json(OUTPUT_DIR / "seed_manifest.json", manifest)
    print(json.dumps({"status": "ok", "dataset": args.dataset, "fixture_hash": manifest["fixture_hash"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
