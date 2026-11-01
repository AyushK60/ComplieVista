// Thin typed API client for the M1 workspace. Structured errors are surfaced, never swallowed.
export type ErrorBody = { code: string; message: string };

export class ApiError extends Error {
  code: string;
  constructor(public body: ErrorBody) {
    super(`${body.code}: ${body.message}`);
    this.code = body.code;
  }
}

async function unwrap<T>(r: Response): Promise<T> {
  if (!r.ok) {
    let body: ErrorBody = { code: "HTTP_" + r.status, message: r.statusText };
    try {
      const j = await r.json();
      if (j?.error) body = j.error;
    } catch {
      /* non-JSON error */
    }
    throw new ApiError(body);
  }
  return r.json() as Promise<T>;
}

export const api = {
  health: () => fetch("/api/v1/health").then((r) => unwrap<Health>(r)),
  capabilities: () => fetch("/api/v1/capabilities").then((r) => unwrap<Capabilities>(r)),
  limits: () => fetch("/api/v1/limits").then((r) => unwrap<{ limits: Record<string, number> }>(r)),
  analyses: () => fetch("/api/v1/analyses").then((r) => unwrap<AnalysisSummary[]>(r)),

  paste: (language: string, filename: string, content: string) =>
    fetch("/api/v1/sources", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind: "paste", language, filename, content }),
    }).then(unwrap<IngestResult>),

  upload: (files: File[]) => {
    const form = new FormData();
    for (const f of files) form.append("file", f);
    return fetch("/api/v1/sources", { method: "POST", body: form }).then(unwrap<IngestResult>);
  },

  /** M6-C: paste a pair side and return its first target reference. */
  createSnapshotFromPaste: async (language: string, filename: string, content: string) => {
    const r = await api.paste(language, filename, content);
    const targets = await fetch(
      `/api/v1/projects/${r.project_id}/targets`).then(
      unwrap<Array<{ target_id: string; status: string }>>);
    return { snapshot_id: r.snapshot_id, target_id: targets[0].target_id };
  },

  importGithub: (url: string, ref?: string) =>
    fetch("/api/v1/imports/github", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(ref ? { url, ref } : { url }),
    }).then(unwrap<IngestResult & ImportProvenance>),

  project: (id: string) => fetch(`/api/v1/projects/${id}`).then(unwrap<Project>),
  projects: () => fetch("/api/v1/projects").then(unwrap<Array<{
    id: string; name: string; created_utc: string;
    snapshot_id: string; origin: string; combined_sha256: string }>>),
  targets: (id: string) => fetch(`/api/v1/projects/${id}/targets`).then(unwrap<Target[]>),
  snapshot: (pid: string, sid: string) =>
    fetch(`/api/v1/projects/${pid}/snapshots/${sid}`).then(unwrap<SnapshotDetail>),
  file: (pid: string, sid: string, fid: string) =>
    fetch(`/api/v1/projects/${pid}/snapshots/${sid}/files/${fid}`).then(unwrap<FileDetail>),

  createAnalysis: (snapshot_id: string, target_id: string) =>
    fetch("/api/v1/analyses", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ snapshot_id, target_id }),
    }).then(unwrap<AnalysisJobRef>),
  analysis: (id: string) => fetch(`/api/v1/analyses/${id}`).then(unwrap<AnalysisJob>),
  stage: (id: string, stage: string) =>
    fetch(`/api/v1/analyses/${id}/stages/${stage}`).then(unwrap<StageData>),
  stageRaw: (id: string, stage: string) =>
    fetch(`/api/v1/analyses/${id}/stages/${stage}/raw`).then(unwrap<StageRaw>),
  cancelAnalysis: (id: string) =>
    fetch(`/api/v1/analyses/${id}/cancel`, { method: "POST" }).then(unwrap),
};

