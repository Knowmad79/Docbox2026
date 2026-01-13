import React, { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { 
  Mail, 
  User, 
  Calendar, 
  Paperclip, 
  Download, 
  Eye, 
  EyeOff,
  Shield,
  AlertTriangle,
  RefreshCw
} from 'lucide-react'

// API URL
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface EmailViewerProps {
  message: any
  token: string | null
  onReply?: (message: any) => void
  onForward?: (message: any) => void
}

export default function EmailViewer({ message, token, onReply, onForward }: EmailViewerProps) {
  const [fullContent, setFullContent] = useState<{ raw_body?: string; raw_body_html?: string } | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showRawHtml, setShowRawHtml] = useState(false)
  const [sanitizedHtml, setSanitizedHtml] = useState<string>('')

  // Fetch full email content
  const fetchFullContent = async () => {
    if (!token || !message?.id) return
    
    try {
      setLoading(true)
      setError(null)
      
      const response = await fetch(`${API_URL}/api/messages/${message.id}/full`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      
      if (!response.ok) throw new Error('Failed to fetch full content')
      
      const data = await response.json()
      setFullContent(data)
      
      // Sanitize HTML if present
      if (data.raw_body_html) {
        setSanitizedHtml(sanitizeHtml(data.raw_body_html))
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch full content')
    } finally {
      setLoading(false)
    }
  }

  // Basic HTML sanitization (in production, use DOMPurify library)
  const sanitizeHtml = (html: string): string => {
    // Remove potentially dangerous elements and attributes
    const dangerousTags = ['script', 'iframe', 'object', 'embed', 'form', 'input', 'button']
    const dangerousAttrs = ['onclick', 'onload', 'onerror', 'onmouseover', 'onfocus', 'onblur']
    
    let sanitized = html
    
    // Remove dangerous tags
    dangerousTags.forEach(tag => {
      const regex = new RegExp(`<${tag}[^>]*>.*?</${tag}>`, 'gis')
      sanitized = sanitized.replace(regex, '')
    })
    
    // Remove dangerous attributes
    dangerousAttrs.forEach(attr => {
      const regex = new RegExp(`\\s${attr}\\s*=\\s*["'][^"']*["']`, 'gi')
      sanitized = sanitized.replace(regex, '')
    })
    
    // Remove javascript: URLs
    sanitized = sanitized.replace(/javascript:/gi, '')
    
    return sanitized
  }

  // Format email headers
  const formatHeaders = () => {
    if (!message) return null
    
    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <User className="w-4 h-4 text-gray-500" />
          <span className="font-medium">From:</span>
          <span>{message.sender}</span>
        </div>
        
        {message.to && (
          <div className="flex items-center gap-2">
            <Mail className="w-4 h-4 text-gray-500" />
            <span className="font-medium">To:</span>
            <span>{message.to}</span>
          </div>
        )}
        
        <div className="flex items-center gap-2">
          <Calendar className="w-4 h-4 text-gray-500" />
          <span className="font-medium">Date:</span>
          <span>{new Date(message.received_at).toLocaleString()}</span>
        </div>
        
        {message.provider && (
          <div className="flex items-center gap-2">
            <Badge variant="outline">{message.provider}</Badge>
          </div>
        )}
      </div>
    )
  }

  // Load content on mount
  useEffect(() => {
    if (message && token) {
      fetchFullContent()
    }
  }, [message, token])

  if (!message) {
    return (
      <div className="text-center py-8">
        <Mail className="w-12 h-12 text-gray-400 mx-auto mb-4" />
        <p className="text-gray-600">Select an email to view</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Email Header */}
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <CardTitle className="text-xl mb-2">{message.subject}</CardTitle>
              <CardDescription>
                {formatHeaders()}
              </CardDescription>
            </div>
            <div className="flex gap-2">
              {onReply && (
                <Button onClick={() => onReply(message)} variant="outline">
                  Reply
                </Button>
              )}
              {onForward && (
                <Button onClick={() => onForward(message)} variant="outline">
                  Forward
                </Button>
              )}
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* AI Processing Info */}
      {(message.summary || message.recommended_action || message.zone) && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Shield className="w-5 h-5" />
              AI Analysis
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center gap-2">
              <Badge variant={
                message.zone === 'STAT' ? 'destructive' :
                message.zone === 'TODAY' ? 'default' :
                message.zone === 'THIS_WEEK' ? 'secondary' : 'outline'
              }>
                Priority: {message.zone}
              </Badge>
              <span className="text-sm text-gray-600">
                Confidence: {Math.round((message.confidence || 0) * 100)}%
              </span>
            </div>
            
            {message.summary && (
              <div>
                <h4 className="font-medium mb-1">Summary:</h4>
                <p className="text-sm text-gray-700">{message.summary}</p>
              </div>
            )}
            
            {message.recommended_action && (
              <div>
                <h4 className="font-medium mb-1">Recommended Action:</h4>
                <p className="text-sm text-gray-700">{message.recommended_action}</p>
              </div>
            )}
            
            {message.llm_fallback && (
              <Alert>
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>
                  This message was processed using AI fallback due to classification uncertainty.
                </AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>
      )}

      {/* Email Content */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Email Content</CardTitle>
            <div className="flex gap-2">
              {fullContent?.raw_body_html && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowRawHtml(!showRawHtml)}
                >
                  {showRawHtml ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
                  {showRawHtml ? 'Formatted' : 'Raw HTML'}
                </Button>
              )}
              <Button variant="outline" size="sm" onClick={fetchFullContent} disabled={loading}>
                <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {error && (
            <Alert>
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {loading ? (
            <div className="text-center py-8">
              <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-4" />
              <p>Loading email content...</p>
            </div>
          ) : fullContent ? (
            <div className="space-y-4">
              {/* Attachments */}
              {message.has_attachments && (
                <div className="flex items-center gap-2 p-3 bg-gray-50 rounded-lg">
                  <Paperclip className="w-4 h-4 text-gray-500" />
                  <span className="text-sm">This email contains attachments</span>
                  <Button variant="outline" size="sm">
                    <Download className="w-4 h-4 mr-1" />
                    View Attachments
                  </Button>
                </div>
              )}

              {/* Email Body */}
              <div className="border rounded-lg overflow-hidden">
                {showRawHtml && fullContent.raw_body_html ? (
                  <div className="p-4">
                    <div className="mb-2 flex items-center gap-2 text-sm text-gray-600">
                      <AlertTriangle className="w-4 h-4" />
                      <span>Raw HTML view - potentially unsafe content hidden</span>
                    </div>
                    <pre className="text-xs bg-gray-100 p-4 rounded overflow-auto max-h-96">
                      {fullContent.raw_body_html}
                    </pre>
                  </div>
                ) : (
                  <div 
                    className="p-4 prose max-w-none"
                    dangerouslySetInnerHTML={{ 
                      __html: sanitizedHtml || fullContent.raw_body || '<p>No content available</p>' 
                    }}
                  />
                )}
              </div>

              {/* Security Notice */}
              {fullContent.raw_body_html && (
                <Alert>
                  <Shield className="h-4 w-4" />
                  <AlertDescription>
                    HTML content has been sanitized for security. Some formatting may be altered.
                  </AlertDescription>
                </Alert>
              )}
            </div>
          ) : (
            <div className="text-center py-8">
              <p className="text-gray-600">No full content available</p>
              <p className="text-sm text-gray-500 mt-2">
                {message.snippet || 'No preview available'}
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
