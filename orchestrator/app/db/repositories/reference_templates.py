"""Reference template repository."""

from __future__ import annotations

from orchestrator.app.db.json import jsonb_param
from orchestrator.app.db.session import db_transaction


REFERENCE_TEMPLATE_COLUMNS = """
id, template_id, title, description, category, sub_category, tags,
business_types, ad_formats, platforms, aspect_ratio, width, height,
asset_public_id, thumbnail_url, preview_url, source_image_path,
style_keywords, color_palette, layout_hint, typography_hint,
background_style, popularity_score, status, source, license_note,
metadata, created_by, created_at, updated_at
"""


def list_reference_templates(*, active_only: bool = False, connection: object | None = None) -> list[dict]:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            query = f"select {REFERENCE_TEMPLATE_COLUMNS} from reference_templates where deleted_at is null"
            params: list[object] = []
            if active_only:
                query += " and status = %s"
                params.append("active")
            query += " order by created_at desc"
            cur.execute(query, tuple(params))
            return list(cur.fetchall() or [])


def get_reference_template(template_id: str, *, connection: object | None = None) -> dict | None:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                select {REFERENCE_TEMPLATE_COLUMNS}
                from reference_templates
                where template_id = %s and deleted_at is null
                """,
                (template_id,),
            )
            return cur.fetchone()


def create_reference_template(data: dict, *, connection: object | None = None) -> dict:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into reference_templates (
                  template_id, title, description, category, sub_category,
                  tags, business_types, ad_formats, platforms, aspect_ratio,
                  width, height, asset_public_id, thumbnail_url, preview_url,
                  source_image_path, style_keywords, color_palette, layout_hint,
                  typography_hint, background_style, popularity_score, status,
                  source, license_note, metadata, created_by
                )
                values (
                  %(template_id)s, %(title)s, %(description)s, %(category)s, %(sub_category)s,
                  %(tags)s, %(business_types)s, %(ad_formats)s, %(platforms)s, %(aspect_ratio)s,
                  %(width)s, %(height)s, %(asset_public_id)s, %(thumbnail_url)s, %(preview_url)s,
                  %(source_image_path)s, %(style_keywords)s, %(color_palette)s, %(layout_hint)s,
                  %(typography_hint)s, %(background_style)s, %(popularity_score)s, %(status)s,
                  %(source)s, %(license_note)s, %(metadata)s::jsonb, %(created_by)s
                )
                returning *
                """,
                {
                    **data,
                    "metadata": jsonb_param(data.get("metadata") or {}),
                },
            )
            return cur.fetchone()


def update_reference_template(template_id: str, data: dict, *, connection: object | None = None) -> dict | None:
    allowed = {
        "title",
        "description",
        "category",
        "sub_category",
        "tags",
        "business_types",
        "ad_formats",
        "platforms",
        "aspect_ratio",
        "style_keywords",
        "color_palette",
        "layout_hint",
        "typography_hint",
        "background_style",
        "popularity_score",
        "status",
        "license_note",
        "metadata",
    }
    updates = {key: value for key, value in data.items() if key in allowed}
    if not updates:
        return get_reference_template(template_id, connection=connection)

    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            assignments = ["updated_at = now()"]
            params: list[object] = []
            for key, value in updates.items():
                if key == "metadata":
                    assignments.append("metadata = coalesce(metadata, '{}'::jsonb) || %s::jsonb")
                    params.append(jsonb_param(value or {}))
                else:
                    assignments.append(f"{key} = %s")
                    params.append(value)
            params.append(template_id)
            cur.execute(
                f"""
                update reference_templates
                set {", ".join(assignments)}
                where template_id = %s and deleted_at is null
                returning *
                """,
                tuple(params),
            )
            return cur.fetchone()
