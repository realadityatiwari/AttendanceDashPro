"""Chunk 9 — static guard against stale old-formula UI text.

The pooled L+T model is the canonical attendance/eligibility formula. These
assertions keep the OLD arithmetic-mean wording — "(Lecture % + Tutorial %) / 2"
and its variants — out of CURRENT user-visible frontend text, and require the
pooled wording wherever the formula is explained.

2026-10 remediation (UI test drift): the user-visible pooled wording was
intentionally consolidated (UIA-004) into the single authoritative constant
``POOLED_ATTENDANCE_FORMULA`` in ``frontend/src/lib/formula.ts``, rendered
once per page (Subjects Overview via ``POOLED_ATTENDANCE_EXPLANATION``, Quiz
Schedule via ``POOLED_ATTENDANCE_FORMULA``) instead of being repeated as body
text on every card. The previous all-caps literal expected here per file no
longer exists BY DESIGN — the constant (and the QuizEligibilityCard's
criterion-title documentation of the same pooled model) is the authoritative
wording these tests now pin. The old-mean guard below is unchanged.

Static file-content assertions only (same lightweight style as the repo's
verify_phase_12e static verifier) — no rendering, no framework, no UI behavior
change. The criterion NAME strings ("Lecture + Tutorial Average") emitted by
the backend are presentation identifiers, not formula text, and are not
affected.
"""
from pathlib import Path

FRONTEND_SRC = Path(__file__).resolve().parents[2] / "frontend" / "src"

OLD_FORMULA_PATTERNS = [
    "(Lecture % + Tutorial %) / 2",
    "(Lecture%+Tutorial%)/2",
    "(Lecture % + Tutorial %) /2",
    "(Lecture% + Tutorial%) / 2",
    "(L% + T%) / 2",
    "(L%+T%)/2",
]

# UIA-004: the app's single authoritative phrasing of the pooled formula.
FORMULA_CONSTANT_FILE = "lib/formula.ts"
FORMULA_CONSTANT_NAME = "POOLED_ATTENDANCE_FORMULA"
FORMULA_CONSTANT_EXPECTED = '(lecture + tutorial present) ÷ (lecture + tutorial conducted)'

# Where the constant is rendered / the pooled model is documented.
#   - Quiz Schedule page renders the shared formula constant itself.
#   - Subjects Overview page renders the full pooled explanation sentence,
#     which embeds the same constant (POOLED_ATTENDANCE_EXPLANATION).
FORMULA_RENDER_SITES = {
    "app/(authenticated)/tools/quiz-schedule/page.tsx": "POOLED_ATTENDANCE_FORMULA",
    "app/(authenticated)/subjects/page.tsx": "POOLED_ATTENDANCE_EXPLANATION",
}

FRONTEND_SUFFIXES = {".tsx", ".ts", ".jsx", ".js"}


def _frontend_files():
    return [p for p in FRONTEND_SRC.rglob("*") if p.suffix in FRONTEND_SUFFIXES]


def test_no_current_user_visible_frontend_file_claims_the_arithmetic_mean():
    offenders = []
    for path in _frontend_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in OLD_FORMULA_PATTERNS:
            if pattern in text:
                offenders.append(f"{path.relative_to(FRONTEND_SRC)}: {pattern}")
    assert not offenders, (
        "Stale old-formula text found (the canonical model is the pooled L+T "
        f"formula): {offenders}"
    )


def test_pooled_formula_lives_in_the_single_authoritative_constant():
    # UIA-004: one constant, pooled present-over-conducted phrasing.
    path = FRONTEND_SRC / FORMULA_CONSTANT_FILE
    assert path.exists(), f"authoritative formula constant file missing: {path}"
    text = path.read_text(encoding="utf-8", errors="replace")
    assert FORMULA_CONSTANT_NAME in text, "POOLED_ATTENDANCE_FORMULA is not defined"
    assert FORMULA_CONSTANT_EXPECTED in text, (
        "the authoritative constant no longer states the pooled "
        "present/conducted phrasing"
    )


def test_pooled_formula_is_rendered_on_its_pages():
    for rel, marker in FORMULA_RENDER_SITES.items():
        path = FRONTEND_SRC / rel
        assert path.exists(), f"expected UI file missing: {rel}"
        text = path.read_text(encoding="utf-8", errors="replace")
        assert marker in text, (
            f"{rel} no longer renders the shared pooled formula ({marker})"
        )


def test_quiz_eligibility_card_documents_the_pooled_model():
    # The quiz card maps both criteria to "Attendance Average" and documents
    # the pooled L+T count-level model in its criterion-title comment.
    path = FRONTEND_SRC / "components/quiz/QuizEligibilityCard.tsx"
    assert path.exists(), "QuizEligibilityCard.tsx missing"
    text = path.read_text(encoding="utf-8", errors="replace")
    assert "Lecture Present + Tutorial Present" in text, (
        "QuizEligibilityCard no longer documents the pooled L+T formula"
    )


def test_subject_card_keeps_the_no_tutorial_branch():
    # The lecture-only branch of the subject card (a "No tutorials" block in
    # place of the tutorial sub-block) is unchanged and remains accurate under
    # the pooled model (a missing type contributes nothing).
    caption = (
        FRONTEND_SRC / "components/dashboard/SubjectAttendanceCard.tsx"
    ).read_text(encoding="utf-8", errors="replace")
    assert "No tutorials" in caption
