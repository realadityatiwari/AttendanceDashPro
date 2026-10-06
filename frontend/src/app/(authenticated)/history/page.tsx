"use client";

import { useEffect, useMemo, useState } from "react";
import { useAttendanceHistory, useSubjects, useProfile } from "@/hooks/useApi";
import { PageHeader } from "@/components/shared/PageHeader";
import { ErrorState } from "@/components/shared/ErrorState";
import { EmptyState } from "@/components/shared/EmptyState";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import {
  AttendanceHistoryItem,
  AttendanceHistoryParams,
  AttendanceStatus,
  HistoryStatusFilter,
} from "@/types/api";
import { formatDateParts, formatDateRange, formatTime } from "@/lib/date";
import { classTypeLabel, getSessionStatus, SESSION_STATUS } from "@/lib/canonicalStatus";
import { RecordedPct } from "@/components/shared/RecordedPct";
import { DateInput } from "@/components/shared/DateInput";
import { Skeleton } from "@/components/ui/skeleton";
import { Search, Loader2, Calendar, FilterX, Clock } from "lucide-react";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 50;

// Filter values are backend contract values; labels come from the canonical
// session vocabulary (25.UX-1) so filter copy can never drift from badges.
const STATUS_OPTIONS: { value: HistoryStatusFilter; label: string }[] = [
  { value: "", label: "All statuses" },
  { value: AttendanceStatus.ATTENDED, label: SESSION_STATUS.PRESENT.label },
  { value: AttendanceStatus.MISSED, label: SESSION_STATUS.ABSENT.label },
  { value: AttendanceStatus.PENDING, label: SESSION_STATUS.PENDING.label },
  { value: "Cancelled", label: SESSION_STATUS.CANCELLED.label },
];

function StatusBadge({ item }: { item: AttendanceHistoryItem }) {
  // Canonical 4-state session vocabulary (Present/Absent/Pending/Cancelled);
  // is_cancelled wins per the canonical normalization order.
  const status = getSessionStatus(item.status, item.is_cancelled);
  return <Badge variant={status.variant} className="uppercase">{status.label}</Badge>;
}

function HistoryRow({ item }: { item: AttendanceHistoryItem }) {
  // 25.UX-3: the class-type label flows from the canonical vocabulary and is
  // uppercased via CSS (the badge treatment) — no local map.
  const displayType = classTypeLabel(item.class_type) ?? "Practical";
  // Canonical 24h "HH:MM" time display; the Extra Class / TBD fallbacks are
  // preserved verbatim.
  const timeLabel = item.start_time
    ? formatTime(item.start_time)
    : item.is_extra
      ? "Extra Class"
      : "TBD";

  return (
    <Card
      className={cn(
        "p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3",
        item.is_cancelled && "opacity-50 grayscale"
      )}
    >
      <div className="flex items-center gap-4 min-w-0">
        <div className="flex flex-col items-center justify-center w-12 h-12 rounded-full bg-muted border border-border shrink-0">
          <span className="text-2xs uppercase tracking-wider text-muted-foreground">
            {formatDateParts(item.date).month}
          </span>
          <span className="text-sm font-bold text-foreground leading-none">
            {formatDateParts(item.date).day}
          </span>
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold text-foreground font-mono text-sm">{item.subject_code}</span>
            <Badge variant="outline" size="xs" className="uppercase tracking-wider">
              {displayType}
            </Badge>
            {item.is_extra && (
              <Badge variant="primary" size="xs" className="tracking-wider">
                EXTRA
              </Badge>
            )}
          </div>
          {/* 25.UX-6: the row is one line-tall at desktop, so the subject name
              stays a truncate (title fallback) there — but inside a flexible
              min-w-0 box so the fluid column itself can grow to the row edge
              without horizontal overflow, and wraps on mobile where a row is
              naturally multi-line. */}
          <div className="text-sm text-muted-foreground mt-0.5 max-w-full sm:max-w-md sm:truncate min-w-0" title={item.subject_name}>
            {item.subject_name}
          </div>
          {/* UIA-026: the record-creation timestamp ("Logged 2:09 AM") was
              internal operational metadata that invited misreading as the
              class time. Only the session time remains. */}
          <div className="text-xs text-muted-foreground mt-1 flex items-center gap-1.5">
            <Clock className="h-3 w-3" aria-hidden="true" />
            {timeLabel}
          </div>
        </div>
      </div>
      <div className="sm:text-right shrink-0">
        <StatusBadge item={item} />
      </div>
    </Card>
  );
}

