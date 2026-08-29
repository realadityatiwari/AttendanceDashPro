"use client";

import { useState, use } from "react";
import Link from "next/link";
import { 
  BookOpen, 
  ChevronRight,
  Loader2,
  FolderTree,
  Plus,
  AlertTriangle
} from "lucide-react";
import { format } from "date-fns";

import { 
  useAdminSessions, 
  useAdminSemesters,
  useAdminSections,
  useAdminSubsectionsStructure,
  useAdminStructureMutations 
} from "@/hooks/useApi";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { 
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";

// Simple un-optimized tree view for Phase 24.5.
// In a real production app we'd paginate/virtualize this, but it meets the requirement.
export default function SessionHierarchyPage({ params }: { params: Promise<{ session_id: string }> }) {
  const resolvedParams = use(params);
  const sessionId = resolvedParams.session_id;

  const { sessions, isLoading: sessionsLoading } = useAdminSessions();
  const session = sessions?.find(s => s.id === sessionId);

  const { semesters, isLoading: semLoading, mutate: mutateSem } = useAdminSemesters(sessionId);
  const mutations = useAdminStructureMutations();

  // Create state
  const [createType, setCreateType] = useState<"semester" | "section" | "subsection" | null>(null);
  const [createParentId, setCreateParentId] = useState<string>("");
  const [createName, setCreateName] = useState("");
  const [createStart, setCreateStart] = useState("");
  const [createEnd, setCreateEnd] = useState("");
  const [createProgram, setCreateProgram] = useState("");
  const [createMaxStrength, setCreateMaxStrength] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  const handleCreateOpen = (type: "semester" | "section" | "subsection", parentId: string) => {
    setCreateType(type);
    setCreateParentId(parentId);
    setCreateName("");
    setCreateStart("");
    setCreateEnd("");
    setCreateProgram("");
    setCreateMaxStrength("");
    setError("");
  };

  const handleCreateSubmit = async () => {
    try {
      setError("");
      setIsSubmitting(true);
      if (!createName.trim()) throw new Error("Name is required");

      if (createType === "semester") {
        if (!createStart || !createEnd) throw new Error("Dates are required for semester");
        const res = await mutations.createSemester(sessionId, {
          name: createName,
          start_date: createStart,
          end_date: createEnd
        });
        if (res.warnings && res.warnings.length > 0) {
          alert("Registration Warning:\n" + res.warnings.map(w => w.message).join("\n"));
        }
        await mutateSem();
      } else if (createType === "section") {
        const res = await mutations.createSection(createParentId, {
          name: createName,
          program: createProgram || null
        });
        if (res.warnings && res.warnings.length > 0) {
          alert("Registration Warning:\n" + res.warnings.map(w => w.message).join("\n"));
        }
        // Normally we'd mutate specifically the sections hook.
        // For simplicity since the hierarchy doesn't deep refetch in this simplified view
        // we trigger a full reload to get fresh data (in production we'd use SWR bounded mutations)
        window.location.reload();
      } else if (createType === "subsection") {
        await mutations.createSubsection(createParentId, {
          name: createName,
          max_strength: createMaxStrength ? parseInt(createMaxStrength, 10) : null
        });
        window.location.reload();
      }
      setCreateType(null);
    } catch (err: any) {
      setError(err.message || "Failed to create");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (sessionsLoading || semLoading) {
    return (
      <div className="p-20 flex justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!session) {
    return <div className="p-10 text-center text-muted-foreground">Session not found.</div>;
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-10">
      {/* Breadcrumbs */}
      <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
        <Link href="/admin/structure" className="hover:text-foreground transition-colors">
          Structure
        </Link>
        <ChevronRight className="h-4 w-4" />
        <span className="text-foreground font-medium">{session.name}</span>
      </div>

      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <FolderTree className="h-6 w-6 text-primary" />
            {session.name} Hierarchy
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {format(new Date(session.start_date), 'MMM d, yyyy')} - {format(new Date(session.end_date), 'MMM d, yyyy')}
          </p>
        </div>
        <Button onClick={() => handleCreateOpen("semester", sessionId)} className="gap-2">
          <Plus className="h-4 w-4" />
          Add Semester
        </Button>
      </div>

      {!semesters || semesters.length === 0 ? (
        <GlassCard className="p-10 text-center text-muted-foreground">
          <FolderTree className="h-10 w-10 mx-auto mb-3 opacity-20" />
          <p>This session has no semesters yet.</p>
        </GlassCard>
      ) : (
        <div className="space-y-6">
          {semesters.map(sem => (
            <SemesterBlock 
              key={sem.id} 
              semester={sem} 
              onCreateSection={(semId) => handleCreateOpen("section", semId)}
              onCreateSubsection={(secId) => handleCreateOpen("subsection", secId)}
            />
          ))}
        </div>
      )}

      {/* Creation Dialog */}
      <Dialog open={createType !== null} onOpenChange={(open) => !open && setCreateType(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {createType === "semester" ? "Add Semester" : 
               createType === "section" ? "Add Section" : "Add Subsection"}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Name</label>
              <Input 
                placeholder="e.g. Sem 1" 
                value={createName}
                onChange={e => setCreateName(e.target.value)}
              />
            </div>
            {createType === "semester" && (
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Start Date</label>
                  <Input type="date" value={createStart} onChange={e => setCreateStart(e.target.value)} />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">End Date</label>
                  <Input type="date" value={createEnd} onChange={e => setCreateEnd(e.target.value)} />
                </div>
              </div>
            )}
            {createType === "section" && (
              <div className="space-y-2">
                <label className="text-sm font-medium">Program (Optional)</label>
                <Input placeholder="e.g. BTech CSE" value={createProgram} onChange={e => setCreateProgram(e.target.value)} />
              </div>
            )}
            {createType === "subsection" && (
              <div className="space-y-2">
                <label className="text-sm font-medium">Max Strength (Optional)</label>
                <Input type="number" placeholder="e.g. 30" value={createMaxStrength} onChange={e => setCreateMaxStrength(e.target.value)} />
              </div>
            )}
            {error && (
              <div className="p-3 bg-destructive/10 text-destructive text-sm rounded-md flex items-start gap-2">
                <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                <p>{error}</p>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateType(null)} disabled={isSubmitting}>Cancel</Button>
            <Button onClick={handleCreateSubmit} disabled={isSubmitting}>
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function SemesterBlock({ 
  semester, 
  onCreateSection,
  onCreateSubsection
}: { 
  semester: any,
  onCreateSection: (id: string) => void,
  onCreateSubsection: (id: string) => void
}) {
  const { sections, isLoading } = useAdminSections(semester.id);

  return (
    <GlassCard className="overflow-hidden">
      <div className="bg-muted/30 border-b border-border p-4 flex items-center justify-between">
        <div>
          <h3 className="font-semibold">{semester.name}</h3>
          <p className="text-xs text-muted-foreground mt-1">
            {format(new Date(semester.start_date), 'MMM d')} - {format(new Date(semester.end_date), 'MMM d, yyyy')}
          </p>
        </div>
        <Button variant="outline" size="sm" className="gap-2" onClick={() => onCreateSection(semester.id)}>
          <Plus className="h-3 w-3" /> Section
        </Button>
      </div>
      <div className="p-4">
        {isLoading ? (
          <div className="flex justify-center py-4"><Loader2 className="h-5 w-5 animate-spin text-muted-foreground" /></div>
        ) : !sections || sections.length === 0 ? (
          <p className="text-sm text-muted-foreground py-4 text-center">No sections in this semester.</p>
        ) : (
          <div className="space-y-4">
            {sections.map(section => (
              <SectionBlock 
                key={section.id} 
                section={section} 
                onCreateSubsection={() => onCreateSubsection(section.id)}
              />
            ))}
          </div>
        )}
      </div>
    </GlassCard>
  );
}

function SectionBlock({ section, onCreateSubsection }: { section: any, onCreateSubsection: () => void }) {
  const { subsections, isLoading } = useAdminSubsectionsStructure(section.id);

  return (
    <div className="border border-border rounded-md overflow-hidden">
      <div className="bg-background p-3 flex items-center justify-between border-b border-border">
        <div className="flex items-center gap-3">
          <Badge variant="neutral">{section.name}</Badge>
          {section.program && <span className="text-xs text-muted-foreground">{section.program}</span>}
          <span className="text-xs text-muted-foreground">({section.student_count} students)</span>
        </div>
        <Button variant="ghost" size="sm" className="h-7 text-xs gap-1" onClick={onCreateSubsection}>
          <Plus className="h-3 w-3" /> Sub
        </Button>
      </div>
      <div className="bg-muted/10 p-3">
        {isLoading ? (
          <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
        ) : !subsections || subsections.length === 0 ? (
          <p className="text-xs text-muted-foreground">No subsections.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {subsections.map(sub => (
              <Badge key={sub.id} variant="outline" className="bg-background text-xs font-normal">
                {sub.name} 
                <span className="ml-1 text-muted-foreground">
                  ({sub.student_count}{sub.max_strength ? `/${sub.max_strength}` : ''})
                </span>
              </Badge>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
