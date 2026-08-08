import { useState } from 'react'
import type { AnalysisResult } from './types'
import DefectForm from './components/DefectForm'
import AnalysisResultComponent from './components/AnalysisResult'
import './App.css'

function App() {
  const [result, setResult] = useState<AnalysisResult | null>(null)

  const handleResult = (r: AnalysisResult) => {
    setResult(r)
    setTimeout(() => {
      document.getElementById('analysis-result')?.scrollIntoView({ behavior: 'smooth' })
    }, 50)
  }

  return (
    <>
      <header className="app-header">
        <h1 className="app-title">FieldIQ</h1>
        <p className="app-subtitle">Building Defect Intelligence Assistant</p>
      </header>
      <main className="app-main">
        <DefectForm onResult={handleResult} />
        {result && (
          <section id="analysis-result">
            <AnalysisResultComponent result={result} />
          </section>
        )}
      </main>
      <footer className="app-footer">
        <p>FieldIQ MVP — RAG-grounded defect analysis</p>
      </footer>
    </>

  )
}

export default App
