import { useState, useEffect, useRef } from 'react'
import './App.css'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { Textarea } from '@/components/ui/textarea'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { AlertTriangle, Clock, Calendar, Archive, Mail, Plus, LogOut, Zap, RefreshCw, Trash2, Bot, Check, Clock3, Copy, X, LayoutGrid } from 'lucide-react'
import MorningBrief from './components/MorningBrief'
import EmailDetail from './components/EmailDetail'
import './components/EmailDetail.css'

// API URL - use environment variable or default to deployed backend
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// Log API URL for debugging
console.log('API_URL:', API_URL)
console.log('Environment:', import.meta.env.MODE)

type ZoneType = 'STAT' | 'TODAY' | 'THIS_WEEK' | 'LATER'

interface Message {
  id: string
  sender: string
  sender_domain: string
  subject: string
  snippet: string | null
  zone: ZoneType
  confidence: number
  reason: string
  jone5_message: string
  received_at: string
  classified_at: string
  corrected: boolean
  summary?: string | null
  recommended_action?: string | null
  action_type?: string | null
  draft_reply?: string | null
  llm_fallback?: boolean
  raw_body?: string | null  // Full email body content
  raw_body_html?: string | null  // Full HTML email content
}

interface User {
  id: string
  email: string
  name: string
  practice_name?: string
}

interface ZoneData {
  zones: Record<ZoneType, Message[]>
  counts: Record<ZoneType, number>
  total: number
}

interface ActionCenter {
  urgent_count: number
  needs_reply_count: number
  snoozed_due_count: number
  done_today: number
  total_action_items: number
  urgent_items: Message[]
  needs_reply: Message[]
  snoozed_due: Message[]
}

const zoneConfig: Record<ZoneType, { label: string; icon: React.ReactNode; color: string; pillBg: string }> = {
  STAT: { label: 'CRITICAL', icon: <AlertTriangle className="w-3 h-3" />, color: 'text-red-400', pillBg: 'bg-red-500/20 text-red-400 border-red-500/30' },
  TODAY: { label: 'HIGH', icon: <Clock className="w-3 h-3" />, color: 'text-orange-400', pillBg: 'bg-orange-500/20 text-orange-400 border-orange-500/30' },
  THIS_WEEK: { label: 'ROUTINE', icon: <Calendar className="w-3 h-3" />, color: 'text-blue-400', pillBg: 'bg-blue-500/20 text-blue-400 border-blue-500/30' },
  LATER: { label: 'FYI', icon: <Archive className="w-3 h-3" />, color: 'text-zinc-400', pillBg: 'bg-zinc-500/20 text-zinc-400 border-zinc-500/30' }
}

const asZoneType = (zone: unknown): ZoneType => {
  return zone === 'STAT' || zone === 'TODAY' || zone === 'THIS_WEEK' || zone === 'LATER' ? zone : 'LATER'
}

