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

// Signal quality with detailed metrics
export interface SignalQuality {
  total_cumulative_time_s: number;
  project_cumulative_time_s: number;
  target_cumulative_time_s: number;
  project_share: number;
  target_share: number;
  low_signal: boolean;
  low_signal_reasons: string[];
  dominant_ownership_bucket: string | null;
}

// Line-level metrics
export interface LineMetrics {
  line: number;
  hits: number;
  time_s: number;
  time_per_hit_ms: number;
}

// Memory profiling metrics
export interface MemoryMetrics {
  peak_memory_bytes: number;
  total_allocations: number;
  allocation_count: number;
  free_count: number;
  net_memory_bytes: number;
  memory_min_bytes: number;
  memory_max_bytes: number;
  workload_count: number;
}

// Code block (loop, branch, etc.) metrics
export interface BlockMetrics {
  block_id: string;
  type: string;
  line_range: [number, number];
  description: string;
  nesting_level: number;
  parent_block_id: string | null;
  child_block_ids: string[];
  hits: number;
  time_s: number;
  time_per_hit_ms: number;
  share_of_function: number;
  workload_count: number;
  time_min_s: number;
  time_max_s: number;
  memory?: MemoryMetrics;
  lines_covered: number;
  line_details?: LineMetrics[];
}

// Structured insight record
export interface InsightRecord {
  kind: 'critical_hotspot' | 'hotspot' | 'loop_dominant' | 'high_complexity' | 'deep_nesting' | 'comprehension_usage' | 'memory_hotspot' | 'high_allocation_rate' | 'memory_intensive' | string;
  severity: 'critical' | 'warning' | 'info';
  message: string;
  evidence?: Record<string, any>;
  line_range?: [number, number];
  block_type?: string;
  block_id?: string;
}

// Per-workload signal metrics
export interface WorkloadSignal {
  workload_id: string;
  workload_kind: string;
  workload_label: string;
  workload_selector: string;
  project_share: number;
  target_share: number;
  dominant_ownership_bucket: string;
  total_cumulative_time_s: number;
  low_signal: boolean;
  success: boolean;
  stderr?: string;
}

// Granular analysis for a target function
export interface GranularAnalysis {
  target_function: string;
  file: string;
  line_range: [number, number];
  total_time_s: number;
  total_hits: number;
  workloads_profiled: number;
  code_blocks: BlockMetrics[];
  insights: InsightRecord[];
  raw_line_count: number;
  raw_line_metrics?: LineMetrics[];
  timer_unit_s: number;
  profiler: string;
  profiler_available: boolean;
  peak_memory_bytes?: number;
  total_allocations?: number;
  memory_profiler?: string;
  memory_profiled?: boolean;
  ast_error?: string;
  memory_error?: string;
}

// Harness/external code summary
export interface HarnessSummary {
  total_time_s: number;
  share: number;
  top_calls: Array<{
    function: string;
    file: string;
    time_s: number;
    calls: number;
  }>;
  total_external_functions: number;
}

// Ownership bucket data
export interface OwnershipBucket {
  bucket: string;
  cumulative_time_s: number;
}

// Enhanced Hotspot Analysis
export interface HotspotAnalysis {
  schema_version?: number;
  signal_quality?: SignalQuality;
  by_workload?: WorkloadSignal[];
  primary_target_hotspot?: {
    file: string;
    line: number;
    function: string;
    share: number;
  };
  recommendations?: string[];
  // Backend sends these as top_functions/target_top_functions
  top_functions?: HotspotFunction[];
  target_top_functions?: HotspotFunction[];
  // Legacy field names (for backward compatibility)
  overall_hotspots?: HotspotFunction[];
  target_hotspots?: HotspotFunction[];
  // Stats for v1 format
  stats?: HotspotFunction[];
  project_top_functions?: HotspotFunction[];
  non_project_top_functions?: HotspotFunction[];
  ownership?: OwnershipBucket[];
  workload_kind_counts?: Record<string, number>;
  harness_summary?: HarnessSummary;
  granular_analysis?: GranularAnalysis;
  insights?: {
    profiled_workload_count?: number;
    strongest_signal_workload?: {
      workload_id: string;
      workload_kind: string;
      project_share: number;
      target_share: number;
    };
    weakest_signal_workload?: {
      workload_id: string;
      workload_kind: string;
      project_share: number;
      target_share: number;
    };
  };
  profiler_capability?: {
    function_level: boolean;
    granular_level: boolean;
    line_profiler_available: boolean;
  };
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
  granular_profiling: boolean;
  memory_profiling: boolean;
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
