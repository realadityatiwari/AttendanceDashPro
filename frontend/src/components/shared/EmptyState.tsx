import { FileQuestion } from "lucide-react";
import { Card } from "@/components/ui/card";

interface EmptyStateProps {
  title?: string;
  message?: string;
  icon?: React.ReactNode;
}

export function EmptyState({ 
  title = "No records found", 
  message = "There is no data to display here yet.",
  icon = <FileQuestion className="h-10 w-10 text-muted-foreground mb-4" />
}: EmptyStateProps) {
  return (
    <Card>
      <div className="flex flex-col items-center justify-center text-center p-12">
        {icon}
        <h3 className="text-base font-semibold text-foreground">{title}</h3>
        <p className="text-sm text-muted-foreground mt-2 max-w-sm mx-auto">
          {message}
        </p>
      </div>
    </Card>
  );
}
