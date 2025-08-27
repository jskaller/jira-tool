import React from 'react'
import ReactDOM from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import './index.css'
import App from './App'
import Login from './pages/Login'
import Admin from './pages/Admin'
import Reports from './pages/Reports'
import ReportDetail from './pages/ReportDetail'

const router = createBrowserRouter([
  { path: '/', element: <App />,
    children: [
      { index: true, element: <Reports /> },
      { path: 'admin', element: <Admin /> },
      { path: 'reports/:id', element: <ReportDetail /> },
      { path: 'login', element: <Login /> },
    ]
  }
])

const qc = new QueryClient()
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </React.StrictMode>
)
