import { useState } from 'react'
import { CheckCircle, XCircle, AlertCircle, GitBranch, Save, Eye, Download } from 'lucide-react'

interface Candidate {
  candidate_id: string
  run_id: string
  operator_name: string
  operator_tier: string
  status: 'accepted' | 'rejected' | 'pending'
  improvements?: {
    energy_ratio: number
    time_ratio: number
    memory_ratio: number
  }
  explanation?: string
  patch_content?: string
  source_content?: string
  dependency_policy_state?: string
}

export default function Apply() {
  const [selectedRun, setSelectedRun] = useState<string>('')
  const [selectedCandidate, setSelectedCandidate] = useState<string>('')
  const [applyConfig, setApplyConfig] = useState({
    branch: true,
    commit: false,
    create_backup: true,
  })
  const [isApplying, setIsApplying] = useState(false)
  const [showPreview, setShowPreview] = useState(false)

  const mockRuns = [
    { run_id: 'run_20240423_001', target: 'example.process_data', accepted_count: 2 },
    { run_id: 'run_20240422_003', target: 'utils.async_transform', accepted_count: 1 },
  ]

  const mockCandidates: Candidate[] = [
    {
      candidate_id: 'candidate_001',
      run_id: 'run_20240423_001',
      operator_name: 'loop_membership_set_cache',
      operator_tier: 'tier_1',
      status: 'accepted',
      improvements: {
        energy_ratio: 0.86,
        time_ratio: 0.86,
        memory_ratio: 0.94,
      },
      explanation: 'Optimized loop membership checks using set cache',
      dependency_policy_state: 'ready_to_apply',
      patch_content: `--- a/example/main.py
+++ b/example/main.py
@@ -39,7 +39,7 @@ def process_data(data):
     for item in data:
         if item in valid_items:
-            processed.append(item)
+            processed.append(item)  # Cached lookup
     return processed`,
    },
    {
      candidate_id: 'candidate_002',
      run_id: 'run_20240423_001',
      operator_name: 'list_comprehension_transform',
      operator_tier: 'tier_2',
      status: 'accepted',
      improvements: {
        energy_ratio: 0.92,
        time_ratio: 0.89,
        memory_ratio: 1.02,
      },
      explanation: 'Transformed nested loops to list comprehension',
      dependency_policy_state: 'ready_to_apply',
    },
  ]

  const availableCandidates = selectedRun
    ? mockCandidates.filter(c => c.run_id === selectedRun && c.status === 'accepted')
    : []

  const selectedCandidateData = availableCandidates.find(c => c.candidate_id === selectedCandidate)

  const formatImprovement = (ratio: number) => {
    const improvement = (1 - ratio) * 100
    const sign = improvement > 0 ? '-' : '+'
    return `${sign}${Math.abs(improvement).toFixed(1)}%`
  }

  const handleApply = () => {
    setIsApplying(true)
    // Simulate application process
    setTimeout(() => {
      setIsApplying(false)
      alert('Candidate applied successfully!')
    }, 3000)
  }

  const getPolicyStatus = (state?: string) => {
    switch (state) {
      case 'ready_to_apply':
        return {
          icon: CheckCircle,
          text: 'Ready to Apply',
          className: 'text-green-600',
        }
      case 'dependency_conflict':
        return {
          icon: XCircle,
          text: 'Dependency Conflict',
          className: 'text-red-600',
        }
      case 'needs_review':
        return {
          icon: AlertCircle,
          text: 'Needs Review',
          className: 'text-yellow-600',
        }
      default:
        return {
          icon: AlertCircle,
          text: 'Unknown Status',
          className: 'text-gray-600',
        }
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-joule-ink">Apply Candidate</h1>
        <p className="text-joule-muted mt-2">
          Review and apply optimization candidates to your codebase
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Selection Panel */}
        <div className="space-y-6">
          {/* Run Selection */}
          <div className="joule-panel">
            <h2 className="text-xl font-semibold text-joule-ink mb-4">Select Run</h2>
            <div className="space-y-3">
              {mockRuns.map((run) => (
                <label
                  key={run.run_id}
                  className="flex items-center p-3 border border-joule-border rounded-lg cursor-pointer hover:bg-joule-bg"
                >
                  <input
                    type="radio"
                    name="run"
                    value={run.run_id}
                    checked={selectedRun === run.run_id}
                    onChange={(e) => {
                      setSelectedRun(e.target.value)
                      setSelectedCandidate('')
                    }}
                    className="mr-3"
                  />
                  <div className="flex-1">
                    <div className="font-medium text-joule-ink">{run.run_id}</div>
                    <div className="text-sm text-joule-muted">
                      {run.target} • {run.accepted_count} accepted candidates
                    </div>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* Candidate Selection */}
          {selectedRun && (
            <div className="joule-panel">
              <h2 className="text-xl font-semibold text-joule-ink mb-4">Select Candidate</h2>
              <div className="space-y-3">
                {availableCandidates.length === 0 ? (
                  <p className="text-joule-muted">No accepted candidates found</p>
                ) : (
                  availableCandidates.map((candidate) => (
                    <label
                      key={candidate.candidate_id}
                      className="flex items-center p-3 border border-joule-border rounded-lg cursor-pointer hover:bg-joule-bg"
                    >
                      <input
                        type="radio"
                        name="candidate"
                        value={candidate.candidate_id}
                        checked={selectedCandidate === candidate.candidate_id}
                        onChange={(e) => setSelectedCandidate(e.target.value)}
                        className="mr-3"
                      />
                      <div className="flex-1">
                        <div className="font-medium text-joule-ink">{candidate.candidate_id}</div>
                        <div className="text-sm text-joule-muted">
                          {candidate.operator_name} • {candidate.operator_tier}
                        </div>
                        {candidate.improvements && (
                          <div className="text-sm text-green-600 mt-1">
                            Energy: {formatImprovement(candidate.improvements.energy_ratio)} • 
                            Time: {formatImprovement(candidate.improvements.time_ratio)}
                          </div>
                        )}
                      </div>
                    </label>
                  ))
                )}
              </div>
            </div>
          )}

          {/* Apply Configuration */}
          {selectedCandidate && (
            <div className="joule-panel">
              <h2 className="text-xl font-semibold text-joule-ink mb-4">Apply Configuration</h2>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium text-joule-ink flex items-center">
                    <GitBranch className="w-4 h-4 mr-2" />
                    Create Branch
                  </label>
                  <button
                    type="button"
                    onClick={() => setApplyConfig({ ...applyConfig, branch: !applyConfig.branch })}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                      applyConfig.branch ? 'bg-joule-accent' : 'bg-joule-border'
                    }`}
                  >
                    <span
                      className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                        applyConfig.branch ? 'translate-x-6' : 'translate-x-1'
                      }`}
                    />
                  </button>
                </div>

                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium text-joule-ink flex items-center">
                    <Save className="w-4 h-4 mr-2" />
                    Commit Changes
                  </label>
                  <button
                    type="button"
                    onClick={() => setApplyConfig({ ...applyConfig, commit: !applyConfig.commit })}
                    disabled={!applyConfig.branch}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                      applyConfig.commit ? 'bg-joule-accent' : 'bg-joule-border'
                    } ${!applyConfig.branch ? 'opacity-50' : ''}`}
                  >
                    <span
                      className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                        applyConfig.commit ? 'translate-x-6' : 'translate-x-1'
                      }`}
                    />
                  </button>
                </div>

                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium text-joule-ink">
                    Create Backup
                  </label>
                  <button
                    type="button"
                    onClick={() => setApplyConfig({ ...applyConfig, create_backup: !applyConfig.create_backup })}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                      applyConfig.create_backup ? 'bg-joule-accent' : 'bg-joule-border'
                    }`}
                  >
                    <span
                      className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                        applyConfig.create_backup ? 'translate-x-6' : 'translate-x-1'
                      }`}
                    />
                  </button>
                </div>
              </div>

              <button
                onClick={handleApply}
                disabled={isApplying}
                className="w-full mt-6 joule-button joule-button-primary flex items-center justify-center"
              >
                {isApplying ? (
                  'Applying...'
                ) : (
                  'Apply Candidate'
                )}
              </button>
            </div>
          )}
        </div>

        {/* Preview Panel */}
        <div className="space-y-6">
          {selectedCandidateData && (
            <>
              {/* Candidate Details */}
              <div className="joule-panel">
                <h2 className="text-xl font-semibold text-joule-ink mb-4">Candidate Details</h2>
                <div className="space-y-4">
                  <div>
                    <h3 className="font-medium text-joule-ink mb-2">Operator</h3>
                    <p className="text-sm text-joule-muted">{selectedCandidateData.operator_name}</p>
                    <span className="joule-chip">{selectedCandidateData.operator_tier}</span>
                  </div>

                  <div>
                    <h3 className="font-medium text-joule-ink mb-2">Explanation</h3>
                    <p className="text-sm text-joule-muted">{selectedCandidateData.explanation}</p>
                  </div>

                  {selectedCandidateData.improvements && (
                    <div>
                      <h3 className="font-medium text-joule-ink mb-2">Improvements</h3>
                      <div className="grid grid-cols-3 gap-3 text-sm">
                        <div className="p-2 bg-joule-bg rounded">
                          <div className="text-joule-muted">Energy</div>
                          <div className="font-medium text-green-600">
                            {formatImprovement(selectedCandidateData.improvements.energy_ratio)}
                          </div>
                        </div>
                        <div className="p-2 bg-joule-bg rounded">
                          <div className="text-joule-muted">Time</div>
                          <div className="font-medium text-green-600">
                            {formatImprovement(selectedCandidateData.improvements.time_ratio)}
                          </div>
                        </div>
                        <div className="p-2 bg-joule-bg rounded">
                          <div className="text-joule-muted">Memory</div>
                          <div className={`font-medium ${
                            selectedCandidateData.improvements.memory_ratio < 1 ? 'text-green-600' : 'text-red-600'
                          }`}>
                            {formatImprovement(selectedCandidateData.improvements.memory_ratio)}
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  <div>
                    <h3 className="font-medium text-joule-ink mb-2">Dependency Policy</h3>
                    {(() => {
                      const status = getPolicyStatus(selectedCandidateData.dependency_policy_state)
                      const StatusIcon = status.icon
                      return (
                        <div className="flex items-center">
                          <StatusIcon className={`w-4 h-4 mr-2 ${status.className}`} />
                          <span className={`text-sm ${status.className}`}>{status.text}</span>
                        </div>
                      )
                    })()}
                  </div>
                </div>
              </div>

              {/* Patch Preview */}
              {selectedCandidateData.patch_content && (
                <div className="joule-panel">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-xl font-semibold text-joule-ink">Patch Preview</h2>
                    <button
                      onClick={() => setShowPreview(!showPreview)}
                      className="joule-button joule-button-secondary text-sm flex items-center"
                    >
                      <Eye className="w-4 h-4 mr-2" />
                      {showPreview ? 'Hide' : 'Show'} Preview
                    </button>
                  </div>

                  {showPreview && (
                    <div className="bg-joule-bg rounded-lg p-4 overflow-x-auto">
                      <pre className="text-xs font-mono whitespace-pre">
                        {selectedCandidateData.patch_content}
                      </pre>
                    </div>
                  )}
                </div>
              )}

              {/* Actions */}
              <div className="joule-panel">
                <h2 className="text-xl font-semibold text-joule-ink mb-4">Actions</h2>
                <div className="space-y-3">
                  <button className="w-full joule-button joule-button-secondary flex items-center justify-center">
                    <Download className="w-4 h-4 mr-2" />
                    Download Patch
                  </button>
                  <button className="w-full joule-button joule-button-secondary flex items-center justify-center">
                    <Eye className="w-4 h-4 mr-2" />
                    View Full Source
                  </button>
                </div>
              </div>
            </>
          )}

          {!selectedCandidate && (
            <div className="joule-panel text-center py-12">
              <Eye className="w-12 h-12 text-joule-muted mx-auto mb-4" />
              <h3 className="text-lg font-medium text-joule-ink mb-2">
                No Candidate Selected
              </h3>
              <p className="text-joule-muted">
                Select a run and candidate to preview changes
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
