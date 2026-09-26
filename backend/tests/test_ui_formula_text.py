"""Chunk 9 — static guard against stale old-formula UI text.

The pooled L+T model is the canonical attendance/eligibility formula. These
assertions keep the OLD arithmetic-mean wording — "(Lecture % + Tutorial %) / 2"
and its variants — out of CURRENT user-visible frontend text, and require the
pooled wording wherever the formula is explained.

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

POOLED_FORMULA_TEXT = "(Lecture Present + Tutorial Present) / (Lecture Conducted + Tutorial Conducted)"

# The three Chunk-9 corrected user-visible explanations.
EXPECTED_POOLED_FILES = [
    "components/quiz/QuizEligibilityCard.tsx",
    "components/dashboard/SubjectAttendanceCard.tsx",
    "app/(authenticated)/tools/quiz-schedule/page.tsx",
]

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


def test_corrected_formula_explanations_use_the_pooled_wording():
    for rel in EXPECTED_POOLED_FILES:
        path = FRONTEND_SRC / rel
        assert path.exists(), f"expected UI file missing: {rel}"
        assert POOLED_FORMULA_TEXT in path.read_text(encoding="utf-8", errors="replace"), (
            f"{rel} no longer explains the pooled L+T formula"
        )


def test_forecast_caption_still_states_the_no_tutorial_collapse():
    # The lecture-only branch of the subject card caption is unchanged and
    # remains accurate under the pooled model.
    caption = (
        FRONTEND_SRC / "components/dashboard/SubjectAttendanceCard.tsx"
    ).read_text(encoding="utf-8", errors="replace")
    assert "No tutorials — subject average equals Lecture %" in caption
