"use client";

import Link from "next/link";
import { TierBadge } from "@/components/shared/tier-badge";

const TIER_ROWS: {
  tier: "strong" | "moderate" | "watchlist" | "noise";
  range: string;
  meaning: string;
}[] = [
  {
    tier: "strong",
    range: "75–100",
    meaning:
      "Specific, committed plans with dollar amounts, square footage, or groundbreaking dates.",
  },
  {
    tier: "moderate",
    range: "50–74",
    meaning:
      "Substantive discussion: network study underway, real estate team engaged, capacity constraints flagged.",
  },
  {
    tier: "watchlist",
    range: "25–49",
    meaning:
      "Early signals or qualified statements; track for future quarters.",
  },
  {
    tier: "noise",
    range: "0–24",
    meaning: "No actionable warehouse expansion signal in this transcript.",
  },
];

export default function HowItWorksPage() {
  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <div>
        <h2 className="text-xl md:text-2xl font-bold text-white">How it works</h2>
        <p className="text-sm text-zinc-500 mt-1">
          Plain-English methodology for the scores you see across the product.
        </p>
      </div>

      <Section title="The four-tier output">
        <p className="text-sm text-zinc-300">
          Every transcript gets a composite score from 0 to 100%, mapped onto
          one of four broker-readable tiers. The number is for sorting; the
          tier is the part you read first.
        </p>
        <p className="text-xs text-zinc-500">
          Internally — and in the API — the same number is stored as a 0.0 to
          1.0 decimal (so 79% is <code className="font-mono text-zinc-300">0.79</code>{" "}
          when you call <code className="font-mono text-zinc-300">/api/scores/PLD</code>).
          The UI multiplies by 100 everywhere; the math doesn&apos;t change.
        </p>
        <div className="rounded-lg border border-zinc-800 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-zinc-900 border-b border-zinc-800">
                <th className="text-left px-3 py-2 font-medium text-zinc-400">
                  Tier
                </th>
                <th className="text-left px-3 py-2 font-medium text-zinc-400 w-24">
                  Score
                </th>
                <th className="text-left px-3 py-2 font-medium text-zinc-400">
                  What it means
                </th>
              </tr>
            </thead>
            <tbody>
              {TIER_ROWS.map((r) => (
                <tr key={r.tier} className="border-b border-zinc-900 last:border-0">
                  <td className="px-3 py-2">
                    <TierBadge tier={r.tier} />
                  </td>
                  <td className="px-3 py-2 font-mono text-zinc-300 tabular-nums">
                    {r.range}
                  </td>
                  <td className="px-3 py-2 text-zinc-300">{r.meaning}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <Section title="How the composite is built">
        <p className="text-sm text-zinc-300">
          We score each <em>chunk</em> of a transcript first, then aggregate
          chunks into a transcript score, then aggregate transcripts into a
          company score.
        </p>

        <Subsection title="1. Hybrid chunk score">
          <pre className="rounded bg-zinc-900 border border-zinc-800 px-3 py-2 text-xs font-mono text-zinc-200 overflow-x-auto">
{`chunk_score
  = 0.40 × LLM expansion strength
  + 0.25 × keyword match strength
  + 0.20 × semantic concept score
  + 0.15 × commitment evidence`}
          </pre>
          <p className="text-xs text-zinc-500">
            Every contribution is auditable: the LLM provides reasoning + an
            evidence quote, the keyword engine logs the literal phrase it
            matched, and the concept engine logs the cosine similarity
            against each concept&apos;s reference vector.
          </p>
        </Subsection>

        <Subsection title="2. Transcript composite (over relevant chunks)">
          <pre className="rounded bg-zinc-900 border border-zinc-800 px-3 py-2 text-xs font-mono text-zinc-200 overflow-x-auto">
{`composite
  = 0.40 × max chunk score      (peak signal in any chunk)
  + 0.30 × weighted average      (weighted by warehouse_relevance)
  + 0.15 × signal flag bonus     (capex / build-to-suit / last-mile)
  + 0.15 × time-horizon bonus    (immediate ≫ historical)`}
          </pre>
          <p className="text-xs text-zinc-500">
            A chunk counts as relevant when its LLM warehouse-relevance is ≥
            0.30 <em>or</em> the chunk has at least one keyword hit. The
            keyword override stops a phrase-rich chunk from being silently
            dropped.
          </p>
        </Subsection>

        <Subsection title="3. Company score">
          <p className="text-xs text-zinc-500">
            Most-recent transcript wins for the headline composite + tier. The
            company-level page also shows the prior quarters as a sparkline so
            you can see whether momentum is building or fading.
          </p>
        </Subsection>
      </Section>

      <Section title="The Signal Framework">
        <p className="text-sm text-zinc-300">
          The keyword side of the score is fully editable. Visit{" "}
          <Link
            href="/framework"
            className="text-blue-400 hover:text-blue-300"
          >
            /framework
          </Link>{" "}
          to add phrases, change weights, or build a second framework for
          comparison. Commitment-level keywords (e.g. &ldquo;broke ground&rdquo;,
          &ldquo;letter of intent&rdquo;) are gated on a numeric or date
          companion within ~20 tokens — so &ldquo;we may&rdquo; alone never
          fires unless it&apos;s anchored to a real commitment.
        </p>
        <p className="text-sm text-zinc-300">
          <strong>Semantic concepts</strong> live alongside keywords in the
          same framework. A concept like &ldquo;warehouse capacity
          constraints&rdquo; matches by cosine similarity to a reference
          vector built from its description plus a few example phrases — so a
          chunk saying &ldquo;we don&apos;t have the storage capacity to keep
          up with demand&rdquo; can fire even when no literal keyword
          matches. Each concept has a weight and a similarity threshold;
          partial-credit hits scale by how far above the threshold the
          similarity sits. Embeddings come from Voyage AI by default.
        </p>
      </Section>

      <Section title="Confidence">
        <p className="text-sm text-zinc-300">
          The dots next to each score (●●●○○) reflect how many relevant chunks
          fed the composite, capped at 5. A single chunk full of strong
          language can still produce a Strong tier, but with low confidence —
          dig into the supporting chunks before acting.
        </p>
      </Section>

      <Section title="Boosts (section + speaker)">
        <p className="text-sm text-zinc-300">
          Each chunk score is multiplied by a section-type boost and a
          speaker-role boost from the active framework, then clamped to 1.0.
          The default seed lifts prepared remarks slightly (1.10×) and
          dampens Q&amp;A (0.90×); CEO statements get 1.20×, CFO 1.10×,
          analyst questions 0.70×.
        </p>
        <p className="text-xs text-zinc-500">
          Edit these on{" "}
          <Link href="/framework" className="text-blue-400 hover:text-blue-300">
            /framework
          </Link>{" "}
          — set everything to 1.0× for a neutral baseline. The applied
          multiplier is shown on every transcript&apos;s score breakdown when
          it deviates from neutral, so it&apos;s never hidden.
        </p>
      </Section>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3">
      <h3 className="text-base font-semibold text-white">{title}</h3>
      {children}
    </section>
  );
}

function Subsection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2 pl-3 border-l-2 border-zinc-800">
      <h4 className="text-sm font-medium text-zinc-200">{title}</h4>
      {children}
    </div>
  );
}
