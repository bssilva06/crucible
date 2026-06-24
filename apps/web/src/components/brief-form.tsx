import { Loader2, Play, RotateCcw } from "lucide-react";

type BriefFormProps = {
  prompt: string;
  dryRun: boolean;
  isLoading: boolean;
  onPromptChange: (prompt: string) => void;
  onDryRunChange: (dryRun: boolean) => void;
  onSubmit: () => void;
};

export function BriefForm({
  prompt,
  dryRun,
  isLoading,
  onPromptChange,
  onDryRunChange,
  onSubmit,
}: BriefFormProps) {
  const canSubmit = prompt.trim().length > 0 && !isLoading;

  return (
    <section className="rounded-md border border-[var(--border)] bg-[var(--panel)] p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-base font-semibold">Brief</h2>
        <label className="flex items-center gap-2 text-sm text-[var(--muted)]">
          <input
            className="h-4 w-4 accent-[var(--accent)]"
            type="checkbox"
            checked={dryRun}
            onChange={(event) => onDryRunChange(event.target.checked)}
          />
          Dry run
        </label>
      </div>

      <textarea
        className="min-h-[260px] w-full resize-y rounded-md border border-[var(--border)] bg-white p-3 text-sm leading-6 outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-teal-100"
        maxLength={1200}
        value={prompt}
        onChange={(event) => onPromptChange(event.target.value)}
      />

      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <span className="text-xs text-[var(--muted)]">{prompt.length}/1200</span>
        <div className="flex gap-2">
          <button
            className="inline-flex h-10 items-center gap-2 rounded-md border border-[var(--border)] px-3 text-sm font-medium text-[var(--foreground)] disabled:opacity-50"
            type="button"
            disabled={isLoading}
            onClick={() => onPromptChange("")}
            title="Clear brief"
          >
            <RotateCcw className="h-4 w-4" />
            Clear
          </button>
          <button
            className="inline-flex h-10 items-center gap-2 rounded-md bg-[var(--accent)] px-4 text-sm font-semibold text-white disabled:opacity-50"
            type="button"
            disabled={!canSubmit}
            onClick={onSubmit}
            title="Generate asset"
          >
            {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            Generate
          </button>
        </div>
      </div>
    </section>
  );
}