export interface AnalysisJobRef { analysis_id: string; status: string; existed: boolean }
export interface AnalysisJob {
  id: string;
  status: string;
  language: string;
  primary_file: string;
  source_combined_sha256: string;
  tool_fingerprint: string | null;
  image_id: string | null;
  error_code: string | null;
  duration_ms: number | null;
  ready_for_controlled_execution: boolean;
  note: string;
  stages: Array<{
    stage: string; availability: string; observation_class: string;
    exit_code: number | null; counts: Record<string, unknown>; truncated: boolean;
    duration_ms: number | null;
  }>;
}
export interface StageData {
  analysis_id: string;
  stage: string;
  language: string;
  availability: string;
  observation_class: string;
  exit_code: number | null;
  counts: Record<string, unknown>;
  items: Array<Record<string, unknown>>;
  limitations: string[];
  raw_artifact_sha256: string | null;
  stderr_artifact_sha256: string | null;
  truncated: boolean;
  duration_ms: number | null;
  provenance?: {
    source_combined_sha256: string;
    raw_artifact_sha256: string | null;
    stderr_artifact_sha256: string | null;
    invocation: Record<string, unknown>;
  };
  invocation: {
    tool?: string | null;
    argv_tail?: string[] | null;
    worker?: string | null;
    tool_versions?: Record<string, string>;
    image_id?: string | null;
    policy_version?: string;
  };
}
export interface StageRaw {
  excerpt: string | null;
  truncated: boolean;
  bytes?: number;
  artifact_sha256?: string;
}

export interface IngestResult {
  project_id: string;
  snapshot_id: string;
  file_count: number;
  rejected_count: number;
  rejected: Array<{ entry: string; reason_code: string; detail?: string }>;
  existed: boolean;
}
export interface Health {
  status: string;
  python_version: string;
  schema_version: string;
}
export interface Capabilities {
  tools: Record<string, ToolCap>;
  modes: Record<string, string>;
  notes: string[];
}
export interface ToolCap {
  available: boolean;
  version: string;
}
export interface AnalysisSummary {
  id: string;
  language: string;
  stages: string[];
  source_combined_sha256: string;
}
export interface ImportProvenance {
  import_id: string;
  canonical_owner: string;
  canonical_repo: string;
  commit_sha: string;
  archive_sha256: string;
  policy_version: string;
}
export interface Project {
  id: string;
  name: string;
  created_utc: string;
  snapshots: Array<{ id: string; origin: string; combined_sha256: string }>;
}
export interface Reason {
  code: string;
  detail: string;
  verified: boolean;
}
export interface Target {
  target_id: string;
  snapshot_id: string;
  kind: string;
  primary_file: string;
  status: string;
  ready_for_controlled_execution: boolean;
  reasons: Reason[];
  note: string;
}
export interface SnapshotDetail {
  id: string;
  origin: string;
  combined_sha256: string;
  files: Array<{ id: string; rel_path: string; size: number; encoding: string; language: string }>;
  diagnostics: Array<{ file_path: string; severity: string; code: string; detail: string }>;
}
export interface FileDetail {
  id: string;
  rel_path: string;
  encoding: string;
  language: string;
  content_sha256: string;
  text: string | null;
  text_truncated: boolean;
}

export interface ExecutionRef { execution_id: string; status: string; existed: boolean; error?: string }
export interface ExecutionJob {
  id: string; status: string; language: string; primary_file: string;
  source_combined_sha256: string; image_id: string | null; binary_sha256: string | null;
  exit_code: number | null; error_code: string | null;
  events_count: number | null; events_truncated: number;
  stdout_truncated: number; stderr_truncated: number;
  stdout_sha256: string | null; stderr_sha256: string | null; trace_sha256: string | null;
  duration_ms: number | null;
  profile?: string; host_pid?: number | null;
  memory_count?: number | null; process_count?: number | null;
  /* M8-G0 trace trust (F-M7-01/02): honest labeling, never a green default. */
  trace_trust?: "CURATED_COOPERATIVE" | "UNTRUSTED_TARGET" | null;
  trace_channel?: string | null;
  trace_integrity?: "CONSISTENT" | "SUSPECT" | null;
  build_image_id?: string | null;
  ready_for_controlled_execution: boolean; note: string;
}
export interface ExecutionEvent {
  seq: number; kind: string; payload: Record<string, unknown>; sha256: string;
}
export interface ExecutionOutput {
  exit_code: number | null; stdout: string | null; stderr: string | null; truncated: boolean;
}
/** M5: typed observation chunks (m5.memory.v1 / m5.process.v1). */
export interface ObservationChunk {
  seq: number; payload: Record<string, unknown>; sha256: string;
}
export interface ObservationStream {
  execution_id: string; status: string; schema: string; language: string;
  profile: string; total: number; artifact_sha256: string | null;
  chunks: ObservationChunk[]; count: number; kinds: string[]; next_after: number;
  limitations: string[];
  host_pid?: number | null; exit_code?: number | null; duration_ms?: number | null;
}

