"use client";

import { useMemo, useState } from "react";
import { BriefForm } from "@/components/brief-form";
import { ResultPanel } from "@/components/result-panel";
import { createRun } from "@/lib/api";
import type { RunResponse } from "@/lib/types";

const DEFAULT_PROMPT =
  "Create a clean e-commerce product shot of a stainless steel water bottle centered on a pure white background. The bottle should be fully visible, uncropped, front-facing, and premium-looking. No text, logos, hands, props, or shadows.";

export default function Home() {
  const [prompt, setPrompt] = useState(DEFAULT_PROMPT);
  const [dryRun, setDryRun] = useState(false);
  const [result, setResult] = useState<RunResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const apiBaseUrl = useMemo(
    () => process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000",
    [],
  );

  async function handleSubmit() {
    setIsLoading(true);
    setError(null);
    setResult(null);
    try {
      const nextResult = await createRun(apiBaseUrl, { prompt, dry_run: dryRun });
      setResult(nextResult);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Generation failed");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="min-h-screen px-4 py-6 sm:px-6 lg:px-8">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-5">
        <header className="flex flex-col gap-1 border-b border-[var(--border)] pb-4">
          <h1 className="text-2xl font-semibold tracking-normal sm:text-3xl">Crucible</h1>
          <p className="max-w-3xl text-sm leading-6 text-[var(--muted)]">
            Genblaze generation, Backblaze B2 storage, and manifest verification for
            e-commerce product shots.
          </p>
        </header>

        <div className="grid gap-5 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
          <BriefForm
            prompt={prompt}
            dryRun={dryRun}
            isLoading={isLoading}
            onPromptChange={setPrompt}
            onDryRunChange={setDryRun}
            onSubmit={handleSubmit}
          />
          <ResultPanel apiBaseUrl={apiBaseUrl} result={result} error={error} isLoading={isLoading} />
        </div>
      </div>
    </main>
  );
}
