import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Separator } from '@/components/ui/separator'
import { 
  Send, 
  Bot, 
  RefreshCw, 
  CheckCircle, 
  AlertTriangle, 
  Lightbulb,
  Zap,
  Clock,
  User
} from 'lucide-react'

// API URL
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface SmartComposeProps {
  message: any
  token: string | null
  onSend?: (reply: string) => void
  onCancel?: () => void
}

interface Suggestion {
  id: string
  type: 'professional' | 'casual' | 'urgent' | 'detailed'
  title: string
  content: string
  tone: string
}

export default function SmartCompose({ message, token, onSend, onCancel }: SmartComposeProps) {
  const [replyText, setReplyText] = useState('')
  const [suggestions, setSuggestions] = useState<Suggestion[]>([])
  const [loading, setLoading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedTone, setSelectedTone] = useState<string>('professional')

  // Generate AI suggestions
  const generateSuggestions = async () => {
    if (!token || !message?.id) return
    
    try {
      setGenerating(true)
      setError(null)
      
      const response = await fetch(`${API_URL}/api/messages/${message.id}/suggest-replies`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          tone: selectedTone,
          context: 'reply'
        })
      })
      
      if (!response.ok) throw new Error('Failed to generate suggestions')
      
      const data = await response.json()
      setSuggestions(data.suggestions || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate suggestions')
    } finally {
      setGenerating(false)
    }
  }

  // Send reply
  const sendReply = async () => {
    if (!token || !message?.id || !replyText.trim()) return
    
    try {
      setLoading(true)
      setError(null)
      
      const response = await fetch(`${API_URL}/api/messages/${message.id}/reply`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          content: replyText,
          tone: selectedTone
        })
      })
      
      if (!response.ok) throw new Error('Failed to send reply')
      
      const data = await response.json()
      onSend?.(replyText)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send reply')
    } finally {
      setLoading(false)
    }
  }

  // Apply suggestion
  const applySuggestion = (suggestion: Suggestion) => {
    setReplyText(suggestion.content)
  }

  // Get tone options
  const toneOptions = [
    { id: 'professional', label: 'Professional', icon: '👔', description: 'Formal, clinical tone' },
    { id: 'casual', label: 'Casual', icon: '😊', description: 'Friendly, approachable' },
    { id: 'urgent', label: 'Urgent', icon: '🚨', description: 'Time-sensitive, direct' },
    { id: 'detailed', label: 'Detailed', icon: '📋', description: 'Comprehensive, thorough' }
  ]

  // Load initial draft if available
  useEffect(() => {
    if (message?.draft_reply) {
      setReplyText(message.draft_reply)
    }
  }, [message])

  // Auto-generate suggestions on mount
  useEffect(() => {
    if (message && token) {
      generateSuggestions()
    }
  }, [message, token, selectedTone])

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Bot className="w-5 h-5" />
            <CardTitle>Smart Reply</CardTitle>
            <Badge variant="secondary" className="text-xs">
              AI-Powered
            </Badge>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={generateSuggestions} disabled={generating}>
              <RefreshCw className={`w-4 h-4 mr-1 ${generating ? 'animate-spin' : ''}`} />
              Regenerate
            </Button>
            {onCancel && (
              <Button variant="outline" size="sm" onClick={onCancel}>
                Cancel
              </Button>
            )}
          </div>
        </div>
        <CardDescription>
          Replying to: {message?.sender} • Subject: {message?.subject}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && (
          <Alert>
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Tone Selection */}
        <div className="space-y-2">
          <label className="text-sm font-medium">Reply Tone</label>
          <div className="grid grid-cols-4 gap-2">
            {toneOptions.map((tone) => (
              <Button
                key={tone.id}
                variant={selectedTone === tone.id ? 'default' : 'outline'}
                size="sm"
                onClick={() => setSelectedTone(tone.id)}
                className="flex flex-col items-center gap-1 h-auto py-2"
              >
                <span className="text-lg">{tone.icon}</span>
                <span className="text-xs">{tone.label}</span>
              </Button>
            ))}
          </div>
        </div>

        {/* AI Suggestions */}
        {suggestions.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Lightbulb className="w-4 h-4 text-yellow-500" />
              <label className="text-sm font-medium">AI Suggestions</label>
            </div>
            <div className="space-y-2">
              {suggestions.map((suggestion) => (
                <div
                  key={suggestion.id}
                  className="p-3 border rounded-lg cursor-pointer hover:bg-gray-50 transition-colors"
                  onClick={() => applySuggestion(suggestion)}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-sm">{suggestion.title}</span>
                    <Badge variant="outline" className="text-xs">
                      {suggestion.tone}
                    </Badge>
                  </div>
                  <p className="text-sm text-gray-600 line-clamp-3">{suggestion.content}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Reply Editor */}
        <div className="space-y-2">
          <label className="text-sm font-medium">Your Reply</label>
          <Textarea
            value={replyText}
            onChange={(e) => setReplyText(e.target.value)}
            placeholder="Type your reply here or select an AI suggestion above..."
            className="min-h-[150px]"
          />
          <div className="flex items-center justify-between text-xs text-gray-500">
            <span>{replyText.length} characters</span>
            <div className="flex items-center gap-2">
              <Clock className="w-3 h-3" />
              <span>Estimated 1-2 min read</span>
            </div>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="space-y-2">
          <label className="text-sm font-medium">Quick Actions</label>
          <div className="grid grid-cols-3 gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setReplyText(`Thank you for your message. I have reviewed the information and will respond accordingly.`)}
            >
              Acknowledge
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setReplyText(`I understand this is urgent. I will prioritize this matter and get back to you shortly.`)}
            >
              Urgent Response
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setReplyText(`Could you please provide additional details about this matter? I want to ensure I address everything properly.`)}
            >
              Request Info
            </Button>
          </div>
        </div>

        {/* Send Button */}
        <div className="flex gap-2 pt-4">
          <Button
            onClick={sendReply}
            disabled={loading || !replyText.trim()}
            className="flex-1"
          >
            {loading ? (
              <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Send className="w-4 h-4 mr-2" />
            )}
            Send Reply
          </Button>
          <Button
            variant="outline"
            onClick={() => setReplyText('')}
            disabled={loading}
          >
            Clear
          </Button>
        </div>

        {/* AI Info */}
        <Alert>
          <Bot className="h-4 w-4" />
          <AlertDescription>
            <Zap className="w-4 h-4 inline mr-1" />
            Smart Compose uses AI to generate context-aware suggestions. 
            Always review and personalize your replies before sending.
          </AlertDescription>
        </Alert>
      </CardContent>
    </Card>
  )
}
