"""DB-backed system prompt template helpers."""
from __future__ import annotations

from core.db import SessionLocal
from core.models import SystemPromptTemplate
from core.tag_normalization import normalize_tag


def normalize_system_prompt_name(name: str) -> tuple[str, str]:
    """Return ``(slug, display_name)`` for one system prompt template name."""

    normalized = normalize_tag(name)
    return normalized.slug, normalized.display_name


def create_system_prompt_template(
    name: str,
    content: str,
    description: str | None = None,
) -> SystemPromptTemplate:
    """Create an active system prompt template with a normalized unique slug."""

    slug, display_name = normalize_system_prompt_name(name)
    if not slug:
        raise ValueError("System prompt template name cannot be empty.")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("System prompt template content cannot be empty.")

    session = SessionLocal()
    try:
        existing = session.query(SystemPromptTemplate).filter_by(slug=slug).first()
        if existing is not None:
            raise ValueError(f"System prompt template already exists: {display_name}")

        template = SystemPromptTemplate(
            slug=slug,
            name=display_name,
            content=content.strip(),
            description=description.strip() if isinstance(description, str) else None,
            is_active=True,
        )
        session.add(template)
        session.commit()
        session.refresh(template)
        session.expunge(template)
        return template
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_all_system_prompt_templates(
    *,
    active_only: bool = True,
) -> list[SystemPromptTemplate]:
    """Return system prompt templates ordered by display name."""

    session = SessionLocal()
    try:
        query = session.query(SystemPromptTemplate)
        if active_only:
            query = query.filter_by(is_active=True)
        templates = (
            query.order_by(SystemPromptTemplate.name, SystemPromptTemplate.slug)
            .all()
        )
        for template in templates:
            session.expunge(template)
        return templates
    finally:
        session.close()


def get_system_prompt_template_by_slug(slug: str) -> SystemPromptTemplate | None:
    """Return one active system prompt template by normalized slug."""

    normalized_slug, _display_name = normalize_system_prompt_name(slug)
    if not normalized_slug:
        return None

    session = SessionLocal()
    try:
        template = (
            session.query(SystemPromptTemplate)
            .filter_by(slug=normalized_slug, is_active=True)
            .first()
        )
        if template is not None:
            session.expunge(template)
        return template
    finally:
        session.close()


def update_system_prompt_template(
    slug: str,
    *,
    name: str | None = None,
    content: str | None = None,
    description: str | None = None,
) -> SystemPromptTemplate:
    """Update provided template fields without changing the existing slug."""

    normalized_slug, _display_name = normalize_system_prompt_name(slug)
    if not normalized_slug:
        raise ValueError("System prompt template slug cannot be empty.")

    session = SessionLocal()
    try:
        template = (
            session.query(SystemPromptTemplate)
            .filter_by(slug=normalized_slug, is_active=True)
            .first()
        )
        if template is None:
            raise ValueError(f"System prompt template not found: {slug}")

        if name is not None:
            if not isinstance(name, str) or not name.strip():
                raise ValueError("System prompt template name cannot be empty.")
            template.name = name.strip()
        if content is not None:
            if not isinstance(content, str) or not content.strip():
                raise ValueError("System prompt template content cannot be empty.")
            template.content = content.strip()
        if description is not None:
            template.description = description.strip() if description.strip() else None

        session.commit()
        session.refresh(template)
        session.expunge(template)
        return template
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def deactivate_system_prompt_template(slug: str) -> bool:
    """Soft-delete one system prompt template by normalized slug."""

    return bool(delete_system_prompt_templates([slug]))


def reactivate_system_prompt_template(slug: str) -> bool:
    """Reactivate one inactive system prompt template by normalized slug."""

    normalized_slug, _display_name = normalize_system_prompt_name(slug)
    if not normalized_slug:
        return False

    session = SessionLocal()
    try:
        template = (
            session.query(SystemPromptTemplate)
            .filter_by(slug=normalized_slug, is_active=False)
            .first()
        )
        if template is None:
            return False
        template.is_active = True
        session.commit()
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def delete_system_prompt_templates(slugs: list[str]) -> list[str]:
    """Soft-delete active system prompt templates and return normalized slugs."""

    normalized_slugs = {
        normalized_slug
        for slug in slugs
        if (normalized_slug := normalize_system_prompt_name(slug)[0])
    }
    if not normalized_slugs:
        return []

    session = SessionLocal()
    try:
        templates = (
            session.query(SystemPromptTemplate)
            .filter(
                SystemPromptTemplate.slug.in_(normalized_slugs),
                SystemPromptTemplate.is_active.is_(True),
            )
            .all()
        )
        deactivated: list[str] = []
        for template in templates:
            template.is_active = False
            deactivated.append(template.slug)
        session.commit()
        return sorted(deactivated)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
