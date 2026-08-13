import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface GlassCardProps extends React.HTMLAttributes<HTMLDivElement> {
  children?: React.ReactNode;
}

export function GlassCard({ children, className, ...props }: GlassCardProps) {
  return (
    <Card 
      className={cn(
        "bg-card border-border shadow-none", 
        className
      )} 
      {...props}
    >
      {children}
    </Card>
  );
}
