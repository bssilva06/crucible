import { AlertCircle, CheckCircle2, Image as ImageIcon } from "lucide-react";
import type { RunResponse } from "@/lib/types";

type ResultPanelProps = {
  apiBaseUrl: string;
  result: RunResponse | null;
  error: string | null;
  isLoading: boolean;
};

export function ResultPanel({ apiBaseUrl, result, error, isLoading }: ResultPanelProps) {
  const assetUrl =
    result?.status === "COMPLETED" ? `${apiBaseUrl}/runs/${encodeURIComponent(result.run_id)}/asset` : null;

  return (
    <section className="rounded-md border border-[var(--border)] bg-[var(--panel)] p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-base font-semibold">Result</h2>
        <StatusBadge result={result} error={error} isLoading={isLoading} />
      </div>

      <div className="flex aspect-square w-full items-center justify-center overflow-hidden rounded-md border border-[var(--border)] bg-[#f1f1ed]">
        {assetUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img className="h-full w-full object-contain" src={assetUrl} alt="Generated product asset" />
        ) : (
          <div className="flex flex-col items-center gap-2 text-sm text-[var(--muted)]">
            <ImageIcon className="h-8 w-8" />
            {isLoading ? "Generating" : "No asset yet"}
          </div>
        )}
      </div>

      {error ? (
        <div className="mt-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-[var(--danger)]">
          {error}
        </div>
      ) : null}

      {result ? (
        <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
          <Meta label="Run" value={result.run_id} />
          <Meta label="Status" value={result.status} />
          <Meta label="Evaluation" value={result.evaluation_status} />
          <Meta label="Provider" value={result.provider || ""} />
          <Meta label="Model" value={result.model || ""} />
          <Meta label="Verification" value={result.verification_status} />
          <Meta label="Failed gates" value={result.failed_hard_gates.join(", ")} wide />
          <Meta label="SHA-256" value={result.asset_sha256 || ""} wide />
          <Meta label="Manifest" value={result.manifest_uri || ""} wide />
          {result.error ? <Meta label="Error" value={result.error} wide /> : null}
        </dl>
      ) : null}

      {result?.criterion_results.length ? (
        <div className="mt-4">
          <h3 className="mb-2 text-sm font-semibold">Deterministic Gates</h3>
          <div className="overflow-hidden rounded-md border border-[var(--border)]">
            {result.criterion_results.map((criterion) => (
              <div
                className="grid gap-2 border-b border-[var(--border)] bg-[#fafaf8] p-3 text-sm last:border-b-0 sm:grid-cols-[140px_80px_minmax(0,1fr)]"
                key={criterion.criterion_id}
              >
                <div className="break-words font-mono text-xs">{criterion.criterion_id}</div>
                <div>
                  <span
                    className={
                      criterion.passed
                        ? "rounded-md bg-teal-50 px-2 py-1 text-xs font-medium text-[var(--accent-strong)]"
                        : "rounded-md bg-red-50 px-2 py-1 text-xs font-medium text-[var(--danger)]"
                    }
                  >
                    {criterion.passed ? "PASS" : "FAIL"}
                  </span>
                </div>
                <div className="min-w-0">
                  <div className="text-sm leading-5">{criterion.feedback || "No feedback"}</div>
                  <div className="mt-1 text-xs text-[var(--muted)]">
                    Score {criterion.score === null ? "—" : criterion.score.toFixed(3)}
                    {criterion.hard_gate ? " · hard gate" : ""}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function StatusBadge({
  result,
  error,
  isLoading,
}: {
  result: RunResponse | null;
  error: string | null;
  isLoading: boolean;
}) {
  if (error || result?.status === "FAILED") {
    return (
      <span className="inline-flex items-center gap-1 rounded-md bg-red-50 px-2 py-1 text-xs font-medium text-[var(--danger)]">
        <AlertCircle className="h-3.5 w-3.5" />
        Failed
      </span>
    );
  }
  if (result?.status === "COMPLETED") {
    return (
      <span className="inline-flex items-center gap-1 rounded-md bg-teal-50 px-2 py-1 text-xs font-medium text-[var(--accent-strong)]">
        <CheckCircle2 className="h-3.5 w-3.5" />
        Verified
      </span>
    );
  }
  return (
    <span className="rounded-md bg-stone-100 px-2 py-1 text-xs font-medium text-[var(--muted)]">
      {isLoading ? "Running" : "Ready"}
    </span>
  );
}

function Meta({ label, value, wide = false }: { label: string; value: string; wide?: boolean }) {
  return (
    <div className={wide ? "sm:col-span-2" : ""}>
      <dt className="mb-1 text-xs font-medium uppercase text-[var(--muted)]">{label}</dt>
      <dd className="break-words rounded-md border border-[var(--border)] bg-[#fafaf8] px-2 py-2 font-mono text-xs">
        {value || "—"}
      </dd>
    </div>
  );
}
