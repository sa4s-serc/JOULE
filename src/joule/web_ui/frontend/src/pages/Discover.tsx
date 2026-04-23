import { useState } from 'react'
import { Search, Code, TestTube, Wrench, Play } from 'lucide-react'

interface Target {
  qualname: string
  file_path: string
  line_number: number
  function_type: 'function' | 'method' | 'async_function' | 'async_method'
}

interface Workload {
  id: string
  kind: 'test' | 'property' | 'harness' | 'default'
  description: string
  file_path?: string
  node_id?: string
}

export default function Discover() {
  const [selectedTarget, setSelectedTarget] = useState<Target | null>(null)
  const [selectedWorkloads, setSelectedWorkloads] = useState<Set<string>>(new Set())
  const [searchTerm, setSearchTerm] = useState('')

  const mockTargets: Target[] = [
    {
      qualname: 'example.process_data',
      file_path: 'example/main.py',
      line_number: 42,
      function_type: 'function',
    },
    {
      qualname: 'ExampleClass.analyze',
      file_path: 'example/models.py',
      line_number: 15,
      function_type: 'method',
    },
    {
      qualname: 'utils.async_transform',
      file_path: 'utils/helpers.py',
      line_number: 88,
      function_type: 'async_function',
    },
  ]

  const mockWorkloads: Workload[] = [
    {
      id: 'test_process_data',
      kind: 'test',
      description: 'Test the process_data function',
      file_path: 'tests/test_main.py',
      node_id: 'test_process_data',
    },
    {
      id: 'property_data_integrity',
      kind: 'property',
      description: 'Data integrity property',
      file_path: 'tests/properties.py',
      node_id: 'test_data_integrity',
    },
    {
      id: 'harness_full_pipeline',
      kind: 'harness',
      description: 'Full pipeline test harness',
      file_path: 'tests/harness.py',
      node_id: 'run_full_pipeline',
    },
  ]

  const filteredTargets = mockTargets.filter(target =>
    target.qualname.toLowerCase().includes(searchTerm.toLowerCase()) ||
    target.file_path.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const toggleWorkload = (workloadId: string) => {
    const newSelection = new Set(selectedWorkloads)
    if (newSelection.has(workloadId)) {
      newSelection.delete(workloadId)
    } else {
      newSelection.add(workloadId)
    }
    setSelectedWorkloads(newSelection)
  }

  const getWorkloadIcon = (kind: Workload['kind']) => {
    switch (kind) {
      case 'test': return TestTube
      case 'property': return Code
      case 'harness': return Wrench
      default: return Play
    }
  }

  const getFunctionTypeColor = (type: Target['function_type']) => {
    switch (type) {
      case 'function': return 'text-blue-600'
      case 'method': return 'text-green-600'
      case 'async_function': return 'text-purple-600'
      case 'async_method': return 'text-pink-600'
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-joule-ink">Discover Targets</h1>
        <p className="text-joule-muted mt-2">
          Find optimization targets and select workloads for measurement
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Targets Panel */}
        <div className="joule-panel">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold text-joule-ink">Targets</h2>
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-1/2 transform -translate-y-1/2 text-joule-muted" />
              <input
                type="text"
                placeholder="Search targets..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10 pr-4 py-2 border border-joule-border rounded-lg focus:outline-none focus:ring-2 focus:ring-joule-accent"
              />
            </div>
          </div>

          <div className="space-y-3">
            {filteredTargets.map((target) => (
              <div
                key={target.qualname}
                onClick={() => setSelectedTarget(target)}
                className={`p-4 rounded-lg border cursor-pointer transition-colors duration-200 ${
                  selectedTarget?.qualname === target.qualname
                    ? 'border-joule-accent bg-joule-chip'
                    : 'border-joule-border hover:bg-joule-bg'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <h3 className="font-medium text-joule-ink">
                      {target.qualname}
                    </h3>
                    <p className="text-sm text-joule-muted font-mono mt-1">
                      {target.file_path}:{target.line_number}
                    </p>
                  </div>
                  <span className={`text-xs font-medium ${getFunctionTypeColor(target.function_type)}`}>
                    {target.function_type.replace('_', ' ')}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Workloads Panel */}
        <div className="joule-panel">
          <h2 className="text-xl font-semibold text-joule-ink mb-6">Workloads</h2>
          
          {!selectedTarget ? (
            <div className="text-center py-8">
              <Search className="w-12 h-12 text-joule-muted mx-auto mb-4" />
              <p className="text-joule-muted">
                Select a target to view available workloads
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {mockWorkloads.map((workload) => {
                const Icon = getWorkloadIcon(workload.kind)
                const isSelected = selectedWorkloads.has(workload.id)

                return (
                  <div
                    key={workload.id}
                    onClick={() => toggleWorkload(workload.id)}
                    className={`p-4 rounded-lg border cursor-pointer transition-colors duration-200 ${
                      isSelected
                        ? 'border-joule-accent bg-joule-chip'
                        : 'border-joule-border hover:bg-joule-bg'
                    }`}
                  >
                    <div className="flex items-start">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => {}}
                        className="mt-1 mr-3"
                      />
                      <div className="flex-1">
                        <div className="flex items-center">
                          <Icon className="w-4 h-4 text-joule-accent mr-2" />
                          <h3 className="font-medium text-joule-ink">
                            {workload.id}
                          </h3>
                          <span className="ml-2 joule-chip text-xs">
                            {workload.kind}
                          </span>
                        </div>
                        <p className="text-sm text-joule-muted mt-1">
                          {workload.description}
                        </p>
                        {workload.file_path && (
                          <p className="text-xs text-joule-muted font-mono mt-1">
                            {workload.file_path}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>

      {/* Actions */}
      {selectedTarget && (
        <div className="joule-panel">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-semibold text-joule-ink">
                Selected Target: {selectedTarget.qualname}
              </h3>
              <p className="text-sm text-joule-muted">
                {selectedWorkloads.size} workload(s) selected
              </p>
            </div>
            <div className="flex space-x-3">
              <button
                className="joule-button joule-button-secondary"
                disabled={selectedWorkloads.size === 0}
              >
                Run Baseline
              </button>
              <button
                className="joule-button joule-button-primary"
                disabled={selectedWorkloads.size === 0}
              >
                Start Optimization
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
