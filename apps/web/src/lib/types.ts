export type RunStatus = "CREATED" | "GENERATING" | "STORING" | "VERIFYING" | "COMPLETED" | "FAILED";

export type RunResponse = {
  run_id: string;
  status: RunStatus;
  prompt: string;
  provider: string | null;
  model: string | null;
  asset_uri: string | null;
  manifest_uri: string | null;
  asset_sha256: string | null;
  verification_status: "pending" | "verified" | "failed";
  evaluation_status: "NOT_RUN" | "PASSED" | "FAILED";
  criterion_results: CriterionResult[];
  failed_hard_gates: string[];
  verdict: RoundVerdict | null;
  judge_status: "NOT_RUN" | "SKIPPED" | "PASSED" | "FAILED" | "ERROR";
  judge_provider: string | null;
  judge_model: string | null;
  judge_error: string | null;
  error: string | null;
};

export type CriterionResult = {
  criterion_id: string;
  passed: boolean;
  score: number | null;
  hard_gate: boolean;
  evaluator: string;
  feedback: string | null;
  evidence: Record<string, unknown>;
  evaluated_at: string;
};

export type RunCreateRequest = {
  prompt: string;
  dry_run?: boolean;
  brief_id?: string;
};

export type RoundVerdict = {
  passed: boolean;
  selected_attempt_id: string | null;
  quality_score: number;
  confidence: number;
  feedback: string;
  criterion_failures: string[];
};
