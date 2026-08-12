import Link from "next/link";
import { LayoutDashboard, BookOpen, Clock, User, CalendarDays, FlaskConical, CalendarClock } from "lucide-react";

export function Sidebar() {
  const navItems = [
    { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
    { name: "Subjects", href: "/subjects", icon: BookOpen },
    { name: "History", href: "/history", icon: Clock },
    { name: "Profile", href: "/profile", icon: User },
  ];

  const toolItems = [
    { name: "Academic Events", href: "/tools/events", icon: CalendarDays },
    { name: "Quiz Schedule", href: "/tools/quiz-schedule", icon: CalendarClock },
    { name: "Laboratory", href: "/tools/laboratory", icon: FlaskConical },
  ];

  return (
    <div className="flex h-full flex-col py-4">
      <div className="px-6 py-2">
        <h2 className="text-xl font-bold tracking-tight text-primary">AttendanceDash</h2>
        <p className="text-xs text-muted-foreground mt-1">Pro Edition</p>
      </div>

      <div className="flex-1 overflow-y-auto py-4">
        <nav className="space-y-1 px-3">
          {navItems.map((item) => (
            <Link
              key={item.name}
              href={item.href}
              className="flex items-center rounded-md px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
            >
              <item.icon className="mr-3 h-5 w-5" aria-hidden="true" />
              {item.name}
            </Link>
          ))}
        </nav>

        <div className="mt-8 px-6">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Tools</h3>
        </div>
        <nav className="mt-2 space-y-1 px-3">
          {toolItems.map((item) => (
            <Link
              key={item.name}
              href={item.href}
              className="flex items-center rounded-md px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
            >
              <item.icon className="mr-3 h-5 w-5" aria-hidden="true" />
              {item.name}
            </Link>
          ))}
        </nav>
      </div>
    </div>
  );
}
