import React from 'react'
import ReactDOM from 'react-dom/client'
import { ClerkProvider } from '@clerk/clerk-react'
import App from './App'
import './index.css'
const KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY || 'pk_test_placeholder'
ReactDOM.createRoot(document.getElementById('root')).render(
  <ClerkProvider publishableKey={KEY}><App /></ClerkProvider>
)
