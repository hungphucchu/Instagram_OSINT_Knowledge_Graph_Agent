export type QueryApiResponse = {
  answer: string;
  citations: Array<{ doc_id: string; snippet: string }>;
  latency_ms: number;
  cypher?: string;
  query_id?: string;
  warnings: string[];
};

export type PipelineSampleResponse = {
  run_id: string;
  raw_artifacts: number;
  extraction_records: number;
  dedup_clusters: number;
};

export type GraphStatsResponse = {
  version: string;
  nodes: number;
  edges: number;
};

export type NamedCount = {
  name: string;
  count: number;
};

export type PipelineFullResponse = {
  run_id: string;
  last_step?: string | null;
  succeeded: boolean;
  collection_mode: string;
  source_path: string;
  collection: Record<string, unknown>;
  extraction: Record<string, unknown>;
  dedup: Record<string, unknown>;
  graph_insert: Record<string, unknown>;
  quality: Record<string, unknown>;
};

export type GraphEntityRow = {
  node_id: string;
  display_name: string;
  entity_kind: string;
  alias_count: number;
  mention_count: number;
  source_run_id?: string | null;
};

export type GraphRelationshipRow = {
  rel_type: string;
  source_id: string;
  source_display: string;
  source_labels: string[];
  target_id: string;
  target_display: string;
  target_labels: string[];
  artifact_id?: string | null;
  confidence?: number | null;
};

export type GraphOverviewResponse = GraphStatsResponse & {
  node_labels: NamedCount[];
  relationship_types: NamedCount[];
  entities: GraphEntityRow[];
  relationships: GraphRelationshipRow[];
};
