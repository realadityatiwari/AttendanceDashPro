import { AlertCircle } from "lucide-react";
import { GlassCard } from "./GlassCard";

interface ErrorStateProps {
  title?: string;
  message?: string;
}

export function ErrorState({ 
  title = "Failed to load data", 
  message = "An error occurred while fetching data from the server. The API may be unavailable or not fully implemented." 
}: ErrorStateProps) {
  return (
    <GlassCard className="bg-red-950/20 border-red-900/50">
      <div className="flex flex-col items-center justify-center text-center p-8">
        <AlertCircle className="h-10 w-10 text-red-500 mb-4" />
        <h3 className="text-lg font-semibold text-red-400">{title}</h3>
        <p className="text-sm text-red-400/80 mt-2 max-w-md mx-auto">
          {message}
        </p>
      </div>
    </GlassCard>
  );
}
