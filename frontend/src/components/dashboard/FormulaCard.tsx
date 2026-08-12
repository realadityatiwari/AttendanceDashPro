import { useState } from "react";
import { ChevronDown, ChevronUp, Sigma } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

export function FormulaCard() {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <Card className="bg-surface/50 border-border/50 backdrop-blur-sm overflow-hidden mb-6">
      <div 
        className="flex items-center justify-between p-4 cursor-pointer hover:bg-surface/80 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
        role="button"
        aria-expanded={isExpanded}
      >
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-full bg-accent/10 flex items-center justify-center text-accent">
            <Sigma size={16} />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-foreground">Eligibility Formula</h3>
            <p className="text-xs text-muted-foreground hidden sm:block">Tap to {isExpanded ? "collapse" : "expand"}</p>
          </div>
        </div>
        {isExpanded ? <ChevronUp size={18} className="text-muted-foreground" /> : <ChevronDown size={18} className="text-muted-foreground" />}
      </div>
      
      {isExpanded && (
        <CardContent className="px-4 pb-4 pt-0 border-t border-border/50 mt-2">
          <div className="text-xs font-medium text-muted-foreground mb-2 mt-3 uppercase tracking-wider">Eligibility Formula Used</div>
          <div className="bg-surface2 p-3 rounded-md text-sm font-mono text-text border border-border/50 mb-3 overflow-x-auto whitespace-nowrap">
            Avg Attendance = ( <span className="text-accent">Lec%</span> + <span className="text-accent">Tut%</span> ) / 2 &nbsp;&ge;&nbsp; <span className="text-emerald-400 font-bold">75%</span>
            <span className="text-muted-foreground mx-2">|</span>
            <span className="text-accent">Lec%</span> = Attended<sub>L</sub> / Total<sub>L</sub> &times; 100
            <span className="text-muted-foreground mx-2">|</span>
            <span className="text-accent">Tut%</span> = Attended<sub>T</sub> / Total<sub>T</sub> &times; 100
          </div>
          <p className="text-xs text-text2 leading-relaxed">
            Minimum attendance is found by exhaustive search over all valid (L, T) combinations &mdash; not by applying 75% to each type independently.
            Tie-breaking: when multiple combinations achieve the same minimum total, the one with maximum lecture skips is chosen.
          </p>
        </CardContent>
      )}
    </Card>
  );
}
