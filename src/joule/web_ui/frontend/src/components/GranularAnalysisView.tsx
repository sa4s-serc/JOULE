import { useState } from 'react'
import { ChevronDown, ChevronRight, Clock, FileCode, Hash, Layers, MemoryStick, Target } from 'lucide-react'
import type { BlockMetrics, GranularAnalysis, LineMetrics } from '../types'

interface GranularAnalysisViewProps {
  analysis: GranularAnalysis
}

const blockTypeConfig: Record<string, { icon: typeof Layers; label: string; color: string; bgColor: string }> = {
  for_loop: { icon: Layers, label: 'For Loop', color: 'text-blue-600', bgColor: 'bg-blue-50' },
  while_loop: { icon: Layers, label: 'While Loop', color: 'text-blue-600', bgColor: 'bg-blue-50' },
  if_branch: { icon: Target, label: 'If Branch', color: 'text-amber-600', bgColor: 'bg-amber-50' },
  elif_branch: { icon: Target, label: 'Elif Branch', color: 'text-amber-600', bgColor: 'bg-amber-50' },
  else_branch: { icon: Target, label: 'Else Branch', color: 'text-amber-600', bgColor: 'bg-amber-50' },
  function_call: { icon: FileCode, label: 'Function Call', color: 'text-purple-600', bgColor: 'bg-purple-50' },
  list_comprehension: { icon: Layers, label: 'List Comprehension', color: 'text-green-600', bgColor: 'bg-green-50' },
  dict_comprehension: { icon: Layers, label: 'Dict Comprehension', color: 'text-green-600', bgColor: 'bg-green-50' },
  set_comprehension: { icon: Layers, label: 'Set Comprehension', color: 'text-green-600', bgColor: 'bg-green-50' },
  generator_expression: { icon: Layers, label: 'Generator Expression', color: 'text-green-600', bgColor: 'bg-green-50' },
  assignment: { icon: FileCode, label: 'Assignment', color: 'text-gray-600', bgColor: 'bg-gray-50' },
  augmented_assignment: { icon: FileCode, label: 'Augmented Assignment', color: 'text-gray-600', bgColor: 'bg-gray-50' },
}

function getBlockConfig(type: string) {
  return blockTypeConfig[type] || { icon: FileCode, label: type.replace(/_/g, ' '), color: 'text-gray-600', bgColor: 'bg-gray-50' }
}

