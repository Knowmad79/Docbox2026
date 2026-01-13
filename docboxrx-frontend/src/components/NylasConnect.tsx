import React, { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Mail, CheckCircle, AlertCircle, RefreshCw, Settings } from 'lucide-react'

// API URL
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface NylasGrant {
  id: string
  grant_id: string
  email: string
  provider: string
  created_at: string
  last_sync_at?: string
  status?: 'active' | 'expired' | 'error'
}

interface NylasConnectProps {
  token: string | null
  onGrantConnected?: (grant: NylasGrant) => void
  onGrantDisconnected?: (grantId: string) => void
}

export default function NylasConnect({ token, onGrantConnected, onGrantDisconnected }: NylasConnectProps) {
  const [grants, setGrants] = useState<NylasGrant[]>([])
  const [loading, setLoading] = useState(false)
  const [connecting, setConnecting] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Fetch connected grants
  const fetchGrants = async () => {
    if (!token) return
    
    try {
      setLoading(true)
      setError(null)
      const response = await fetch(`${API_URL}/api/nylas/grants`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      
      if (!response.ok) throw new Error('Failed to fetch grants')
      const data = await response.json()
      setGrants(data.grants || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch connected accounts')
    } finally {
      setLoading(false)
    }
  }

  // Connect new provider
  const connectProvider = async (provider: string) => {
    if (!token) {
      setError('Please login first')
      return
    }

    try {
      setConnecting(provider)
      setError(null)
      
      const response = await fetch(`${API_URL}/api/nylas/auth-url?provider=${provider}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      
      if (!response.ok) throw new Error('Failed to get auth URL')
      const data = await response.json()
      
      if (data.auth_url) {
        // Store state for callback verification
        sessionStorage.setItem('nylas_connect_state', JSON.stringify({
          provider,
          timestamp: Date.now(),
          returnUrl: window.location.href
        }))
        
        // Open OAuth in popup for better UX
        const popup = window.open(data.auth_url, 'nylas-oauth', 'width=500,height=600,scrollbars=yes,resizable=yes')
        
        // Listen for popup close
        const checkClosed = setInterval(() => {
          if (popup?.closed) {
            clearInterval(checkClosed)
            setConnecting(null)
            // Refresh grants after potential connection
            setTimeout(fetchGrants, 1000)
          }
        }, 1000)
        
        // Fallback: redirect if popup blocked
        setTimeout(() => {
          if (!popup?.closed) {
            clearInterval(checkClosed)
            window.location.href = data.auth_url
          }
        }, 5000)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to connect account')
      setConnecting(null)
    }
  }

  // Disconnect grant
  const disconnectGrant = async (grantId: string) => {
    if (!token) return
    
    try {
      setError(null)
      const response = await fetch(`${API_URL}/api/nylas/disconnect/${grantId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      })
      
      if (!response.ok) throw new Error('Failed to disconnect account')
      
      setGrants(prev => prev.filter(g => g.grant_id !== grantId))
      onGrantDisconnected?.(grantId)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to disconnect account')
    }
  }

  // Sync grant
  const syncGrant = async (grantId: string) => {
    if (!token) return
    
    try {
      setError(null)
      const response = await fetch(`${API_URL}/api/nylas/sync/${grantId}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      })
      
      if (!response.ok) throw new Error('Failed to sync account')
      
      // Refresh grants to get updated sync time
      await fetchGrants()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to sync account')
    }
  }

  // Handle OAuth callback
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search)
    const nylasSuccess = urlParams.get('nylas_success')
    const nylasError = urlParams.get('nylas_error')
    const nylasEmail = urlParams.get('email')
    
    if (nylasSuccess === 'true' && nylasEmail) {
      // Clear URL params
      window.history.replaceState({}, document.title, window.location.pathname)
      
      // Show success message and refresh grants
      setError(null)
      setTimeout(fetchGrants, 500)
      
      // Notify parent
      onGrantConnected?.({
        id: '',
        grant_id: '',
        email: nylasEmail,
        provider: '',
        created_at: new Date().toISOString()
      })
    } else if (nylasError) {
      setError(`Connection failed: ${decodeURIComponent(nylasError)}`)
      window.history.replaceState({}, document.title, window.location.pathname)
    }
  }, [onGrantConnected])

  // Load grants on mount and when token changes
  useEffect(() => {
    if (token) {
      fetchGrants()
    }
  }, [token])

  const providers = [
    { id: 'google', name: 'Gmail', icon: '📧', color: 'bg-red-500' },
    { id: 'microsoft', name: 'Outlook', icon: '📨', color: 'bg-blue-500' },
    { id: 'yahoo', name: 'Yahoo', icon: '📬', color: 'bg-purple-500' },
    { id: 'imap', name: 'IMAP/Other', icon: '⚙️', color: 'bg-gray-500' }
  ]

  const getProviderIcon = (provider: string) => {
    const p = providers.find(p => p.id === provider)
    return p?.icon || '📧'
  }

  const getProviderName = (provider: string) => {
    const p = providers.find(p => p.id === provider)
    return p?.name || provider
  }

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Mail className="w-5 h-5" />
          Email Accounts
        </CardTitle>
        <CardDescription>
          Connect your email accounts to enable real-time synchronization and smart processing
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && (
          <Alert>
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Connected Accounts */}
        <div className="space-y-2">
          <h4 className="text-sm font-medium">Connected Accounts ({grants.length})</h4>
          {grants.length === 0 ? (
            <p className="text-sm text-muted-foreground">No email accounts connected yet</p>
          ) : (
            <div className="space-y-2">
              {grants.map((grant) => (
                <div key={grant.grant_id} className="flex items-center justify-between p-3 border rounded-lg">
                  <div className="flex items-center gap-3">
                    <span className="text-lg">{getProviderIcon(grant.provider)}</span>
                    <div>
                      <p className="font-medium">{grant.email}</p>
                      <p className="text-sm text-muted-foreground">
                        {getProviderName(grant.provider)} • Connected {new Date(grant.created_at).toLocaleDateString()}
                      </p>
                      {grant.last_sync_at && (
                        <p className="text-xs text-muted-foreground">
                          Last sync: {new Date(grant.last_sync_at).toLocaleString()}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => syncGrant(grant.grant_id)}
                      disabled={loading}
                    >
                      <RefreshCw className="w-4 h-4" />
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => disconnectGrant(grant.grant_id)}
                    >
                      Disconnect
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Add New Account */}
        <div className="space-y-2">
          <h4 className="text-sm font-medium">Add New Account</h4>
          <div className="grid grid-cols-2 gap-2">
            {providers.map((provider) => (
              <Button
                key={provider.id}
                variant="outline"
                onClick={() => connectProvider(provider.id)}
                disabled={loading || connecting === provider.id}
                className="flex items-center gap-2"
              >
                <span>{provider.icon}</span>
                {connecting === provider.id ? 'Connecting...' : provider.name}
              </Button>
            ))}
          </div>
        </div>

        {/* Help Text */}
        <div className="text-xs text-muted-foreground space-y-1">
          <p>• Connect multiple email accounts for unified inbox</p>
          <p>• Emails are automatically categorized and prioritized</p>
          <p>• Real-time sync ensures you never miss important messages</p>
        </div>
      </CardContent>
    </Card>
  )
}
