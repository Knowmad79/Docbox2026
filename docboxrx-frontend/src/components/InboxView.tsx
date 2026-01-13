import React, { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Separator } from '@/components/ui/separator'
import { 
  Mail, 
  AlertTriangle, 
  Clock, 
  Calendar, 
  Archive, 
  CheckCircle, 
  Reply, 
  Forward, 
  Star,
  Search,
  Filter,
  RefreshCw,
  Eye,
  Paperclip
} from 'lucide-react'

// API URL
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface Message {
  id: string
  sender: string
  sender_domain: string
  subject: string
  snippet: string | null
  zone: 'STAT' | 'TODAY' | 'THIS_WEEK' | 'LATER'
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
  raw_body?: string | null
  raw_body_html?: string | null
  read?: boolean
  starred?: boolean
  important?: boolean
  has_attachments?: boolean
  grant_id?: string
  provider?: string
  thread_id?: string
}

interface ZoneData {
  STAT: Message[]
  TODAY: Message[]
  THIS_WEEK: Message[]
  LATER: Message[]
}

interface InboxViewProps {
  token: string | null
  onMessageSelect?: (message: Message) => void
  onReply?: (message: Message) => void
}

export default function InboxView({ token, onMessageSelect, onReply }: InboxViewProps) {
  const [messages, setMessages] = useState<ZoneData>({ STAT: [], TODAY: [], THIS_WEEK: [], LATER: [] })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [activeZone, setActiveZone] = useState<'all' | 'STAT' | 'TODAY' | 'THIS_WEEK' | 'LATER'>('all')
  const [selectedMessages, setSelectedMessages] = useState<Set<string>>(new Set())

  // Fetch messages
  const fetchMessages = async () => {
    if (!token) return
    
    try {
      setLoading(true)
      setError(null)
      
      const response = await fetch(`${API_URL}/api/messages`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      
      if (!response.ok) throw new Error('Failed to fetch messages')
      
      const data = await response.json()
      setMessages(data.zones || { STAT: [], TODAY: [], THIS_WEEK: [], LATER: [] })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch messages')
    } finally {
      setLoading(false)
    }
  }

  // Mark message as read
  const markAsRead = async (messageId: string) => {
    if (!token) return
    
    try {
      await fetch(`${API_URL}/api/messages/${messageId}/read`, {
        method: 'PATCH',
        headers: { 'Authorization': `Bearer ${token}` }
      })
      
      // Update local state
      setMessages(prev => {
        const updated = { ...prev }
        Object.keys(updated).forEach(zone => {
          updated[zone as keyof ZoneData] = updated[zone as keyof ZoneData].map(msg => 
            msg.id === messageId ? { ...msg, read: true } : msg
          )
        })
        return updated
      })
    } catch (err) {
      console.error('Failed to mark as read:', err)
    }
  }

  // Toggle star
  const toggleStar = async (messageId: string) => {
    if (!token) return
    
    try {
      await fetch(`${API_URL}/api/messages/${messageId}/star`, {
        method: 'PATCH',
        headers: { 'Authorization': `Bearer ${token}` }
      })
      
      // Update local state
      setMessages(prev => {
        const updated = { ...prev }
        Object.keys(updated).forEach(zone => {
          updated[zone as keyof ZoneData] = updated[zone as keyof ZoneData].map(msg => 
            msg.id === messageId ? { ...msg, starred: !msg.starred } : msg
          )
        })
        return updated
      })
    } catch (err) {
      console.error('Failed to toggle star:', err)
    }
  }

  // Filter messages based on search and zone
  const getFilteredMessages = () => {
    let filtered: Message[] = []
    
    if (activeZone === 'all') {
      filtered = [...messages.STAT, ...messages.TODAY, ...messages.THIS_WEEK, ...messages.LATER]
    } else {
      filtered = messages[activeZone] || []
    }
    
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      filtered = filtered.filter(msg => 
        msg.subject.toLowerCase().includes(query) ||
        msg.sender.toLowerCase().includes(query) ||
        msg.snippet?.toLowerCase().includes(query) ||
        msg.summary?.toLowerCase().includes(query)
      )
    }
    
    return filtered.sort((a, b) => new Date(b.received_at).getTime() - new Date(a.received_at).getTime())
  }

  // Get zone config
  const getZoneConfig = (zone: string) => {
    const configs = {
      STAT: { label: 'CRITICAL', icon: AlertTriangle, color: 'text-red-500', bgColor: 'bg-red-50 border-red-200' },
      TODAY: { label: 'HIGH', icon: Clock, color: 'text-orange-500', bgColor: 'bg-orange-50 border-orange-200' },
      THIS_WEEK: { label: 'ROUTINE', icon: Calendar, color: 'text-blue-500', bgColor: 'bg-blue-50 border-blue-200' },
      LATER: { label: 'FYI', icon: Archive, color: 'text-gray-500', bgColor: 'bg-gray-50 border-gray-200' }
    }
    return configs[zone as keyof typeof configs] || configs.LATER
  }

  // Format date
  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    const now = new Date()
    const diffHours = (now.getTime() - date.getTime()) / (1000 * 60 * 60)
    
    if (diffHours < 1) return 'Just now'
    if (diffHours < 24) return `${Math.floor(diffHours)}h ago`
    if (diffHours < 168) return `${Math.floor(diffHours / 24)}d ago`
    return date.toLocaleDateString()
  }

  // Message list item
  const MessageItem = ({ message }: { message: Message }) => {
    const zoneConfig = getZoneConfig(message.zone)
    const Icon = zoneConfig.icon
    
    return (
      <div 
        className={`p-4 border rounded-lg cursor-pointer transition-colors hover:bg-gray-50 ${!message.read ? 'bg-blue-50 border-blue-200' : ''} ${selectedMessages.has(message.id) ? 'ring-2 ring-blue-500' : ''}`}
        onClick={() => {
          onMessageSelect?.(message)
          if (!message.read) markAsRead(message.id)
        }}
      >
        <div className="flex items-start justify-between mb-2">
          <div className="flex items-center gap-2 flex-1 min-w-0">
            <Icon className={`w-4 h-4 ${zoneConfig.color} flex-shrink-0`} />
            <div className="flex-1 min-w-0">
              <p className={`font-medium truncate ${!message.read ? 'text-blue-900' : ''}`}>
                {message.sender}
              </p>
              <p className={`text-sm truncate ${!message.read ? 'text-blue-700' : 'text-gray-600'}`}>
                {message.subject}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-1 flex-shrink-0">
            {message.has_attachments && <Paperclip className="w-4 h-4 text-gray-400" />}
            {message.important && <Star className="w-4 h-4 text-yellow-500 fill-current" />}
            <Button
              variant="ghost"
              size="sm"
              onClick={(e) => {
                e.stopPropagation()
                toggleStar(message.id)
              }}
              className="p-1"
            >
              <Star className={`w-4 h-4 ${message.starred ? 'text-yellow-500 fill-current' : 'text-gray-400'}`} />
            </Button>
          </div>
        </div>
        
        <p className="text-sm text-gray-600 line-clamp-2 mb-2">
          {message.summary || message.snippet || 'No preview available'}
        </p>
        
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Badge variant="secondary" className={zoneConfig.bgColor}>
              {zoneConfig.label}
            </Badge>
            {message.llm_fallback && (
              <Badge variant="outline" className="text-xs">
                AI Fallback
              </Badge>
            )}
          </div>
          <span className="text-xs text-gray-500">
            {formatDate(message.received_at)}
          </span>
        </div>
        
        {message.recommended_action && (
          <div className="mt-2 p-2 bg-gray-50 rounded text-sm">
            <span className="font-medium">AI suggests:</span> {message.recommended_action}
          </div>
        )}
      </div>
    )
  }

  // Load messages on mount and when token changes
  useEffect(() => {
    if (token) {
      fetchMessages()
    }
  }, [token])

  const filteredMessages = getFilteredMessages()
  const totalCount = messages.STAT.length + messages.TODAY.length + messages.THIS_WEEK.length + messages.LATER.length

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Inbox</h2>
          <p className="text-gray-600">{totalCount} messages</p>
        </div>
        <Button onClick={fetchMessages} disabled={loading} variant="outline">
          <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {/* Search and Filters */}
      <div className="flex gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
          <Input
            placeholder="Search messages..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
          />
        </div>
        <Button variant="outline">
          <Filter className="w-4 h-4 mr-2" />
          Filters
        </Button>
      </div>

      {/* Zone Tabs */}
      <Tabs value={activeZone} onValueChange={(value) => setActiveZone(value as any)}>
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="all">All ({totalCount})</TabsTrigger>
          <TabsTrigger value="STAT" className="text-red-600">
            STAT ({messages.STAT.length})
          </TabsTrigger>
          <TabsTrigger value="TODAY" className="text-orange-600">
            TODAY ({messages.TODAY.length})
          </TabsTrigger>
          <TabsTrigger value="THIS_WEEK" className="text-blue-600">
            THIS WEEK ({messages.THIS_WEEK.length})
          </TabsTrigger>
          <TabsTrigger value="LATER" className="text-gray-600">
            LATER ({messages.LATER.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value={activeZone} className="space-y-4">
          {error && (
            <Alert>
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {loading ? (
            <div className="text-center py-8">
              <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-4" />
              <p>Loading messages...</p>
            </div>
          ) : filteredMessages.length === 0 ? (
            <div className="text-center py-8">
              <Mail className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-600">No messages found</p>
            </div>
          ) : (
            <div className="space-y-2">
              {filteredMessages.map((message) => (
                <MessageItem key={message.id} message={message} />
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
