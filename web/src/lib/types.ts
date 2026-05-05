export type QueryApiResponse = {
  queryId: string;
  answer: string;
  evidenceRows: number;
  evidence: Array<Record<string, unknown>>;
  cypher?: string;
  warnings: string[];
  rawOutput: string;
};

export type AgentRunRequest = {
  command: "pipeline" | "collect" | "extract" | "dedup" | "graph-insert" | "quality" | "query";
  runId?: string;
  maxItems?: number;
  usernames?: string[];
  question?: string;
  showCypher?: boolean;
};

export type AgentRunResponse = {
  ok: boolean;
  command: string;
  stdout: string;
  stderr: string;
  exitCode: number;
};
