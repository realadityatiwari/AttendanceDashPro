"""Phase 23.11: admin_scopes — authoritative scoped administrative assignments

Revision ID: f9a0b1c2d3e4
Revises: f8a9b0c1d2e3
Create Date: 2026-08-29

Phase 23.11 (API Scope & Authorization) — establishes the backend-authoritative
scoped-admin authorization foundation that the future Admin Portal depends on.

Why a schema change is genuinely required:
  - The current role model is a single ``users.role`` column (STUDENT/ADMIN).
  - There is NO existing structure able to represent scoped administrative
    assignments (CLASS_ADMIN per section, SUBSECTION_ADMIN per subsection,
    ELECTIVE_ADMIN per concrete elective subject) — no equivalent table or
    relationship exists anywhere in the repository.

Changes (additive, non-destructive):
1. New enum type ``adminrole`` (HEAD_ADMIN, CLASS_ADMIN, SUBSECTION_ADMIN,
   ELECTIVE_ADMIN).
2. New table ``admin_scopes``:
     - user_id      FK users.id (NOT NULL, indexed)
     - role         adminrole (NOT NULL)
     - section_id   FK sections.id      (nullable)
     - subsection_id FK subsections.id  (nullable)
     - subject_id   FK subjects.id      (nullable)
     - active       boolean, default TRUE
     - CHECK ``ck_admin_scopes_role_scope``: the scope-target columns must
       match the role (HEAD_ADMIN -> none; CLASS_ADMIN -> section;
       SUBSECTION_ADMIN -> subsection; ELECTIVE_ADMIN -> subject).

Backward compatibility:
  - ``users.role == ADMIN`` is unchanged and resolves as HEAD_ADMIN (global).
  - The existing provisioned ADMIN account keeps full authority.
  - No existing table, row, role, or constraint is modified.
  - Subsection data still does not exist (subsections table empty,
    users.subsection_id NULL) — SUBSECTION_ADMIN scope rows are representable
    but inert until authoritative subsection data exists. Nothing is fabricated.

Downgrade drops the table then the enum type (the CHECK is dropped with the
table; no data is lost beyond the new table's own rows).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ENUM

revision = "f9a0b1c2d3e4"
down_revision = "f8a9b0c1d2e3"
branch_labels = None
depends_on = None

ADMIN_ROLE_ENUM = ENUM(
    "HEAD_ADMIN",
    "CLASS_ADMIN",
    "SUBSECTION_ADMIN",
    "ELECTIVE_ADMIN",
    name="adminrole",
)
ADMIN_ROLE_COL = ENUM(
    "HEAD_ADMIN",
    "CLASS_ADMIN",
    "SUBSECTION_ADMIN",
    "ELECTIVE_ADMIN",
    name="adminrole",
    create_type=False,
)


def upgrade() -> None:
    ADMIN_ROLE_ENUM.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "admin_scopes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True,
                  server_default=sa.func.now()),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role", ADMIN_ROLE_COL, nullable=False),
        sa.Column("section_id", sa.UUID(), nullable=True),
        sa.Column("subsection_id", sa.UUID(), nullable=True),
        sa.Column("subject_id", sa.UUID(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_admin_scope_user"),
        sa.ForeignKeyConstraint(["section_id"], ["sections.id"], name="fk_admin_scope_section"),
        sa.ForeignKeyConstraint(["subsection_id"], ["subsections.id"], name="fk_admin_scope_subsection"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], name="fk_admin_scope_subject"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "CASE role "
            "  WHEN 'HEAD_ADMIN' THEN "
            "    section_id IS NULL AND subsection_id IS NULL AND subject_id IS NULL "
            "  WHEN 'CLASS_ADMIN' THEN "
            "    section_id IS NOT NULL AND subsection_id IS NULL AND subject_id IS NULL "
            "  WHEN 'SUBSECTION_ADMIN' THEN "
            "    subsection_id IS NOT NULL AND section_id IS NULL AND subject_id IS NULL "
            "  WHEN 'ELECTIVE_ADMIN' THEN "
            "    subject_id IS NOT NULL AND section_id IS NULL AND subsection_id IS NULL "
            "END",
            name="ck_admin_scopes_role_scope",
        ),
    )
    op.create_index("ix_admin_scopes_user_id", "admin_scopes", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_admin_scopes_user_id", table_name="admin_scopes")
    op.drop_table("admin_scopes")
    ADMIN_ROLE_ENUM.drop(op.get_bind(), checkfirst=True)
