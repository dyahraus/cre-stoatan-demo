import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function EvidenceList({ snippets }: { snippets: string[] }) {
  if (snippets.length === 0) return null;

  return (
    <Card className="bg-zinc-900 border-zinc-800">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm text-zinc-400">
          Evidence Snippets ({snippets.length})
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {snippets.map((s, i) => (
          <blockquote
            key={i}
            className="border-l-2 border-zinc-700 pl-2 md:pl-3 text-sm text-zinc-300 italic"
          >
            <span className="text-zinc-600 not-italic font-mono text-xs mr-2">
              {i + 1}.
            </span>
            {s}
          </blockquote>
        ))}
      </CardContent>
    </Card>
  );
}
