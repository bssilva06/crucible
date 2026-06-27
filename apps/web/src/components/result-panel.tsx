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
  const deterministicResults =
    result?.criterion_results.filter((criterion) => criterion.evaluator === "deterministic") ?? [];
  const judgeResults =
    result?.criterion_results.filter((criterion) => criterion.evaluator !== "deterministic") ?? [];

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
          <Meta label="Judge" value={result.judge_status} />
          <Meta label="Provider" value={result.provider || ""} />
          <Meta label="Model" value={result.model || ""} />
          <Meta label="Verification" value={result.verification_status} />
          <Meta label="Judge provider" value={result.judge_provider || ""} />
          <Meta label="Judge model" value={result.judge_model || ""} />
          <Meta label="Failed gates" value={result.failed_hard_gates.join(", ")} wide />
          <Meta label="SHA-256" value={result.asset_sha256 || ""} wide />
          <Meta label="Manifest" value={result.manifest_uri || ""} wide />
          {result.judge_error ? <Meta label="Judge note" value={result.judge_error} wide /> : null}
          {result.error ? <Meta label="Error" value={result.error} wide /> : null}
        </dl>
      ) : null}

      {result?.verdict ? (
        <div className="mt-4 rounded-md border border-[var(--border)] bg-[#fafaf8] p-3">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold">Verdict</h3>
            <span
              className={
                result.verdict.passed
                  ? "rounded-md bg-teal-50 px-2 py-1 text-xs font-medium text-[var(--accent-strong)]"
                  : "rounded-md bg-red-50 px-2 py-1 text-xs font-medium text-[var(--danger)]"
              }
            >
              {result.verdict.passed ? "Passed quality gates" : "Needs revision"}
            </span>
          </div>
          <p className="text-sm leading-5">{result.verdict.feedback}</p>
          <div className="mt-3 grid gap-2 text-xs text-[var(--muted)] sm:grid-cols-2">
            <span>Quality score {result.verdict.quality_score.toFixed(3)}</span>
            <span>Confidence {result.verdict.confidence.toFixed(3)}</span>
          </div>
        </div>
      ) : null}

      {result?.candidates.length ? (
        <div className="mt-4">
          <div className="mb-2 flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold">Candidates</h3>
            <span className="text-xs text-[var(--muted)]">{result.candidate_count} generated</span>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {result.candidates.map((candidate) => (
              <CandidateCard
                apiBaseUrl={apiBaseUrl}
                candidate={candidate}
                isSelected={candidate.attempt_id === result.selected_attempt_id}
                runId={result.run_id}
                key={candidate.attempt_id}
              />
            ))}
          </div>
        </div>
      ) : null}

      <CriterionSection title="Deterministic Gates" results={deterministicResults} />
      <CriterionSection
        title="AI Judge"
        results={judgeResults}
        emptyText={
          !result
            ? undefined
            : result.judge_status === "SKIPPED"
            ? result.judge_error || "Judge skipped."
            : result.judge_status === "ERROR"
              ? result.judge_error || "Judge errored."
              : "No judge results yet."
        }
      />
    </section>
  );
}

function CandidateCard({
  apiBaseUrl,
  runId,
  candidate,
  isSelected,
}: {
  apiBaseUrl: string;
  runId: string;
  candidate: RunResponse["candidates"][number];
  isSelected: boolean;
}) {
  const assetUrl = candidate.asset
    ? `${apiBaseUrl}/runs/${encodeURIComponent(runId)}/candidates/${encodeURIComponent(candidate.attempt_id)}/asset`
    : null;
  const score = candidate.verdict ? candidate.verdict.quality_score.toFixed(3) : "—";
  return (
    <div className="overflow-hidden rounded-md border border-[var(--border)] bg-[#fafaf8]">
      <div className="flex aspect-square items-center justify-center border-b border-[var(--border)] bg-[#f1f1ed]">
        {assetUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img className="h-full w-full object-contain" src={assetUrl} alt={`${candidate.attempt_id} asset`} />
        ) : (
          <div className="px-3 text-center text-xs text-[var(--muted)]">{candidate.error || "No asset"}</div>
        )}
      </div>
      <div className="space-y-2 p-3 text-xs">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="break-all font-mono">{candidate.attempt_id}</span>
          <span
            className={
              isSelected
                ? "rounded-md bg-teal-50 px-2 py-1 font-medium text-[var(--accent-strong)]"
                : candidate.status === "FAILED" || candidate.status === "REJECTED"
                  ? "rounded-md bg-red-50 px-2 py-1 font-medium text-[var(--danger)]"
                  : "rounded-md bg-stone-100 px-2 py-1 font-medium text-[var(--muted)]"
            }
          >
            {isSelected ? "SELECTED" : candidate.status}
          </span>
        </div>
        <div className="grid gap-1 text-[var(--muted)]">
          <span className="break-words">Provider {candidate.provider || "—"}</span>
          <span className="break-words">Model {candidate.model || "—"}</span>
          <span>Score {score}</span>
          <span className="break-words">Failed gates {candidate.failed_hard_gates.join(", ") || "—"}</span>
        </div>
        {candidate.selection_reason ? <p className="leading-5">{candidate.selection_reason}</p> : null}
      </div>
    </div>
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

function CriterionSection({
  title,
  results,
  emptyText,
}: {
  title: string;
  results: RunResponse["criterion_results"];
  emptyText?: string;
}) {
  if (!results.length && !emptyText) {
    return null;
  }
  return (
    <div className="mt-4">
      <h3 className="mb-2 text-sm font-semibold">{title}</h3>
      {results.length ? (
        <div className="overflow-hidden rounded-md border border-[var(--border)]">
          {results.map((criterion) => (
            <div
              className="grid gap-2 border-b border-[var(--border)] bg-[#fafaf8] p-3 text-sm last:border-b-0 sm:grid-cols-[150px_80px_minmax(0,1fr)]"
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
      ) : (
        <div className="rounded-md border border-[var(--border)] bg-[#fafaf8] p-3 text-sm text-[var(--muted)]">
          {emptyText}
        </div>
      )}
    </div>
  );
}
