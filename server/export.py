"""Safe Markdown and frontmatter exporter for Whis2ndBrain notes."""

from __future__ import annotations

from pathlib import Path

import yaml

from contracts.schemas import ExportFrontmatter
from server.pass1 import VAULT_ROOT, Conflict, Note, Receipt, Rejected, _write_durable


def refuse_vault_destination(dest: Path, forbidden: Path = VAULT_ROOT) -> None:
    """Ensure destination is never the live vault or any directory inside it."""
    root = forbidden.resolve()
    target = dest.resolve()
    if target == root or root in target.parents:
        raise Rejected("export destination is inside the vault")


def build_markdown_body(note: Note, receipt: Receipt) -> str:
    """Generate Markdown content with formal YAML frontmatter."""
    fm = ExportFrontmatter(
        capture_id=note.capture_id,
        sha256=receipt.sha256,
        transcript_source=note.transcript_source or "none",
        review_state=note.status,
        category=getattr(note, "category", None),
        urgency=getattr(note, "urgency", None),
        actionable=getattr(note, "actionable", None),
        received_at=note.received_at,
    )
    frontmatter_yaml = yaml.safe_dump(fm.to_dict(), sort_keys=False).strip()
    return f"---\n{frontmatter_yaml}\n---\n\n{note.transcript or ''}\n"


def export_note_to_dir(
    note: Note, receipt: Receipt, dest_dir: Path, forbidden: Path = VAULT_ROOT
) -> Path:
    """Safely export a note to a designated directory outside the vault."""
    dest_path = Path(dest_dir)
    refuse_vault_destination(dest_path, forbidden)
    dest_path.mkdir(parents=True, exist_ok=True)

    file_path = dest_path / f"{note.capture_id}.md"
    body = build_markdown_body(note, receipt)

    if file_path.exists():
        if file_path.read_text(encoding="utf-8") == body:
            return file_path
        raise Conflict(note.capture_id)

    _write_durable(file_path, body.encode("utf-8"))
    return file_path
