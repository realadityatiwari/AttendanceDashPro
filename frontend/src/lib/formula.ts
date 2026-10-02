/**
 * UIA-004 — the app's single authoritative phrasing of the pooled attendance
 * formula. It is rendered ONCE per page (Subjects Overview and Quiz
 * Eligibility) instead of being repeated as body text on every card.
 *
 * Presentation only: no calculation lives here. The backend remains the sole
 * source of attendance values; this string exists so the explanation can
 * never drift into three different phrasings across surfaces.
 */
export const POOLED_ATTENDANCE_FORMULA =
  "(lecture + tutorial present) ÷ (lecture + tutorial conducted)";

/** Full sentence form for a page-level caption/description. */
export const POOLED_ATTENDANCE_EXPLANATION =
  `Combined attendance pools both class types: ${POOLED_ATTENDANCE_FORMULA}.`;
