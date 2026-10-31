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

  importGithub: (url: string, ref?: string) =>
    fetch("/api/v1/imports/github", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(ref ? { url, ref } : { url }),
    }).then(unwrap<IngestResult & ImportProvenance>),

  project: (id: string) => fetch(`/api/v1/projects/${id}`).then(unwrap<Project>),
  targets: (id: string) => fetch(`/api/v1/projects/${id}/targets`).then(unwrap<Target[]>),
  snapshot: (pid: string, sid: string) =>
    fetch(`/api/v1/projects/${pid}/snapshots/${sid}`).then(unwrap<SnapshotDetail>),
  file: (pid: string, sid: string, fid: string) =>
    fetch(`/api/v1/projects/${pid}/snapshots/${sid}/files/${fid}`).then(unwrap<FileDetail>),
};

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
