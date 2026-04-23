import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Projects from './pages/Projects'
import Discover from './pages/Discover'
import Baseline from './pages/Baseline'
import Optimize from './pages/Optimize'
import Results from './pages/Results'
import Inspect from './pages/Inspect'
import Apply from './pages/Apply'
import NotFound from './pages/NotFound'
import { ErrorBoundary } from './components/ErrorBoundary'
import { ToastContainer } from './components/Toast'

function App() {
  return (
    <ErrorBoundary>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/projects" element={<Projects />} />
          <Route path="/discover" element={<Discover />} />
          <Route path="/baseline" element={<Baseline />} />
          <Route path="/optimize" element={<Optimize />} />
          <Route path="/results" element={<Results />} />
          <Route path="/inspect" element={<Results />} />
          <Route path="/inspect/:runId" element={<Inspect />} />
          <Route path="/apply" element={<Apply />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Layout>
      <ToastContainer />
    </ErrorBoundary>
  )
}

export default App