function BlockRow({ block, isExpanded, onToggle }: { block: BlockMetrics; isExpanded: boolean; onToggle: () => void }) {
  const config = getBlockConfig(block.type)
  const Icon = config.icon
  const sharePercent = (block.share_of_function * 100).toFixed(1)
  const hasMemory = block.memory && block.memory.peak_memory_bytes > 0
  const hasLineDetails = block.line_details && block.line_details.length > 0

  // Calculate indentation based on nesting level
  const indentClass = block.nesting_level > 0 ? `ml-${Math.min(block.nesting_level * 4, 12)}` : ''

  return (
    <div className={`border border-joule-border rounded-lg overflow-hidden ${indentClass}`}>
      <button
        onClick={onToggle}
        className="w-full px-4 py-3 flex items-center gap-3 hover:bg-joule-bg transition-colors text-left"
      >
        {(hasMemory || hasLineDetails) && (
          isExpanded ? <ChevronDown className="w-4 h-4 text-joule-muted" /> : <ChevronRight className="w-4 h-4 text-joule-muted" />
        )}

        <div className={`p-1.5 rounded ${config.bgColor}`}>
          <Icon className={`w-4 h-4 ${config.color}`} />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-sm text-joule-ink truncate">{block.description}</span>
            <span className={`text-xs px-2 py-0.5 rounded ${config.bgColor} ${config.color}`}>
              {config.label}
            </span>
            {block.nesting_level > 0 && (
              <span className="text-xs text-joule-muted">
                Level {block.nesting_level}
              </span>
            )}
          </div>
          <div className="flex items-center gap-3 text-xs text-joule-muted mt-1">
            <span className="font-mono">Lines {block.line_range[0]}:{block.line_range[1]}</span>
            {block.workload_count > 1 && (
              <span>({block.workload_count} workloads)</span>
            )}
          </div>
        </div>

        <div className="text-right">
          <div className={`font-semibold ${parseFloat(sharePercent) > 30 ? 'text-red-600' : parseFloat(sharePercent) > 10 ? 'text-amber-600' : 'text-joule-ink'}`}>
            {sharePercent}%
          </div>
          <div className="text-xs text-joule-muted">{block.time_s.toFixed(4)}s</div>
        </div>
      </button>

      {isExpanded && (
        <div className="px-4 py-3 bg-joule-bg/50 border-t border-joule-border">
          {/* Metrics Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            <div className="bg-white p-2.5 rounded border border-joule-border">
              <div className="flex items-center gap-1.5 text-joule-muted text-xs mb-1">
                <Clock className="w-3 h-3" />
                Time/Hit
              </div>
              <div className="font-mono text-sm font-medium text-joule-ink">
                {block.time_per_hit_ms.toFixed(2)}ms
              </div>
            </div>
            <div className="bg-white p-2.5 rounded border border-joule-border">
              <div className="flex items-center gap-1.5 text-joule-muted text-xs mb-1">
                <Hash className="w-3 h-3" />
                Hits
              </div>
              <div className="font-mono text-sm font-medium text-joule-ink">
                {block.hits.toLocaleString()}
              </div>
            </div>
            <div className="bg-white p-2.5 rounded border border-joule-border">
              <div className="flex items-center gap-1.5 text-joule-muted text-xs mb-1">
                <Layers className="w-3 h-3" />
                Lines Covered
              </div>
              <div className="font-mono text-sm font-medium text-joule-ink">
                {block.lines_covered}
              </div>
            </div>
            {hasMemory && (
              <div className="bg-white p-2.5 rounded border border-joule-border">
                <div className="flex items-center gap-1.5 text-joule-muted text-xs mb-1">
                  <MemoryStick className="w-3 h-3" />
                  Peak Memory
                </div>
                <div className="font-mono text-sm font-medium text-joule-ink">
                  {(block.memory!.peak_memory_bytes / (1024 * 1024)).toFixed(2)} MiB
                </div>
              </div>
            )}
          </div>

          {/* Line Details Table */}
          {hasLineDetails && (
            <div className="mt-3">
              <h5 className="text-xs font-medium text-joule-muted uppercase tracking-wide mb-2">Line-Level Details</h5>
              <div className="bg-white rounded border border-joule-border overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-joule-bg">
                    <tr>
                      <th className="px-3 py-2 text-left text-xs font-medium text-joule-muted">Line</th>
                      <th className="px-3 py-2 text-right text-xs font-medium text-joule-muted">Hits</th>
                      <th className="px-3 py-2 text-right text-xs font-medium text-joule-muted">Time (s)</th>
                      <th className="px-3 py-2 text-right text-xs font-medium text-joule-muted">Time/Hit (ms)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-joule-border">
                    {block.line_details!.map((line, idx) => (
                      <LineMetricsRow key={idx} line={line} />
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Memory Details */}
          {hasMemory && (
            <div className="mt-3">
              <h5 className="text-xs font-medium text-joule-muted uppercase tracking-wide mb-2">Memory Details</h5>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                <div className="bg-white p-2 rounded border border-joule-border">
                  <div className="text-xs text-joule-muted">Total Allocations</div>
                  <div className="font-mono text-sm font-medium">{block.memory!.total_allocations.toLocaleString()}</div>
                </div>
                <div className="bg-white p-2 rounded border border-joule-border">
                  <div className="text-xs text-joule-muted">Allocation Count</div>
                  <div className="font-mono text-sm font-medium">{block.memory!.allocation_count.toLocaleString()}</div>
                </div>
                <div className="bg-white p-2 rounded border border-joule-border">
                  <div className="text-xs text-joule-muted">Free Count</div>
                  <div className="font-mono text-sm font-medium">{block.memory!.free_count.toLocaleString()}</div>
                </div>
                <div className="bg-white p-2 rounded border border-joule-border">
                  <div className="text-xs text-joule-muted">Net Bytes</div>
                  <div className="font-mono text-sm font-medium">
                    {(block.memory!.net_memory_bytes / 1024).toFixed(1)} KiB
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function LineMetricsRow({ line }: { line: LineMetrics }) {
  return (
    <tr className="hover:bg-joule-bg/50">
      <td className="px-3 py-2 font-mono text-xs text-joule-muted">{line.line}</td>
      <td className="px-3 py-2 text-right font-mono text-xs">{line.hits.toLocaleString()}</td>
      <td className="px-3 py-2 text-right font-mono text-xs">{line.time_s.toFixed(6)}</td>
      <td className="px-3 py-2 text-right font-mono text-xs">{line.time_per_hit_ms.toFixed(4)}</td>
    </tr>
  )
}

export function GranularAnalysisView({ analysis }: GranularAnalysisViewProps) {
  const [expandedBlocks, setExpandedBlocks] = useState<Set<string>>(new Set())

  const toggleBlock = (blockId: string) => {
    const newSet = new Set(expandedBlocks)
    if (newSet.has(blockId)) {
      newSet.delete(blockId)
    } else {
      newSet.add(blockId)
    }
    setExpandedBlocks(newSet)
  }

  const { target_function, file, total_time_s, total_hits, workloads_profiled, code_blocks, profiler, profiler_available } = analysis

  return (
    <div className="space-y-6">
      {/* Header Info */}
      <div className="bg-joule-bg p-4 rounded-lg border border-joule-border">
        <div className="flex items-start justify-between flex-wrap gap-4">
          <div>
            <h3 className="font-semibold text-joule-ink flex items-center gap-2">
              <FileCode className="w-5 h-5 text-joule-accent" />
              {target_function}
            </h3>
            <p className="text-sm text-joule-muted font-mono mt-1">{file}</p>
            <p className="text-sm text-joule-muted mt-1">
              Lines {analysis.line_range[0]}:{analysis.line_range[1]}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right">
              <div className="text-sm font-medium text-joule-ink">{total_time_s.toFixed(4)}s</div>
              <div className="text-xs text-joule-muted">Total time</div>
            </div>
            <div className="text-right">
              <div className="text-sm font-medium text-joule-ink">{total_hits.toLocaleString()}</div>
              <div className="text-xs text-joule-muted">Total hits</div>
            </div>
            <div className="text-right">
              <div className="text-sm font-medium text-joule-ink">{workloads_profiled}</div>
              <div className="text-xs text-joule-muted">Workloads</div>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 mt-4 text-xs">
          <span className={`px-2 py-1 rounded ${profiler_available ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'}`}>
            {profiler_available ? '✓' : '⚠'} {profiler}
          </span>
          {analysis.memory_profiled && (
            <span className="px-2 py-1 rounded bg-purple-100 text-purple-700">
              <MemoryStick className="w-3 h-3 inline mr-1" />
              Memory profiled
            </span>
          )}
        </div>

        {analysis.ast_error && (
          <div className="mt-3 p-3 bg-amber-50 border border-amber-200 rounded text-sm text-amber-800">
            <strong>AST Analysis Error:</strong> {analysis.ast_error}
          </div>
        )}
        {analysis.memory_error && (
          <div className="mt-3 p-3 bg-amber-50 border border-amber-200 rounded text-sm text-amber-800">
            <strong>Memory Profiling Error:</strong> {analysis.memory_error}
          </div>
        )}
      </div>

      {/* Code Blocks */}
      <div className="space-y-3">
        <h4 className="font-medium text-joule-ink flex items-center gap-2">
          <Layers className="w-4 h-4" />
          Code Blocks ({code_blocks.length})
        </h4>
        {code_blocks.map((block) => (
          <BlockRow
            key={block.block_id}
            block={block}
            isExpanded={expandedBlocks.has(block.block_id)}
            onToggle={() => toggleBlock(block.block_id)}
          />
        ))}
      </div>
    </div>
  )
}
