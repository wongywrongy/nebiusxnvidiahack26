import React from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'
import App from './App'
import Memo from './Memo'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    {location.pathname.startsWith('/memo/') ? <Memo runId={decodeURIComponent(location.pathname.slice(6))} /> : <App />}
  </React.StrictMode>,
)