export const executions = {
  create: (snapshot_id: string, target_id: string, profile?: string) =>
    fetch("/api/v1/executions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ snapshot_id, target_id, profile }),
    }).then(unwrap<ExecutionRef>),
  get: (id: string) => fetch(`/api/v1/executions/${id}`).then(unwrap<ExecutionJob>),
  events: (id: string, after = 0, limit = 500) =>
    fetch(`/api/v1/executions/${id}/events?after=${after}&limit=${limit}`).then(unwrap<{events: ExecutionEvent[]}>),
  output: (id: string) => fetch(`/api/v1/executions/${id}/output`).then(unwrap<ExecutionOutput>),
  cancel: (id: string) => fetch(`/api/v1/executions/${id}/cancel`, { method: "POST" }).then(unwrap),
  memory: (id: string, after = 0, limit = 500) =>
    fetch(`/api/v1/executions/${id}/memory?after=${after}&limit=${limit}`).then(unwrap<ObservationStream>),
  process: (id: string, after = 0, limit = 500) =>
    fetch(`/api/v1/executions/${id}/process?after=${after}&limit=${limit}`).then(unwrap<ObservationStream>),
};

/** M6: OptimizationLab / benchmarks / pair comparison. */
export interface ExperimentStage {
  stage: string; availability: string;
  result: Record<string, unknown>;
  artifact_sha256: string | null; duration_ms: number | null;
}
export interface Experiment {
  id: string; kind: string; status: string; config: Record<string, unknown>;
  source_combined_sha256: string | null; error_code: string | null;
  result_sha256: string | null; created_utc: string; finished_utc: string | null;
  duration_ms: number | null; stages: ExperimentStage[];
}
export interface PairSpec {
  id: string; concept: string; c_file: string; py_file: string;
  expected_stdout: string; c_source: string | null; py_source: string | null;
}
export const experiments = {
  create: (body: Record<string, unknown>) =>
    fetch("/api/v1/experiments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(unwrap<ExecutionRef & { experiment_id?: string }>),
  get: (id: string) => fetch(`/api/v1/experiments/${id}`).then(unwrap<Experiment>),
  artifact: (id: string, stage: string, kind: string) =>
    fetch(`/api/v1/experiments/${id}/artifacts/${stage}/${kind}`)
      .then(unwrap<{ excerpt: string; truncated: boolean; sha256: string; bytes: number }>),
  cancel: (id: string) =>
    fetch(`/api/v1/experiments/${id}/cancel`, { method: "POST" }).then(unwrap),
};
export const pairs = {
  list: () => fetch("/api/v1/pairs").then(unwrap<{ pairs: PairSpec[] }>),
};

/** M7: Demo Library + Error Microscope. */
export interface DemoEntry {
  id: string; group: string; title: string; difficulty: string;
  concepts: string[];
  files: Array<{ path: string; sha256: string }>;
  primary_file: string; tus: string[];
  expected_stdout: string; expected_exit: number;
  guided: { simple: string; detailed: string; technical: string };
  capabilities: Record<string, string>;
  limits: string[];
}
export interface DemoRunResult {
  demo_id: string; execution_id: string; snapshot_id: string; target_id: string;
  status: string; exit_code: number | null; stdout: string | null;
  expected_stdout: string; stdout_match: boolean; expected_exit: number;
}
export const demos = {
  list: () => fetch("/api/v1/demos").then(unwrap<{ demos: DemoEntry[] }>),
  run: (id: string) =>
    fetch(`/api/v1/demos/${id}/run`, { method: "POST" }).then(unwrap<DemoRunResult>),
  analyze: (id: string) =>
    fetch(`/api/v1/demos/${id}/analyze`, { method: "POST" })
      .then(unwrap<{ demo_id: string; analysis_id: string; status: string;
        snapshot_id?: string; target_id?: string }>),
  optimize: (id: string) =>
    fetch(`/api/v1/demos/${id}/optimize`, { method: "POST" })
      .then(unwrap<{ experiment_id?: string; status: string }>),
  reportUrl: (id: string) => `/api/v1/demos/${id}/report`,
};
export const errorFixtures = {
  list: () => fetch("/api/v1/demos/errors")
    .then(unwrap<{ fixtures: Array<{ id: string; file: string; language: string;
      kind: string }> }>),
  run: (id: string) =>
    fetch(`/api/v1/demos/errors/${id}/run`, { method: "POST" })
      .then(unwrap<{ fixture_id: string; kind: string; status?: string;
        exit_code?: number | null; diagnostic?: string; analysis_id?: string }>),
};
