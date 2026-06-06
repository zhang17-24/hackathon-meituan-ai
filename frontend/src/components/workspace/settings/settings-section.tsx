import { cn } from "@/lib/utils";

export function SettingsSection({
  className,
  title,
  description,
  children,
}: {
  className?: string;
  title: React.ReactNode;
  description?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section
      className={cn(
        "rounded-3xl border border-pink-100/80 bg-white/45 p-5 shadow-sm",
        className,
      )}
    >
      <header className="space-y-2">
        <div className="text-lg font-bold text-[#5b1738]">{title}</div>
        {description && (
          <div className="text-sm leading-6 text-[#8f7b88]">{description}</div>
        )}
      </header>
      <main className="mt-4">{children}</main>
    </section>
  );
}
