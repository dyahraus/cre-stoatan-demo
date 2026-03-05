"use client";

import { cn } from "@/lib/utils";

interface StepCardProps {
  stepNumber: number;
  title: string;
  description: string;
  status: "locked" | "active" | "completed";
  summary?: string;
  children: React.ReactNode;
}

export function StepCard({
  stepNumber,
  title,
  description,
  status,
  summary,
  children,
}: StepCardProps) {
  return (
    <div
      className={cn(
        "rounded-lg border transition-all duration-300",
        status === "active" && "border-blue-500/50 bg-zinc-900/50",
        status === "completed" && "border-zinc-700 bg-zinc-900/30",
        status === "locked" && "border-zinc-800/50 bg-zinc-950/50 opacity-40"
      )}
    >
      <div className="flex items-center gap-3 p-4">
        <div
          className={cn(
            "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-bold",
            status === "active" && "bg-blue-500/20 text-blue-400",
            status === "completed" && "bg-green-500/20 text-green-400",
            status === "locked" && "bg-zinc-800 text-zinc-500"
          )}
        >
          {status === "completed" ? (
            <svg
              className="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M5 13l4 4L19 7"
              />
            </svg>
          ) : (
            stepNumber
          )}
        </div>
        <div className="min-w-0 flex-1">
          <h3
            className={cn(
              "text-sm font-semibold",
              status === "active" && "text-white",
              status === "completed" && "text-zinc-300",
              status === "locked" && "text-zinc-500"
            )}
          >
            {title}
          </h3>
          {status === "completed" && summary ? (
            <p className="text-xs text-zinc-500 truncate">{summary}</p>
          ) : (
            <p className="text-xs text-zinc-500">{description}</p>
          )}
        </div>
      </div>

      {status !== "locked" && (
        <div className="border-t border-zinc-800/50 p-4">{children}</div>
      )}
    </div>
  );
}
