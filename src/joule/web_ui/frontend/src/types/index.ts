export interface Project {
  path: string;
  name: string;
  config?: JouleConfig;
  health?: ProjectHealth;
}

export interface JouleConfig {
  seed: number;
  artifact_dir: string;
  db_name: string;
  default_backend: string;
  baseline_repetitions: number;
  optimization_budget: number;
  hotspot_limit: number;
  dashboard_port: number;
  max_parallel_workers: number;
  terminal_verbosity: string;
  [key: string]: any;
}

export interface ProjectHealth {
  backend_available: boolean;
  backend_name: string;
  python_version: string;
  dependencies_ok: boolean;
  artifact_dir_exists: boolean;
  db_accessible: boolean;
  issues: string[];
}

export interface TargetSpec {
  qualname: string;
  file_path: string;
  line_number: number;
  function_type: 'function' | 'method' | 'async_function' | 'async_method';
}

export interface WorkloadSpec {
  id: string;
  kind: 'test' | 'property' | 'harness' | 'default';
  description: string;
  file_path?: string;
  node_id?: string;
}

export interface Run {
  run_id: string;
  run_type: 'baseline' | 'optimize' | 'resume';
  status: 'running' | 'completed' | 'failed' | 'cancelled';
  target_qualname: string;
  backend: string;
  created_at: string;
  completed_at?: string;
  metadata?: Record<string, any>;
}

export interface BaselineResult {
  run_id: string;
  target_qualname: string;
  measurements: {
    energy_j: number;
    wall_time_s: number;
    cpu_time_s: number;
    peak_memory_bytes: number;
  };
  repetitions: number;
  hotspots?: HotspotAnalysis;
}

export interface OptimizationResult {
  run_id: string;
  baseline: BaselineResult;
  candidates: Candidate[];
  best_candidate?: Candidate;
  funnel: FunnelAnalysis;
  optimization_analysis: OptimizationAnalysis;
}

export interface Candidate {
  candidate_id: string;
  operator_name: string;
  operator_tier: string;
  status: 'accepted' | 'rejected' | 'pending';
  measurements?: {
    energy_j: number;
    wall_time_s: number;
    cpu_time_s: number;
    peak_memory_bytes: number;
  };
  improvements?: {
    energy_ratio: number;
    time_ratio: number;
    memory_ratio: number;
  };
  metadata: Record<string, any>;
  patch_content?: string;
  source_content?: string;
  explanation?: string;
  rejection_reason?: string;
}

export interface HotspotAnalysis {
  signal_quality: {
    low_signal: boolean;
    project_share: number;
    target_share: number;
    dominant_ownership_bucket: string;
  };
  primary_target_hotspot?: {
    file: string;
    line: number;
    function: string;
    share: number;
  };
  recommendations: string[];
  overall_hotspots: HotspotFunction[];
  target_hotspots: HotspotFunction[];
}

export interface HotspotFunction {
  file: string;
  line: number;
  function: string;
  cumulative_time_s: number;
  share: number;
  owner?: string;
}

export interface FunnelAnalysis {
  total_candidates: number;
  accepted_count: number;
  rejected_count: number;
  pending_count: number;
  by_operator: Record<string, {
    total: number;
    accepted: number;
    rejected: number;
  }>;
}

export interface OptimizationAnalysis {
  schema_version: string;
  funnel: FunnelAnalysis;
  operator_analysis: Record<string, any>;
  hotspot_analysis: HotspotAnalysis;
  recommendations: string[];
}

export interface Artifact {
  name: string;
  path: string;
  size: number;
  created_at: string;
  content_type: string;
}

export interface WebSocketMessage {
  type: 'run_status' | 'progress' | 'candidate' | 'error' | 'log' | 'run_update';
  data: any;
  timestamp: string;
  run_id?: string;
}

export interface BaselineConfig {
  target: string;
  workloads: string[];
  backend: string;
  repetitions: number;
  hotspots: boolean;
  hotspot_limit: number;
  cache: boolean;
}

export interface OptimizationConfig {
  target: string;
  workloads: string[];
  backend: string;
  budget: number;
  analysis: boolean;
  cache: boolean;
  fresh_surrogate: boolean;
  parallel: number;
  improvement_threshold: number;
}

export interface ApplyConfig {
  run_id: string;
  candidate_id?: string;
  branch: boolean;
  commit_changes: boolean;
}