function App() {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [zoneData, setZoneData] = useState<ZoneData | null>(null)
  const [loading, setLoading] = useState(false)
  const [jone5Message, setJone5Message] = useState<string>('')
  const [isLoginMode, setIsLoginMode] = useState(true)
  const [loginForm, setLoginForm] = useState({ email: '', password: '', name: '', practice_name: '' })
  const [connectingEmail, setConnectingEmail] = useState<string | null>(null)
  const [connectedEmails, setConnectedEmails] = useState<string[]>([])
  const [ingestForm, setIngestForm] = useState({ sender: '', subject: '', snippet: '' })
  const [ingestOpen, setIngestOpen] = useState(false)
  const [viewMode, setViewMode] = useState<'inbox' | 'decision-deck'>('inbox')
  const [selectedMessage, setSelectedMessage] = useState<Message | null>(null)
  const [replyComposerOpen, setReplyComposerOpen] = useState(false)
  const [replyText, setReplyText] = useState('')
  const [fullEmailContent, setFullEmailContent] = useState<{raw_body?: string, raw_body_html?: string} | null>(null)
  const [showEmailDetail, setShowEmailDetail] = useState(false)
  const [newZone, setNewZone] = useState<ZoneType>('TODAY')
  const [actionCenter, setActionCenter] = useState<ActionCenter | null>(null)
  const [activeTab, setActiveTab] = useState<'all' | ZoneType>('all')
  const [providerBanner, setProviderBanner] = useState<{ variant: 'default' | 'destructive'; title: string; message: string } | null>(null)
  const refreshInFlight = useRef(false)

  useEffect(() => {
    // Test backend connection on load (non-blocking, just for logging)
    const testConnection = async () => {
      try {
        console.log('Testing backend connection to:', API_URL)
        const response = await fetch(`${API_URL}/health`, { 
          method: 'GET',
          headers: { 'Content-Type': 'application/json' },
          signal: AbortSignal.timeout(5000) // 5 second timeout
        })
        if (response.ok) {
          const data = await response.json()
          console.log('✅ Backend connection successful:', data)
        } else {
          console.warn('⚠️ Backend responded but with error:', response.status, response.statusText)
        }
      } catch (error) {
        // Don't block app - just log the error
        console.warn('⚠️ Backend health check failed (this is OK if backend is not deployed yet):', error)
      }
    }
    // Run in background, don't await
    testConnection().catch(() => {}) // Silently fail
    
    // Check for email verification and Nylas connection in URL
    const urlParams = new URLSearchParams(window.location.search)
    const verifySuccess = urlParams.get('verify_success')
    const verifyError = urlParams.get('verify_error')
    const nylasSuccess = urlParams.get('nylas_success')
    const nylasEmail = urlParams.get('email')
    const autoSync = urlParams.get('auto_sync')
    const nylasError = urlParams.get('nylas_error')
    
    if (verifySuccess === 'true') {
      setJone5Message("Email verified successfully! You can now log in.")
      window.history.replaceState({}, document.title, window.location.pathname)
    } else if (verifyError) {
      setJone5Message(`Verification failed: ${verifyError === 'invalid_token' ? 'Invalid or expired verification link' : 'Verification error'}`)
      window.history.replaceState({}, document.title, window.location.pathname)
    } else if (nylasSuccess === 'true' && nylasEmail) {
      setJone5Message(`${nylasEmail} connected${autoSync === 'true' ? ' and synced!' : '!'}`)
      setConnectedEmails(prev => [...prev, nylasEmail])
      if (token) {
        fetchMessages() // Refresh messages if logged in
      }
      window.history.replaceState({}, document.title, window.location.pathname)
    } else if (nylasError) {
      setJone5Message(`Email connection failed: ${decodeURIComponent(nylasError)}`)
      window.history.replaceState({}, document.title, window.location.pathname)
    }
    
    const savedToken = localStorage.getItem('docboxrx_token')
    const savedUser = localStorage.getItem('docboxrx_user')
    if (savedToken && savedUser) {
      setToken(savedToken)
      setUser(JSON.parse(savedUser))
    }
  }, [token])

  useEffect(() => {
    if (token) {
      fetchMessages()
      fetchActionCenter()
    }
  }, [token])

  // Auto-load full email content when message is selected (jukebox-style access)
  useEffect(() => {
    if (!selectedMessage || !token) {
      setFullEmailContent(null)
      return
    }

    // If we already have full content in the message, use it immediately (cached)
    if (selectedMessage.raw_body || selectedMessage.raw_body_html) {
      setFullEmailContent({
        raw_body: selectedMessage.raw_body || undefined,
        raw_body_html: selectedMessage.raw_body_html || undefined
      })
      return
    }

    // Otherwise, fetch full content from backend (on-demand jukebox access)
    const fetchFullContent = async () => {
      try {
        console.log('Fetching full email content for:', selectedMessage.id)
        const content = await apiCall(`/api/messages/${selectedMessage.id}/full`)
        if (content) {
          setFullEmailContent({
            raw_body: content.raw_body,
            raw_body_html: content.raw_body_html
          })
          console.log('Full email content loaded:', content.cached ? 'from cache' : 'from provider')
        }
      } catch (error) {
        console.error('Failed to fetch full email content:', error)
        // Fall back to snippet if fetch fails
        setFullEmailContent({
          raw_body: selectedMessage.snippet || undefined
        })
      }
    }

    fetchFullContent()
  }, [selectedMessage?.id, token])

  useEffect(() => {
    if (!token) return
    const tick = async () => {
      if (refreshInFlight.current) return
      if (typeof document !== 'undefined' && document.hidden) return
      refreshInFlight.current = true
      try {
        await fetchMessages({ silent: true })
        await fetchActionCenter()
      } finally {
        refreshInFlight.current = false
      }
    }
    const interval = window.setInterval(tick, 60000)
    return () => {
      window.clearInterval(interval)
      refreshInFlight.current = false
    }
  }, [token])

  useEffect(() => {
    if (zoneData && !selectedMessage) {
      const first = zoneData.zones.STAT?.[0] || zoneData.zones.TODAY?.[0] || zoneData.zones.THIS_WEEK?.[0] || zoneData.zones.LATER?.[0]
      if (first) setSelectedMessage(first)
    }
  }, [zoneData])

  const allMessages = zoneData ? [
    ...zoneData.zones.STAT,
    ...zoneData.zones.TODAY,
    ...zoneData.zones.THIS_WEEK,
    ...zoneData.zones.LATER
  ] : []

  const filteredMessages = activeTab === 'all' ? allMessages : (zoneData?.zones[activeTab] || [])

  const fetchActionCenter = async () => {
    try {
      const data = await apiCall('/api/action-center')
      if (data) setActionCenter(data)
    } catch (error) {
      console.error('Failed to fetch action center:', error)
    }
  }

  const applyProviderFeedback = (result: any, defaultMessage: string) => {
    if (!result || !result.success) return
    if (result.provider_synced) {
      setProviderBanner(null)
    } else if (result.provider_error) {
      setProviderBanner({
        variant: 'destructive',
        title: 'Mailbox Sync Failed',
        message: String(result.provider_error),
      })
    } else if (result.provider_message) {
      setProviderBanner({
        variant: 'default',
        title: 'Mailbox Sync Notice',
        message: String(result.provider_message),
      })
    } else {
      setProviderBanner(null)
    }
    setJone5Message(defaultMessage)
  }

  const handleMarkDone = async (messageId: string, e?: React.MouseEvent) => {
    e?.stopPropagation()
    try {
      const result = await apiCall(`/api/messages/${messageId}/status`, { method: 'POST', body: JSON.stringify({ status: 'done' }) })
      if (!result) return
      applyProviderFeedback(result, "Done! One less thing to worry about.")
      fetchMessages()
      fetchActionCenter()
    } catch (error) {
      alert(error instanceof Error ? error.message : 'Failed to mark as done')
    }
  }

  const handleArchive = async (messageId: string, e?: React.MouseEvent) => {
    e?.stopPropagation()
    try {
      const result = await apiCall(`/api/messages/${messageId}/status`, { method: 'POST', body: JSON.stringify({ status: 'archived' }) })
      if (!result) return
      applyProviderFeedback(result, "Archived!")
      fetchMessages()
      fetchActionCenter()
    } catch (error) {
      alert(error instanceof Error ? error.message : 'Failed to archive')
    }
  }

  const handleSnooze = async (messageId: string, hours: number, e?: React.MouseEvent) => {
    e?.stopPropagation()
    const snoozedUntil = new Date(Date.now() + hours * 60 * 60 * 1000).toISOString()
    try {
      const result = await apiCall(`/api/messages/${messageId}/status`, { method: 'POST', body: JSON.stringify({ status: 'snoozed', snoozed_until: snoozedUntil }) })
      if (!result) return
      applyProviderFeedback(result, `Snoozed for ${hours} hours.`)
      fetchMessages()
      fetchActionCenter()
    } catch (error) {
      alert(error instanceof Error ? error.message : 'Failed to snooze')
    }
  }

  const apiCall= async (endpoint: string, options: RequestInit = {}) => {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (token) headers['Authorization'] = `Bearer ${token}`
    const controller = new AbortController()
    // Increased timeout for registration (email sending can take time)
    const timeout = endpoint.includes('/register') ? 60000 : 30000
    const timeoutId = setTimeout(() => controller.abort(), timeout)
    try {
      const url = `${API_URL}${endpoint}`
      console.log(`API Call: ${options.method || 'GET'} ${url}`, { headers, body: options.body })
      const response = await fetch(url, { 
        ...options, 
        headers, 
        signal: controller.signal,
        mode: 'cors', // Explicitly set CORS mode
        credentials: 'omit' // Don't send credentials for CORS
      })
      clearTimeout(timeoutId)
      console.log(`API Response: ${response.status} ${response.statusText}`, response)
      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Request failed' }))
        if (response.status === 401 && token) {
          localStorage.removeItem('docboxrx_token')
          localStorage.removeItem('docboxrx_user')
          setToken(null)
          setUser(null)
          setZoneData(null)
          alert('Session expired. Please log in again.')
          return null
        }
        // Better error messages for 422 validation errors
        if (response.status === 422) {
          const errorMsg = error.detail || (Array.isArray(error.detail) 
            ? error.detail.map((e: any) => e.msg || e.message || JSON.stringify(e)).join(', ')
            : 'Validation error: Please check your input')
          throw new Error(errorMsg)
        }
        throw new Error(error.detail || error.message || `Request failed with status ${response.status}`)
      }
      return response.json()
    } catch (error) {
      clearTimeout(timeoutId)
      if (error instanceof Error && error.name === 'AbortError') {
        console.error('Request timed out:', endpoint)
        throw new Error('Request timed out. Please try again.')
      }
      console.error('API call error:', error, 'Endpoint:', endpoint, 'URL:', `${API_URL}${endpoint}`)
      if (error instanceof Error) {
        if (error.message.includes('Failed to fetch') || error.message.includes('NetworkError') || error.name === 'TypeError') {
          console.error('Connection error - possible causes:')
          console.error('1. Backend not running or not deployed')
          console.error('2. CORS issue (check browser console)')
          console.error('3. Network connectivity issue')
          console.error('4. Backend URL incorrect:', API_URL)
          console.error('Check Network tab (F12 → Network) to see the actual request')
          throw new Error(`Cannot connect to server at ${API_URL}. Please check if the backend is running and deployed.`)
        }
      }
      throw error
    }
  }

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    
    // Validate required fields
    if (!loginForm.email || !loginForm.password) {
      alert('Please enter both email and password')
      return
    }
    
    if (!isLoginMode && !loginForm.name) {
      alert('Please enter your name')
      return
    }
    
    // Basic email validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!emailRegex.test(loginForm.email)) {
      alert('Please enter a valid email address')
      return
    }
    
    setLoading(true)
    try {
      const endpoint = isLoginMode ? '/api/auth/login' : '/api/auth/register'
      const body = isLoginMode 
        ? { email: loginForm.email.trim(), password: loginForm.password } 
        : { 
            email: loginForm.email.trim(), 
            password: loginForm.password, 
            name: loginForm.name.trim(),
            practice_name: loginForm.practice_name?.trim() || undefined
          }
      console.log(`Attempting ${isLoginMode ? 'login' : 'registration'} for:`, loginForm.email.trim())
      const data = await apiCall(endpoint, { method: 'POST', body: JSON.stringify(body) })
      console.log(`${isLoginMode ? 'Login' : 'Registration'} response:`, data)
      
      if (data.requires_verification) {
        // Registration successful but needs email verification
        setJone5Message(data.message || "Registration successful! Please check your email to verify your account.")
        alert(data.message || "Registration successful! Please check your email and click the verification link to activate your account.")
        return
      }
      
      setToken(data.access_token)
      setUser(data.user)
      localStorage.setItem('docboxrx_token', data.access_token)
      localStorage.setItem('docboxrx_user', JSON.stringify(data.user))
      setJone5Message("Welcome! jonE5 is ready.")
    } catch (error) {
      console.error('Login error:', error)
      let errorMessage = 'Login failed'
      
      if (error instanceof Error) {
        errorMessage = error.message
        // Check for specific error types
        if (error.message.includes('403') || error.message.includes('not verified')) {
          errorMessage = 'Email not verified. Please check your email and click the verification link.'
        } else if (error.message.includes('401') || error.message.includes('Invalid')) {
          errorMessage = 'Invalid email or password. Please try again.'
        } else if (error.message.includes('timeout')) {
          errorMessage = 'Request timed out. Please check your connection and try again.'
        } else if (error.message.includes('Failed to fetch')) {
          errorMessage = 'Cannot connect to server. Please check if the backend is running.'
        }
      }
      
      alert(errorMessage)
      setJone5Message(`Login failed: ${errorMessage}`)
    } finally {
      setLoading(false)
    }
  }

  const handleLogout = () => {
    setToken(null)
    setUser(null)
    setZoneData(null)
    setProviderBanner(null)
    localStorage.removeItem('docboxrx_token')
    localStorage.removeItem('docboxrx_user')
  }

  const fetchMessages = async (options: { silent?: boolean } = {}) => {
    const silent = options.silent ?? false
    if (!silent) setLoading(true)
    try {
      const data = await apiCall('/api/messages/by-zone')
      if (data) setZoneData(data)
    } catch (error) {
      console.error('Failed to fetch messages:', error)
    } finally {
      if (!silent) setLoading(false)
    }
  }

  const [cloudOpen, setCloudOpen] = useState(false)
  const [cloudZoneData, setCloudZoneData] = useState<ZoneData | null>(null)

  const fetchCloudMessages = async () => {
    try {
      const data = await apiCall('/api/cloudmailin/messages')
      if (data) setCloudZoneData(data)
    } catch (error) {
      console.error('Failed to fetch cloudmailin messages:', error)
    }
  }

  const handleCloudAction = async (messageId: string, status: string) => {
    try {
      await apiCall(`/api/cloudmailin/messages/${messageId}/status`, { method: 'POST', body: JSON.stringify({ status }) })
      fetchCloudMessages()
      fetchMessages()
      fetchActionCenter()
    } catch (error) {
      alert(error instanceof Error ? error.message : 'Cloud action failed')
    }
  }

  const handleCloudDelete = async (messageId: string) => {
    if (!confirm('Delete this cloud message?')) return
    try {
      await apiCall(`/api/cloudmailin/messages/${messageId}`, { method: 'DELETE' })
      fetchCloudMessages()
      fetchMessages()
      fetchActionCenter()
    } catch (error) {
      alert(error instanceof Error ? error.message : 'Cloud delete failed')
    }
  }

  const handleIngest = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      const result = await apiCall('/api/messages/ingest', { method: 'POST', body: JSON.stringify(ingestForm) })
      setJone5Message(result.jone5_message)
      setIngestForm({ sender: '', subject: '', snippet: '' })
      setIngestOpen(false)
      fetchMessages()
    } catch (error) {
      alert(error instanceof Error ? error.message : 'Ingest failed')
    } finally {
      setLoading(false)
    }
  }

  const handleCorrection = async () => {
    if (!selectedMessage) return
    setLoading(true)
    try {
      const result = await apiCall('/api/messages/correct', { method: 'POST', body: JSON.stringify({ message_id: selectedMessage.id, new_zone: newZone }) })
      setJone5Message(result.jone5_response)
      fetchMessages()
    } catch (error) {
      alert(error instanceof Error ? error.message : 'Correction failed')
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (messageId: string) => {
    if (!confirm('Delete this message?')) return
    try {
      const result = await apiCall(`/api/messages/${messageId}`, { method: 'DELETE' })
      if (!result) return
      applyProviderFeedback(result, 'Message deleted.')
      if (selectedMessage?.id === messageId) setSelectedMessage(null)
      fetchMessages()
      fetchActionCenter()
    } catch (error) {
      alert(error instanceof Error ? error.message : 'Delete failed')
    }
  }

  const seedDemoData = async () => {
    setLoading(true)
    try {
      await apiCall('/api/demo/seed', { method: 'POST' })
      setJone5Message("Demo data loaded!")
      fetchMessages()
      fetchActionCenter()
    } catch (error) {
      alert(error instanceof Error ? error.message : 'Seed failed')
    } finally {
      setLoading(false)
    }
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
    setJone5Message("Copied to clipboard!")
  }

  // LOGIN SCREEN
  if (!user) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center p-4">
        <Card className="w-full max-w-md bg-zinc-900 border-zinc-800">
          <CardHeader className="text-center pb-4">
            <div className="w-16 h-16 bg-gradient-to-br from-emerald-500 to-teal-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
              <Bot className="w-9 h-9 text-white" />
            </div>
            <CardTitle className="text-2xl font-bold text-zinc-100">DocBoxRX</CardTitle>
            <CardDescription className="text-zinc-500">Medical Email Triage</CardDescription>
            <p className="text-xs text-emerald-500 mt-1">Powered by jonE5 AI Agent</p>
          </CardHeader>
          <CardContent>
            <Tabs value={isLoginMode ? 'login' : 'register'} onValueChange={(v) => setIsLoginMode(v === 'login')}>
              <TabsList className="grid w-full grid-cols-2 mb-6 bg-zinc-800">
                <TabsTrigger value="login" className="data-[state=active]:bg-emerald-600 text-zinc-400 data-[state=active]:text-white">Login</TabsTrigger>
                <TabsTrigger value="register" className="data-[state=active]:bg-emerald-600 text-zinc-400 data-[state=active]:text-white">Register</TabsTrigger>
              </TabsList>
              <form onSubmit={handleLogin} className="space-y-4">
                {!isLoginMode && (
                  <>
                    <div><Label className="text-zinc-400 text-sm">Name</Label><Input placeholder="Dr. Smith" value={loginForm.name} onChange={(e) => setLoginForm({ ...loginForm, name: e.target.value })} required={!isLoginMode} className="bg-zinc-800 border-zinc-700 text-zinc-100 mt-1" /></div>
                    <div><Label className="text-zinc-400 text-sm">Practice</Label><Input placeholder="Smith Dental" value={loginForm.practice_name} onChange={(e) => setLoginForm({ ...loginForm, practice_name: e.target.value })} className="bg-zinc-800 border-zinc-700 text-zinc-100 mt-1" /></div>
                  </>
                )}
                <div><Label className="text-zinc-400 text-sm">Email</Label><Input type="email" placeholder="doctor@practice.com" value={loginForm.email} onChange={(e) => setLoginForm({ ...loginForm, email: e.target.value })} required className="bg-zinc-800 border-zinc-700 text-zinc-100 mt-1" /></div>
                <div><Label className="text-zinc-400 text-sm">Password</Label><Input type="password" placeholder="********" value={loginForm.password} onChange={(e) => setLoginForm({ ...loginForm, password: e.target.value })} required className="bg-zinc-800 border-zinc-700 text-zinc-100 mt-1" /></div>
                
                {!isLoginMode && (
                  <div className="pt-2">
                    <Label className="text-zinc-400 text-sm mb-2 block">Connect Email Accounts (Optional - Auto-syncs top 5 emails)</Label>
                    <div className="grid grid-cols-2 gap-2">
                      {['gmail', 'outlook', 'yahoo', 'aol', 'apple'].map((provider) => (
                        <Button
                          key={provider}
                          type="button"
                          variant="outline"
                          onClick={async () => {
                            try {
                              setConnectingEmail(provider)
                              // Get auth URL (public endpoint for registration)
                              const response = await fetch(`${API_URL}/api/nylas/auth-url-public?provider=${provider}`)
                              const data = await response.json()
                              if (data.auth_url) {
                                // Store user_id in localStorage temporarily for callback
                                localStorage.setItem('temp_user_email', loginForm.email)
                                window.location.href = data.auth_url
                              }
                            } catch (error) {
                              alert('Failed to connect email account')
                            } finally {
                              setConnectingEmail(null)
                            }
                          }}
                          disabled={loading || connectingEmail !== null}
                          className="bg-zinc-800 border-zinc-700 text-zinc-300 hover:bg-zinc-700 text-xs"
                        >
                          {connectingEmail === provider ? 'Connecting...' : provider.charAt(0).toUpperCase() + provider.slice(1)}
                        </Button>
                      ))}
                    </div>
                    {connectedEmails.length > 0 && (
                      <div className="mt-2 text-xs text-emerald-400">
                        Connected: {connectedEmails.join(', ')}
                      </div>
                    )}
                  </div>
                )}
                
                <Button type="submit" className="w-full bg-emerald-600 hover:bg-emerald-700 text-white" disabled={loading}>{loading ? 'Please wait...' : (isLoginMode ? 'Login' : 'Create Account')}</Button>
              </form>
            </Tabs>
          </CardContent>
        </Card>
      </div>
    )
  }

  // MAIN APP - TWO PANE LAYOUT
  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col">
      {/* Header */}
      <header className="bg-zinc-900 border-b border-zinc-800 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-gradient-to-br from-emerald-500 to-teal-600 rounded-lg flex items-center justify-center">
            <Bot className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-zinc-100">DocBoxRX</h1>
            <p className="text-xs text-zinc-500">{user.name}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button 
            variant={viewMode === 'decision-deck' ? 'default' : 'outline'} 
            size="sm" 
            onClick={() => setViewMode(viewMode === 'inbox' ? 'decision-deck' : 'inbox')}
            className={viewMode === 'decision-deck' ? 'bg-blue-600 hover:bg-blue-700' : 'bg-zinc-800 border-zinc-700 text-zinc-300 hover:bg-zinc-700'}
          >
            <LayoutGrid className="w-4 h-4 mr-1" />
            {viewMode === 'decision-deck' ? 'Inbox' : 'Decision Deck'}
          </Button>
          <Button variant="outline" size="sm" onClick={seedDemoData} disabled={loading} className="bg-zinc-800 border-zinc-700 text-zinc-300 hover:bg-zinc-700"><Zap className="w-4 h-4 mr-1" />Demo</Button>
          <Dialog open={ingestOpen} onOpenChange={setIngestOpen}>
            <DialogTrigger asChild><Button size="sm" className="bg-emerald-600 hover:bg-emerald-700"><Plus className="w-4 h-4 mr-1" />Add Email</Button></DialogTrigger>
            <DialogContent className="bg-zinc-900 border-zinc-700 text-zinc-100">
              <DialogHeader><DialogTitle>Add Email</DialogTitle><DialogDescription className="text-zinc-400">Paste email details for jonE5 to analyze</DialogDescription></DialogHeader>
              <form onSubmit={handleIngest} className="space-y-4">
                <div><Label className="text-zinc-400">From</Label><Input placeholder="sender@example.com" value={ingestForm.sender} onChange={(e) => setIngestForm({ ...ingestForm, sender: e.target.value })} required className="bg-zinc-800 border-zinc-700 text-zinc-100 mt-1" /></div>
                <div><Label className="text-zinc-400">Subject</Label><Input placeholder="Email subject" value={ingestForm.subject} onChange={(e) => setIngestForm({ ...ingestForm, subject: e.target.value })} required className="bg-zinc-800 border-zinc-700 text-zinc-100 mt-1" /></div>
                <div><Label className="text-zinc-400">Body</Label><Textarea placeholder="Full email content..." value={ingestForm.snippet} onChange={(e) => setIngestForm({ ...ingestForm, snippet: e.target.value })} rows={5} className="bg-zinc-800 border-zinc-700 text-zinc-100 mt-1" /></div>
                <Button type="submit" className="w-full bg-emerald-600 hover:bg-emerald-700" disabled={loading}>{loading ? 'Analyzing...' : 'Analyze with jonE5'}</Button>
              </form>
            </DialogContent>
          </Dialog>

          {/* CloudMailin Inbox */}
          <Dialog open={cloudOpen} onOpenChange={(open) => { setCloudOpen(open); if (open) fetchCloudMessages() }}>
            <DialogTrigger asChild><Button size="sm" className="bg-zinc-800 border-zinc-700 text-zinc-300 hover:bg-zinc-700">Cloud</Button></DialogTrigger>
            <DialogContent className="bg-zinc-900 border-zinc-700 text-zinc-100 w-[800px] max-w-full">
              <DialogHeader><DialogTitle>CloudMailin Inbox</DialogTitle><DialogDescription className="text-zinc-400">Real emails received via CloudMailin</DialogDescription></DialogHeader>
              <div className="max-h-[60vh] overflow-y-auto mt-4">
                {cloudZoneData ? (
                  (['STAT','TODAY','THIS_WEEK','LATER'] as ZoneType[]).map(z => (
                    <div key={z} className="mb-6">
                      <h4 className="text-xs text-zinc-400 uppercase mb-2">{zoneConfig[z].label} ({cloudZoneData.counts[z] || 0})</h4>
                      {(cloudZoneData.zones[z] || []).map((m: any) => (
                        <div key={m.id} className="p-3 mb-2 bg-zinc-800 border border-zinc-700 rounded-lg flex items-start justify-between">
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
                              <Badge className={`text-xs px-1.5 py-0 border ${zoneConfig[asZoneType(m.zone)].pillBg}`}>{zoneConfig[asZoneType(m.zone)].label}</Badge>
                              <div className="text-xs text-zinc-400 truncate">{m.sender}</div>
                              <div className="text-xs text-zinc-600 ml-2">{new Date(m.received_at).toLocaleString()}</div>
                            </div>
                            <div className="flex items-center gap-2">
                              <div className="text-sm font-medium text-zinc-200">{m.subject}</div>
                              {m.llm_fallback && <Badge className="text-xs bg-red-800 text-red-200">Needs Review</Badge>}
                            </div>
                            {m.snippet && <div className="text-xs text-zinc-400 mt-1 truncate">{m.snippet}</div>}
                          </div>
                          <div className="flex flex-col gap-2 ml-4">
                            <Button size="sm" variant="outline" onClick={() => handleCloudAction(m.id, 'done')} className="bg-zinc-800 border-zinc-700 text-emerald-400">Done</Button>
                            <Button size="sm" variant="outline" onClick={() => handleCloudAction(m.id, 'archived')} className="bg-zinc-800 border-zinc-700 text-zinc-400">Archive</Button>
                            <Button size="sm" variant="outline" onClick={() => handleCloudDelete(m.id)} className="bg-zinc-800 border-zinc-700 text-red-400">Delete</Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  ))
                ) : (
                  <div className="p-6 text-center text-zinc-400">No cloud messages</div>
                )}
              </div>
            </DialogContent>
          </Dialog>
          <Button variant="outline" size="sm" onClick={() => fetchMessages()} disabled={loading} className="bg-zinc-800 border-zinc-700 text-zinc-300 hover:bg-zinc-700"><RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /></Button>
          <Button variant="ghost" size="sm" onClick={handleLogout} className="text-zinc-400 hover:text-zinc-100"><LogOut className="w-4 h-4" /></Button>
        </div>
      </header>

      {providerBanner && (
        <div className="bg-zinc-900 border-b border-zinc-800 px-4 py-2">
          <Alert variant={providerBanner.variant}>
            <div className="flex items-start gap-3">
              <div className="flex-1">
                <AlertTitle className="text-sm">{providerBanner.title}</AlertTitle>
                <AlertDescription className="text-xs text-zinc-400">{providerBanner.message}</AlertDescription>
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 w-6 p-0 text-zinc-500 hover:text-zinc-200"
                onClick={() => setProviderBanner(null)}
              >
                <X className="w-4 h-4" />
              </Button>
            </div>
          </Alert>
        </div>
      )}

      {jone5Message && (
        <div className="bg-emerald-900/30 border-b border-emerald-800/50 px-4 py-2 flex items-center gap-2">
          <Bot className="w-4 h-4 text-emerald-400" />
          <span className="text-sm text-emerald-300">{jone5Message}</span>
          <Button variant="ghost" size="sm" className="ml-auto h-6 px-2 text-emerald-400 hover:text-emerald-300" onClick={() => setJone5Message('')}>x</Button>
        </div>
      )}

      {/* Action Center Summary */}
      {actionCenter && actionCenter.total_action_items > 0 && (
        <div className="bg-zinc-900/50 border-b border-zinc-800 px-4 py-3">
          <div className="flex items-center gap-6 text-sm">
            <span className="text-zinc-400">Today:</span>
            <span className="text-red-400 font-medium">{actionCenter.urgent_count} urgent</span>
            <span className="text-orange-400 font-medium">{actionCenter.needs_reply_count} need reply</span>
            <span className="text-emerald-400 font-medium">{actionCenter.done_today} done</span>
          </div>
        </div>
      )}

      {/* Main Content - Conditional View */}
      {viewMode === 'decision-deck' ? (
        <MorningBrief />
      ) : (
        <div className="flex-1 flex overflow-hidden">
          {/* Left Pane - Message List */}
          <div className="w-96 border-r border-zinc-800 flex flex-col bg-zinc-900/50">
          {/* Filter Tabs */}
          <div className="p-2 border-b border-zinc-800 flex gap-1 overflow-x-auto">
            <Button variant={activeTab === 'all' ? 'default' : 'ghost'} size="sm" onClick={() => setActiveTab('all')} className={activeTab === 'all' ? 'bg-zinc-700' : 'text-zinc-400'}>All ({allMessages.length})</Button>
            {(['STAT', 'TODAY', 'THIS_WEEK', 'LATER'] as ZoneType[]).map(z => (
              <Button key={z} variant={activeTab === z ? 'default' : 'ghost'} size="sm" onClick={() => setActiveTab(z)} className={`${activeTab === z ? 'bg-zinc-700' : 'text-zinc-400'} ${zoneConfig[z].color}`}>
                {zoneConfig[z].label} ({zoneData?.counts[z] || 0})
              </Button>
            ))}
          </div>
          {/* Message List */}
          <div className="flex-1 overflow-y-auto">
            {filteredMessages.length === 0 ? (
              <div className="p-8 text-center text-zinc-500">
                <Mail className="w-12 h-12 mx-auto mb-3 opacity-30" />
                <p>No messages</p>
                <p className="text-xs mt-1">Click Demo to load sample emails</p>
              </div>
            ) : (
              filteredMessages.map((msg) => (
                <div key={msg.id} onClick={() => { setSelectedMessage(msg); setShowEmailDetail(true); }} className={`p-3 border-b border-zinc-800 cursor-pointer hover:bg-zinc-800/50 transition-colors ${selectedMessage?.id === msg.id ? 'bg-zinc-800 border-l-2 border-l-emerald-500' : ''}`}>
                  <div className="flex items-center gap-2 mb-1">
                    <Badge className={`text-xs px-1.5 py-0 border ${zoneConfig[msg.zone].pillBg}`}>{zoneConfig[msg.zone].label}</Badge>
                    <span className="text-xs text-zinc-500 truncate flex-1">{msg.sender}</span>
                    <span className="text-xs text-zinc-600">{Math.round(msg.confidence * 100)}%</span>
                  </div>
                  <p className="text-sm font-medium text-zinc-200 truncate">{msg.subject}</p>
                  {msg.recommended_action && <p className="text-xs text-emerald-500 mt-1 truncate">{msg.recommended_action}</p>}
                </div>
              ))
            )}
          </div>
        </div>

        {/* Right Pane - Email Detail + jonE5 Analysis */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {selectedMessage ? (
            <>
              {/* Email Detail Modal */}
              {showEmailDetail && (
                <EmailDetail
                  subject={selectedMessage.subject}
                  from={selectedMessage.sender}
                  date={new Date(selectedMessage.received_at).toLocaleString()}
                  html={fullEmailContent?.raw_body_html || ''}
                  onClose={() => setShowEmailDetail(false)}
                />
              )}
              {/* Email Header */}
              <div className="p-4 border-b border-zinc-800 bg-zinc-900/30">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2">
                      <Badge className={`border ${zoneConfig[selectedMessage.zone].pillBg}`}>{zoneConfig[selectedMessage.zone].icon}{zoneConfig[selectedMessage.zone].label}</Badge>
                      <span className="text-xs text-zinc-500">{Math.round(selectedMessage.confidence * 100)}% confidence</span>
                    </div>
                    <h2 className="text-xl font-semibold text-zinc-100 mb-1">{selectedMessage.subject}</h2>
                    <p className="text-sm text-zinc-400">From: <span className="text-zinc-300">{selectedMessage.sender}</span></p>
                    <p className="text-xs text-zinc-500 mt-1">{new Date(selectedMessage.received_at).toLocaleString()}</p>
                  </div>
                  <div className="flex gap-1">
                    <Button size="sm" variant="outline" onClick={(e) => handleMarkDone(selectedMessage.id, e)} className="bg-zinc-800 border-zinc-700 text-emerald-400 hover:bg-emerald-900/30"><Check className="w-4 h-4" /></Button>
                    <Button size="sm" variant="outline" onClick={(e) => handleSnooze(selectedMessage.id, 4, e)} className="bg-zinc-800 border-zinc-700 text-blue-400 hover:bg-blue-900/30"><Clock3 className="w-4 h-4" /></Button>
                    <Button size="sm" variant="outline" onClick={(e) => handleArchive(selectedMessage.id, e)} className="bg-zinc-800 border-zinc-700 text-zinc-400 hover:bg-zinc-700"><Archive className="w-4 h-4" /></Button>
                    <Button size="sm" variant="outline" onClick={() => handleDelete(selectedMessage.id)} className="bg-zinc-800 border-zinc-700 text-red-400 hover:bg-red-900/30"><Trash2 className="w-4 h-4" /></Button>
                  </div>
                </div>
              </div>

              {/* Scrollable Content */}
              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {/* Email Body - Full Content Display */}
                <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
                  <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wide mb-3">Email Content</h3>
                  {fullEmailContent?.raw_body_html ? (
                    <div className="text-sm text-zinc-300 leading-relaxed prose prose-invert max-w-none">
                      <Button size="sm" className="mb-2 bg-blue-700 hover:bg-blue-800 text-white" onClick={() => setShowEmailDetail(true)}>Open Full HTML View</Button>
                      <div className="mt-2" dangerouslySetInnerHTML={{ __html: fullEmailContent.raw_body_html }} />
                    </div>
                  ) : (
                    <div className="text-sm text-zinc-300 whitespace-pre-wrap leading-relaxed">
                      {fullEmailContent?.raw_body || selectedMessage.raw_body || selectedMessage.snippet || 'Loading full email content...'}
                    </div>
                  )}
                </div>

                {/* jonE5 AI Analysis */}
                <div className="bg-gradient-to-br from-emerald-950/50 to-teal-950/30 border border-emerald-800/50 rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-4">
                    <Bot className="w-5 h-5 text-emerald-400" />
                    <h3 className="text-sm font-semibold text-emerald-400">jonE5 AI Analysis</h3>
                    <span className="text-xs text-emerald-600 bg-emerald-900/50 px-2 py-0.5 rounded">AI Generated</span>
                  </div>

                  {/* Summary */}
                  <div className="mb-4">
                    <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wide mb-2">Summary</h4>
                    <p className="text-sm text-zinc-300">{selectedMessage.summary || selectedMessage.reason || 'jonE5 analyzed this email and classified it based on sender patterns and content keywords.'}</p>
                  </div>

                  {/* Recommended Action */}
                  <div className="mb-4">
                    <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wide mb-2">Recommended Action</h4>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-emerald-300">{selectedMessage.recommended_action || 'Review and respond as needed'}</span>
                      {selectedMessage.action_type && <Badge className="bg-emerald-900/50 text-emerald-400 border-emerald-700">{selectedMessage.action_type}</Badge>}
                    </div>
                  </div>

                  {/* Classification Reason */}
                  <div className="mb-4">
                    <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wide mb-2">Why This Priority</h4>
                    <p className="text-sm text-zinc-400">{selectedMessage.reason}</p>
                  </div>

                  {/* Draft Reply */}
                  <div>
                    <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wide mb-2">Draft Reply</h4>
                    {selectedMessage.llm_fallback && (
                      <Alert variant="destructive" className="mb-3 bg-red-950/40 border-red-900/60 text-red-200">
                        <AlertTriangle className="w-4 h-4" />
                        <AlertTitle className="text-sm">Review before sending</AlertTitle>
                        <AlertDescription className="text-xs text-red-200/80">
                          jonE5 relied on a fallback response and may not have tailored this draft. Please edit before sending.
                        </AlertDescription>
                      </Alert>
                    )}
                    <div className="bg-zinc-900/80 border border-zinc-700 rounded-lg p-3">
                      <p className="text-sm text-zinc-300 whitespace-pre-wrap mb-3">
                        {selectedMessage.draft_reply || `Thank you for your email regarding "${selectedMessage.subject}".\n\nI have reviewed the information and will respond accordingly.\n\nBest regards,\n${user.name}`}
                      </p>
                      <div className="flex gap-2">
                        <Button size="sm" variant="outline" onClick={() => copyToClipboard(selectedMessage.draft_reply || `Thank you for your email regarding "${selectedMessage.subject}".\n\nI have reviewed the information and will respond accordingly.\n\nBest regards,\n${user.name}`)} className="bg-zinc-800 border-zinc-700 text-zinc-300 hover:bg-zinc-700">
                          <Copy className="w-4 h-4 mr-1" />Copy Reply
                        </Button>
                        <Button size="sm" onClick={() => setReplyComposerOpen(true)} className="bg-emerald-600 hover:bg-emerald-700 text-white">
                          <Mail className="w-4 h-4 mr-1" />Reply
                        </Button>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Move to Different Zone */}
                <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
                  <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wide mb-3">Reclassify</h3>
                  <div className="flex items-center gap-2">
                    <Select value={newZone} onValueChange={(v) => setNewZone(v as ZoneType)}>
                      <SelectTrigger className="w-40 bg-zinc-800 border-zinc-700 text-zinc-300"><SelectValue /></SelectTrigger>
                      <SelectContent className="bg-zinc-800 border-zinc-700">
                        {(['STAT', 'TODAY', 'THIS_WEEK', 'LATER'] as ZoneType[]).map((z) => (
                          <SelectItem key={z} value={z} className="text-zinc-300">{zoneConfig[z].label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Button size="sm" onClick={handleCorrection} disabled={loading || newZone === selectedMessage.zone} className="bg-zinc-700 hover:bg-zinc-600 text-zinc-200">Move & Teach jonE5</Button>
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center text-zinc-500">
              <div className="text-center">
                <Mail className="w-16 h-16 mx-auto mb-4 opacity-30" />
                <p className="text-lg">Select an email to view</p>
                <p className="text-sm mt-1">Or click Demo to load sample emails</p>
              </div>
            </div>
          )}
        </div>
      </div>
      )}

      {/* Integrated Reply Composer Modal */}
      <Dialog open={replyComposerOpen} onOpenChange={setReplyComposerOpen}>
        <DialogContent className="bg-zinc-900 border-zinc-700 text-zinc-100 max-w-2xl">
          <DialogHeader>
            <DialogTitle>Reply to {selectedMessage?.sender}</DialogTitle>
            <DialogDescription className="text-zinc-400">
              {selectedMessage?.subject}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 mt-4">
            <div>
              <Label className="text-zinc-400 text-sm mb-2 block">To</Label>
              <Input 
                value={selectedMessage?.sender.match(/<([^>]+)>/)?.[1] || selectedMessage?.sender.match(/[\w.-]+@[\w.-]+/)?.[0] || selectedMessage?.sender || ''} 
                readOnly 
                className="bg-zinc-800 border-zinc-700 text-zinc-300"
              />
            </div>
            <div>
              <Label className="text-zinc-400 text-sm mb-2 block">Subject</Label>
              <Input 
                value={`Re: ${selectedMessage?.subject || ''}`} 
                readOnly 
                className="bg-zinc-800 border-zinc-700 text-zinc-300"
              />
            </div>
            <div>
              <Label className="text-zinc-400 text-sm mb-2 block">Message</Label>
              <Textarea
                value={replyText}
                onChange={(e) => setReplyText(e.target.value)}
                rows={10}
                className="bg-zinc-800 border-zinc-700 text-zinc-300 font-mono text-sm"
                placeholder="Type your reply here..."
              />
            </div>
            <div className="flex gap-2 justify-end">
              <Button 
                variant="outline" 
                onClick={() => setReplyComposerOpen(false)}
                className="bg-zinc-800 border-zinc-700 text-zinc-300"
              >
                Cancel
              </Button>
              <Button 
                onClick={async () => {
                  if (!selectedMessage || !replyText.trim()) return
                  try {
                    setLoading(true)
                    const result = await apiCall(`/api/messages/${selectedMessage.id}/send-reply`, {
                      method: 'POST',
                      body: JSON.stringify({ 
                        message_id: selectedMessage.id, 
                        reply_body: replyText 
                      })
                    })
                    if (result && result.success) {
                      setJone5Message("Reply sent successfully!")
                      setReplyComposerOpen(false)
                      fetchMessages()
                      fetchActionCenter()
                    }
                  } catch (error) {
                    alert(error instanceof Error ? error.message : 'Failed to send reply. Make sure you have connected an email account via Nylas.')
                  } finally {
                    setLoading(false)
                  }
                }} 
                disabled={loading || !replyText.trim()}
                className="bg-emerald-600 hover:bg-emerald-700 text-white"
              >
                {loading ? 'Sending...' : 'Send Reply'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default App
