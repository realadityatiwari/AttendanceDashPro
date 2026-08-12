import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface GlassCardProps extends React.HTMLAttributes<HTMLDivElement> {
  children?: React.ReactNode;
}

export function GlassCard({ children, className, ...props }: GlassCardProps) {
  return (
    <Card 
      className={cn(
        "bg-surface/50 border-border/50 backdrop-blur-sm overflow-hidden", 
        className
      )} 
      {...props}
    >
      {children}
    </Card>
  );
}
