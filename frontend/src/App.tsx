import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router-dom'
import ConsentPage from './components/ConsentPage/ConsentPage'
import PlanPage from './components/PlanPage/PlanPage'
import { Spinner } from './components/ui'

// The dashboard pulls in Recharts; the phone-facing pages must stay light for mobile data.
const Dashboard = lazy(() => import('./components/Dashboard'))

export default function App() {
  return (
    <Routes>
      <Route path="/consent/:sessionId" element={<ConsentPage />} />
      <Route path="/plan/:applicationId" element={<PlanPage />} />
      <Route path="*" element={<Suspense fallback={<div className="grid h-full place-items-center"><Spinner className="h-6 w-6" /></div>}><Dashboard /></Suspense>} />
    </Routes>
  )
}
