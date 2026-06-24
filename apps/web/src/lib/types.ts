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
  error: string | null;
};

export type RunCreateRequest = {
  prompt: string;
  dry_run?: boolean;
  brief_id?: string;
};
