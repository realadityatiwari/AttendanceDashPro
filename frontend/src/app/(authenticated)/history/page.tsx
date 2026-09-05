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
  ClassType,
  HistoryStatusFilter,
} from "@/types/api";
import { formatLongDate, formatPct, formatShortDate } from "@/lib/date";
import { Search, Loader2, Calendar, FilterX, Clock } from "lucide-react";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 50;

const STATUS_OPTIONS: { value: HistoryStatusFilter; label: string }[] = [
  { value: "", label: "All states" },
  { value: AttendanceStatus.ATTENDED, label: "Present" },
  { value: AttendanceStatus.MISSED, label: "Absent" },
  { value: AttendanceStatus.PENDING, label: "Pending" },
  { value: "Cancelled", label: "Cancelled" },
];

function StatusBadge({ item }: { item: AttendanceHistoryItem }) {
  if (item.is_cancelled) {
    return <Badge variant="neutral" className="uppercase">Cancelled</Badge>;
  }
  if (item.status === AttendanceStatus.ATTENDED) {
    return <Badge variant="success" className="uppercase">Present</Badge>;
  }
  if (item.status === AttendanceStatus.MISSED) {
    return <Badge variant="danger" className="uppercase">Absent</Badge>;
  }
  return <Badge variant="warning" className="uppercase">Pending</Badge>;
}

function HistoryRow({ item }: { item: AttendanceHistoryItem }) {
  const displayType =
    item.class_type === ClassType.LECTURE ? "LECTURE" :
    item.class_type === ClassType.TUTORIAL ? "TUTORIAL" : "PRACTICAL";
  const timeLabel = item.start_time || (item.is_extra ? "Extra Class" : "TBD");

  return (
    <Card
      className={cn(
        "p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3",
        item.is_cancelled && "opacity-50 grayscale"
      )}
    >
      <div className="flex items-center gap-4 min-w-0">
        <div className="flex flex-col items-center justify-center w-12 h-12 rounded-full bg-muted border border-border shrink-0">
          <span className="text-[11px] uppercase tracking-wider text-muted-foreground">
            {formatShortDate(item.date).split(" ")[1]}
          </span>
          <span className="text-sm font-bold text-foreground leading-none">
            {formatShortDate(item.date).split(" ")[0]}
          </span>
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold text-foreground font-mono text-sm">{item.subject_code}</span>
            <Badge variant="outline" className="text-[11px] leading-none tracking-wider py-0 h-4">
              {displayType}
            </Badge>
            {item.is_extra && (
              <Badge variant="primary" className="text-[11px] leading-none tracking-wider py-0 h-4">
                EXTRA
              </Badge>
            )}
          </div>
          <div className="text-sm text-muted-foreground mt-0.5 truncate max-w-md">
            {item.subject_name}
          </div>
          <div className="text-xs text-muted-foreground mt-1 flex items-center gap-1.5">
            <Clock className="h-3 w-3" />
            {timeLabel}
            {item.marked_at && (
              <span className="text-muted-foreground/70">
                · Logged {new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit" }).format(new Date(item.marked_at))}
              </span>
            )}
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
      ? `${formatLongDate(semesterStart).replace(" · ", " ")} – ${formatLongDate(semesterEnd).replace(" · ", " ")}`
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
            ? `${history.range_start} → ${history.range_end}`
            : "Your complete semester attendance history.")
        }
      />

      {/* Summary */}
      <Card className="p-4 bg-muted border-border flex flex-col gap-3">
        <div className="flex items-baseline justify-between">
          <span className="text-sm font-semibold text-foreground">
            {hasFilters ? "Filtered sessions" : "Semester sessions"}
          </span>
          <span className="text-sm font-bold text-foreground">
            {summary ? `${formatPct(summary.pct)} overall` : "—"}
          </span>
        </div>
        <div className="grid grid-cols-3 sm:grid-cols-5 gap-2">
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
          {hasFilters && (
            <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={resetFilters}>
              <FilterX className="h-3.5 w-3.5 mr-1" />
              Reset
            </Button>
          )}
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2">
          <div className="flex flex-col gap-1">
            <label className="text-[11px] uppercase tracking-wider text-muted-foreground" htmlFor="history-subject">Subject</label>
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
            <label className="text-[11px] uppercase tracking-wider text-muted-foreground" htmlFor="history-status">State</label>
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
            <label className="text-[11px] uppercase tracking-wider text-muted-foreground" htmlFor="history-from">From</label>
            <Input
              id="history-from"
              type="date"
              className="[color-scheme:dark]"
              min={semesterStart ?? undefined}
              max={semesterEnd ?? undefined}
              value={dateFrom}
              onChange={e => setDateFrom(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[11px] uppercase tracking-wider text-muted-foreground" htmlFor="history-to">To</label>
            <Input
              id="history-to"
              type="date"
              className="[color-scheme:dark]"
              min={semesterStart ?? undefined}
              max={semesterEnd ?? undefined}
              value={dateTo}
              onChange={e => setDateTo(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[11px] uppercase tracking-wider text-muted-foreground" htmlFor="history-search">Search</label>
            <div className="relative">
              <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-muted-foreground" />
              <Input
                id="history-search"
                type="search"
                placeholder="Code, name, type, date..."
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
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              ) : null}
              Load more ({history.total_count - rows.length} remaining)
            </Button>
          ) : isLoading ? (
            // history is undefined while a filtered/page request is in
            // flight (SWR gives a fresh key per URL); render a loading row
            // instead of a button that dereferences history.total_count.
            <div className="flex items-center justify-center gap-2 py-3 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading sessions…
            </div>
          ) : null}

          <p className="text-center text-xs text-muted-foreground">
            Showing {rows.length} of {history ? history.total_count : "..."} sessions
          </p>
        </div>
      ) : isLoading || !history ? (
        <div className="space-y-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <Card key={i} className="h-20 animate-pulse bg-muted border-border" />
          ))}
        </div>
      ) : (
        <EmptyState
          title={hasFilters ? "No sessions match your filters" : "No classes scheduled this semester"}
          message={
            hasFilters
              ? "Try adjusting the subject, state, dates, or search query."
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
      <span className="text-[11px] uppercase tracking-wider text-muted-foreground mt-0.5">{label}</span>
    </div>
  );
}