"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAdminScopeMutations, useAdminSubjects, useAdminSections, useAdminSessions, useAdminSemesters } from "@/hooks/useApi";
import { AdminUserSummary, AdminRole, AssignScopeRequest } from "@/types/api";

const selectClass =
  "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50";

/**
 * Assign a scope to an admin user. HEAD_ADMIN scope rows are never created
 * (HEAD authority comes from the legacy users.role). The backend enforces
 * the scope-role CHECK constraint and duplicate protection.
 */
export function AssignScopeDialog({
  user, onClose,
}: {
  user: AdminUserSummary;
  onClose: () => void;
}) {
  const { sessions } = useAdminSessions();
  const [sessionId, setSessionId] = useState("");
  const { semesters } = useAdminSemesters(sessionId || null);
  const [semesterId, setSemesterId] = useState("");
  const { sections } = useAdminSections(semesterId || null);
  const { subjects } = useAdminSubjects();
  const { assignScope } = useAdminScopeMutations();

  const [role, setRole] = useState<AdminRole>(AdminRole.CLASS_ADMIN);
  const [sectionId, setSectionId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const filteredSubjects = (subjects?.items ?? []).filter((s) => !semesterId || s.semester_id === semesterId);

  const handleSubmit = async () => {
    if (role === AdminRole.CLASS_ADMIN && !sectionId) { setError("A section is required for CLASS_ADMIN"); return; }
    if (role === AdminRole.ELECTIVE_ADMIN && !subjectId) { setError("A subject is required for ELECTIVE_ADMIN"); return; }
    setError(null); setSuccess(false);
    setBusy(true);
    try {
      const payload: AssignScopeRequest = { role };
      if (role === AdminRole.CLASS_ADMIN) payload.section_id = sectionId;
      if (role === AdminRole.ELECTIVE_ADMIN) payload.subject_id = subjectId;
      await assignScope(user.id, payload);
      setSuccess(true);
      setTimeout(onClose, 1200);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to assign scope");
    } finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4" onClick={onClose}>
      <div className="max-w-md w-full rounded-lg bg-background p-6 shadow-lg" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-semibold">Assign Scope</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Target: <strong>{user.display_name}</strong> ({user.roll_number ?? "—"})
        </p>
        {error && <p className="mt-2 text-sm text-destructive">{error}</p>}
        {success && <p className="mt-2 text-sm text-green-500">Scope assigned successfully.</p>}
        <div className="mt-4 space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Role</label>
            <select className={selectClass} value={role} onChange={(e) => setRole(e.target.value as AdminRole)}>
              <option value={AdminRole.CLASS_ADMIN}>Class Admin</option>
              <option value={AdminRole.ELECTIVE_ADMIN}>Elective Admin</option>
            </select>
            <p className="text-xs text-muted-foreground">
              HEAD_ADMIN is granted via the legacy admin role; SUBSECTION_ADMIN is structurally inert (no subsections data).
            </p>
          </div>

          {role === AdminRole.CLASS_ADMIN && (
            <>
              <div className="space-y-2">
                <label className="text-sm font-medium">Session</label>
                <select className={selectClass} value={sessionId} onChange={(e) => { setSessionId(e.target.value); setSemesterId(""); }}>
                  <option value="">Select a session</option>
                  {(sessions ?? []).map((s) => (
                    <option key={s.id} value={s.id}>{s.name}{s.is_active ? " (active)" : ""}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Semester</label>
                <select className={selectClass} value={semesterId} onChange={(e) => setSemesterId(e.target.value)} disabled={!sessionId}>
                  <option value="">Select a semester</option>
                  {(semesters ?? []).map((s) => (<option key={s.id} value={s.id}>{s.name}</option>))}
                </select>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Section</label>
                <select className={selectClass} value={sectionId} onChange={(e) => setSectionId(e.target.value)} disabled={!semesterId}>
                  <option value="">Select a section</option>
                  {(sections ?? []).map((s) => (<option key={s.id} value={s.id}>{s.name}</option>))}
                </select>
              </div>
            </>
          )}

          {role === AdminRole.ELECTIVE_ADMIN && (
            <div className="space-y-2">
              <label className="text-sm font-medium">Subject</label>
              <select className={selectClass} value={subjectId} onChange={(e) => setSubjectId(e.target.value)}>
                <option value="">Select a subject</option>
                {filteredSubjects.map((s) => (
                  <option key={s.id} value={s.id}>{s.code} — {s.name}</option>
                ))}
              </select>
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={onClose} disabled={busy}>Cancel</Button>
            <Button onClick={handleSubmit} disabled={busy}>
              {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Assign
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}