export default function HistoryPage() {
  const { profile } = useProfile();
  const { subjects } = useSubjects();

  const [subject, setSubject] = useState("");
  const [status, setStatus] = useState<HistoryStatusFilter>("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [offset, setOffset] = useState(0);

  // Debounce the search input before it becomes part of the query.
  useEffect(() => {
    const timer = setTimeout(() => setAppliedSearch(searchInput.trim()), 400);
    return () => clearTimeout(timer);
  }, [searchInput]);

  const params: AttendanceHistoryParams = useMemo(
    () => ({
      subject_code: subject || undefined,
      status: status || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      search: appliedSearch || undefined,
      limit: PAGE_SIZE,
      offset,
    }),
    [subject, status, dateFrom, dateTo, appliedSearch, offset]
  );

  const { history, isLoading, isError, mutate } = useAttendanceHistory(params);

  // Accumulate pages locally; reset whenever any filter changes.
  const filterSig = [subject, status, dateFrom, dateTo, appliedSearch].join("|");
  const [rows, setRows] = useState<AttendanceHistoryItem[]>([]);
  const [lastSig, setLastSig] = useState(filterSig);

  useEffect(() => {
    if (lastSig !== filterSig) {
      setLastSig(filterSig);
      setOffset(0);
      // Drop rows from the previous filter immediately so stale items are
      // never shown (or mixed into the new result) while the filtered
      // request loads — the skeleton renders instead.
      setRows([]);
    }
  }, [filterSig, lastSig]);

  useEffect(() => {
    if (!history) return;
    if (offset === 0) {
      setRows(history.items);
      return;
    }
    setRows(prev => {
      const seen = new Set(prev.map(r => r.id));
      const fresh = history.items.filter(r => !seen.has(r.id));
      return [...prev, ...fresh];
    });
  }, [history, offset]);

  const hasFilters = Boolean(subject || status || dateFrom || dateTo || appliedSearch);
  const semesterStart = history?.semester_start ?? profile?.semester_start ?? null;
  const semesterEnd = history?.semester_end ?? profile?.semester_end ?? null;

  const resetFilters = () => {
    setSubject("");
    setStatus("");
    setDateFrom("");
    setDateTo("");
    setSearchInput("");
    setAppliedSearch("");
  };

  const contextLine = [
    profile?.semester_name,
    semesterStart && semesterEnd
      ? formatDateRange(semesterStart, semesterEnd)
      : null,
  ]
    .filter(Boolean)
    .join(" · ");

  const summary = history?.summary;

  return (
    <div className="flex-1 py-6 w-full flex flex-col gap-6">
      <PageHeader
        title="Attendance History"
        description={
          contextLine ||
          (history?.range_start && history?.range_end
            ? formatDateRange(history.range_start, history.range_end)
            : "Your complete semester attendance history.")
        }
      />

      {/* Summary */}
      <Card className="p-4 bg-muted border-border flex flex-col gap-3">
        <div className="flex items-baseline justify-between gap-3">
          <span className="text-sm font-semibold text-foreground">
            {hasFilters ? "Filtered sessions" : "Semester sessions"}
          </span>
          {/* UIA-001: the recorded-only percentage carries its basis — a
              semester with 280 pending sessions must never read as "83%
              overall" when the figure is 5 of 6 recorded. */}
          {summary ? (
            <RecordedPct
              value={summary.pct}
              valueClassName="text-sm font-bold text-foreground"
              suffixClassName="text-xs font-medium text-muted-foreground"
            />
          ) : (
            <span className="text-sm font-bold text-foreground">—</span>
          )}
        </div>
        {summary && summary.attended + summary.missed === 0 && (
          <p className="text-xs text-muted-foreground">
            No sessions recorded yet — mark classes to build your history.
          </p>
        )}
        {/* 25.UX-6: the stat strip matches the dashboard QuizSnapshotCard's
            2-col mobile grid (grid-cols-2 sm:grid-cols-5) — the former
            3-col mobile layout stacked 3 stats over a ragged 2 when five
            aggregates shared one row. Desktop is unchanged. */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
          <SummaryStat label="Total" value={summary?.total} className="text-foreground" />
          <SummaryStat label="Present" value={summary?.attended} className="text-success" />
          <SummaryStat label="Absent" value={summary?.missed} className="text-destructive" />
          <SummaryStat label="Pending" value={summary?.pending} className="text-warning" />
          <SummaryStat label="Cancelled" value={summary?.cancelled} className="text-muted-foreground" />
        </div>
      </Card>

      {/* Filters */}
      <Card className="p-4 border-border flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Filters
          </span>
          {/* UIA-030: the per-component sm:h-7 override is removed — the
              shared button size now enforces the 40px touch / 32px pointer
              floor. */}
          {hasFilters && (
            <Button variant="ghost" size="sm" className="text-xs" onClick={resetFilters}>
              <FilterX className="h-3.5 w-3.5 mr-1" aria-hidden="true" />
              Reset
            </Button>
          )}
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2">
          <div className="flex flex-col gap-1">
            <label className="text-2xs uppercase tracking-wider text-muted-foreground" htmlFor="history-subject">Subject</label>
            <Select
              id="history-subject"
              value={subject}
              onChange={e => setSubject(e.target.value)}
            >
              <option value="">All subjects</option>
              {(subjects ?? []).map(s => (
                <option key={s.id} value={s.code}>{s.code} · {s.name}</option>
              ))}
            </Select>
          </div>
          <div className="flex flex-col gap-1">
            {/* UIA-027: the filter group is "Status" — the same user-facing
                vocabulary the status badges use. */}
            <label className="text-2xs uppercase tracking-wider text-muted-foreground" htmlFor="history-status">Status</label>
            <Select
              id="history-status"
              value={status}
              onChange={e => setStatus(e.target.value as HistoryStatusFilter)}
            >
              {STATUS_OPTIONS.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </Select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-2xs uppercase tracking-wider text-muted-foreground" htmlFor="history-from">From</label>
            {/* UIA-025: native date input + visible formatted companion. */}
            <DateInput
              id="history-from"
              min={semesterStart ?? undefined}
              max={semesterEnd ?? undefined}
              value={dateFrom}
              onValueChange={setDateFrom}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-2xs uppercase tracking-wider text-muted-foreground" htmlFor="history-to">To</label>
            <DateInput
              id="history-to"
              min={semesterStart ?? undefined}
              max={semesterEnd ?? undefined}
              value={dateTo}
              onValueChange={setDateTo}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-2xs uppercase tracking-wider text-muted-foreground" htmlFor="history-search">Search</label>
            <div className="relative">
              <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
              <Input
                id="history-search"
                type="search"
                // UIA-034: short enough to render fully in the narrow filter
                // column (the long field list used to clip mid-word).
                placeholder="e.g. BCS-501"
                className="pl-8"
                value={searchInput}
                onChange={e => setSearchInput(e.target.value)}
              />
            </div>
          </div>
        </div>
      </Card>

      {/* Results */}
      {isError ? (
        <ErrorState
          message="Could not load your attendance history. Check your connection and try again."
          onRetry={() => mutate()}
        />
      ) : rows.length > 0 ? (
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-4">
            {rows.map(item => (
              <HistoryRow key={item.id} item={item} />
            ))}
          </div>

          {history && rows.length < history.total_count ? (
            <Button
              variant="outline"
              className="w-full"
              disabled={isLoading}
              onClick={() => setOffset(prev => prev + PAGE_SIZE)}
            >
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin mr-2" aria-hidden="true" />
              ) : null}
              Load more ({history.total_count - rows.length} remaining)
            </Button>
          ) : isLoading ? (
            // history is undefined while a filtered/page request is in
            // flight (SWR gives a fresh key per URL); render a loading row
            // instead of a button that dereferences history.total_count.
            <div className="flex items-center justify-center gap-2 py-3 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              Loading sessions…
            </div>
          ) : null}

          <p className="text-center text-xs text-muted-foreground">
            Showing {rows.length} of {history ? history.total_count : "..."} sessions
          </p>
        </div>
      ) : isLoading || !history ? (
        <div className="space-y-4" aria-hidden="true">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-20 rounded-xl" />
          ))}
        </div>
      ) : (
        <EmptyState
          title={hasFilters ? "No sessions match your filters" : "No classes scheduled this semester"}
          message={
            hasFilters
              ? "Try adjusting the subject, status, dates, or search query."
              : "There are no scheduled sessions in your current semester range."
          }
          icon={<Calendar className="h-10 w-10 text-muted-foreground mb-4" />}
        />
      )}
    </div>
  );
}

function SummaryStat({ label, value, className }: { label: string; value: number | undefined; className?: string }) {
  return (
    <div className="flex flex-col items-center rounded-lg border border-border bg-background px-2 py-2">
      <span className={cn("text-xl font-bold tracking-tight", className)}>
        {value ?? "—"}
      </span>
      <span className="text-2xs uppercase tracking-wider text-muted-foreground mt-0.5">{label}</span>
    </div>
  );
}