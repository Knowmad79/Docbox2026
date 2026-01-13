import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Separator } from '@/components/ui/separator'
import { AlertTriangle, Clock, User, Mail, CheckCircle, ArrowRight, RefreshCw, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'

// API URL
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface StateVector {
  id: string
  nylas_message_id: string
  grant_id: string
  intent_label: string
  risk_score: number
  context_blob: {
    patient_name?: string
    dob?: string
    [key: string]: any
  }
  summary?: string
  current_owner_role?: string
  deadline_at?: string
  lifecycle_state?: string
  is_overdue?: boolean
  created_at?: string
  updated_at?: string
}

interface ActionResponse {
  status: string
  action: string
  vector_id: string
}

export default function MorningBrief() {
  const [vectors, setVectors] = useState<StateVector[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [currentCardIndex, setCurrentCardIndex] = useState(0)
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  const fetchDailyDeck = async () => {
    try {
      setLoading(true)
      setError(null)
      
      const response = await fetch(`${API_URL}/api/briefing/daily-deck?role=lead_doctor`)
      if (!response.ok) {
        throw new Error(`Failed to fetch daily deck: ${response.status}`)
      }
      
      const data = await response.json()
      setVectors(data)
      setCurrentCardIndex(0)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load daily deck')
    } finally {
      setLoading(false)
    }
  }

  const takeAction = async (vectorId: string, action: string) => {
    try {
      setActionLoading(vectorId)
      
      const response = await fetch(`${API_URL}/api/briefing/${vectorId}/action?action=${encodeURIComponent(action)}`, {
        method: 'POST',
      })
      
      if (!response.ok) {
        throw new Error(`Failed to take action: ${response.status}`)
      }
      
      const result: ActionResponse = await response.json()
      console.log('Action taken:', result)
      
      // Remove the card from the deck (swipe it away)
      setVectors(prev => prev.filter(v => v.id !== vectorId))
      
      // Keep index in-range after removal
      setCurrentCardIndex(prev => Math.max(0, Math.min(prev, vectors.length - 2)))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to take action')
    } finally {
      setActionLoading(null)
    }
  }

  useEffect(() => {
    fetchDailyDeck()
  }, [])

  const getRiskColor = (risk: number) => {
    if (risk >= 0.8) return 'bg-red-100 text-red-800 border-red-200'
    if (risk >= 0.5) return 'bg-yellow-100 text-yellow-800 border-yellow-200'
    return 'bg-green-100 text-green-800 border-green-200'
  }

  const getRiskLabel = (risk: number) => {
    if (risk >= 0.8) return 'CRITICAL'
    if (risk >= 0.5) return 'MEDIUM'
    return 'LOW'
  }

  const formatDeadline = (deadline: string) => {
    const date = new Date(deadline)
    const now = new Date()
    const hoursUntil = (date.getTime() - now.getTime()) / (1000 * 60 * 60)
    
    if (hoursUntil < 1) return 'Due NOW'
    if (hoursUntil < 24) return `Due in ${Math.round(hoursUntil)}h`
    return `Due in ${Math.round(hoursUntil / 24)}d`
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4 text-blue-600" />
          <p className="text-gray-600">Loading your Decision Deck...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <Alert className="max-w-md">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
          <Button onClick={fetchDailyDeck} className="mt-4">
            <RefreshCw className="h-4 w-4 mr-2" />
            Retry
          </Button>
        </Alert>
      </div>
    )
  }

  if (vectors.length === 0) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <Card className="max-w-md text-center">
          <CardHeader>
            <CheckCircle className="h-12 w-12 text-green-600 mx-auto mb-4" />
            <CardTitle className="text-xl">All Clear! 🎉</CardTitle>
            <CardDescription>
              No urgent items in your Decision Deck. You're caught up!
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={fetchDailyDeck} variant="outline" className="w-full">
              <RefreshCw className="h-4 w-4 mr-2" />
              Refresh Deck
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  const currentVector = vectors[currentCardIndex]

  return (
    <div className="min-h-screen bg-gray-50 p-4">
      {/* Header */}
      <div className="max-w-2xl mx-auto mb-8">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Morning Brief</h1>
            <p className="text-gray-600">Your Decision Deck • {vectors.length} items</p>
          </div>
          <Button onClick={fetchDailyDeck} variant="outline" size="sm">
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
        </div>
        
        {/* Progress indicator */}
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <span>Card {currentCardIndex + 1} of {vectors.length}</span>
          <div className="flex-1 bg-gray-200 rounded-full h-2">
            <div 
              className="bg-blue-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${((currentCardIndex + 1) / vectors.length) * 100}%` }}
            />
          </div>
        </div>
      </div>

      {/* Card Stack */}
      <div className="max-w-2xl mx-auto relative h-[600px]">
        {/* Cards behind current one (for stack effect) */}
        {vectors.slice(currentCardIndex + 1, currentCardIndex + 3).map((vector, index) => (
          <div
            key={vector.id}
            className="absolute inset-0 transition-all duration-300"
            style={{
              transform: `translateY(${(index + 1) * 8}px) scale(${1 - (index + 1) * 0.02})`,
              zIndex: 10 - index,
              opacity: 0.3 - (index * 0.1)
            }}
          >
            <Card className="h-full border-gray-200 bg-white">
              <CardContent className="p-6">
                <div className="h-full flex items-center justify-center text-gray-400">
                  <div className="text-center">
                    <Mail className="h-8 w-8 mx-auto mb-2" />
                    <p>Next Item</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        ))}

        {/* Current Card */}
        <div className="absolute inset-0 z-20">
          <Card className={cn(
            "h-full transition-all duration-300 hover:shadow-2xl",
            currentVector.risk_score >= 0.8 && "border-red-300 border-2",
            currentVector.risk_score >= 0.5 && currentVector.risk_score < 0.8 && "border-yellow-300 border-2",
            currentVector.risk_score < 0.5 && "border-green-300 border-2"
          )}>
            <CardHeader className="pb-4">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <Badge className={getRiskColor(currentVector.risk_score)}>
                      <AlertTriangle className="h-3 w-3 mr-1" />
                      {getRiskLabel(currentVector.risk_score)}: {currentVector.risk_score.toFixed(1)}
                    </Badge>
                    {currentVector.is_overdue && (
                      <Badge variant="destructive">
                        <Clock className="h-3 w-3 mr-1" />
                        OVERDUE
                      </Badge>
                    )}
                  </div>
                  
                  <CardTitle className="text-xl text-gray-900 mb-2">
                    {currentVector.summary || 'Urgent medical attention required'}
                  </CardTitle>
                  
                  <CardDescription className="text-base">
                    {currentVector.intent_label === 'CLINICAL' && (
                      <div className="flex items-center gap-2 text-red-600 font-medium">
                        <AlertTriangle className="h-4 w-4" />
                        Clinical Priority
                      </div>
                    )}
                  </CardDescription>
                </div>
                
                {currentVector.deadline_at && (
                  <div className="text-right">
                    <div className="flex items-center gap-1 text-sm text-gray-500">
                      <Clock className="h-4 w-4" />
                      {formatDeadline(currentVector.deadline_at)}
                    </div>
                  </div>
                )}
              </div>
            </CardHeader>

            <CardContent className="flex-1">
              {/* Patient Info */}
              {currentVector.context_blob.patient_name && (
                <div className="bg-gray-50 rounded-lg p-4 mb-6">
                  <div className="flex items-center gap-3">
                    <div className="bg-blue-100 rounded-full p-2">
                      <User className="h-4 w-4 text-blue-600" />
                    </div>
                    <div>
                      <p className="font-medium text-gray-900">
                        {currentVector.context_blob.patient_name}
                      </p>
                      {currentVector.context_blob.dob && (
                        <p className="text-sm text-gray-500">
                          DOB: {currentVector.context_blob.dob}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Message Preview */}
              <div className="mb-6">
                <p className="text-gray-700 leading-relaxed">
                  {currentVector.summary || 'Patient requires immediate attention...'}
                </p>
              </div>

              <Separator className="my-6" />

              {/* Action Buttons */}
              <div className="space-y-3">
                <Button 
                  className="w-full h-12 text-base"
                  onClick={() => takeAction(currentVector.id, 'resolve')}
                  disabled={actionLoading === currentVector.id}
                >
                  {actionLoading === currentVector.id ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <CheckCircle className="h-4 w-4 mr-2" />
                  )}
                  Resolve & Reply
                </Button>

                <div className="grid grid-cols-2 gap-3">
                  <Button 
                    variant="outline" 
                    className="h-12"
                    onClick={() => takeAction(currentVector.id, 'delegate')}
                    disabled={actionLoading === currentVector.id}
                  >
                    <ArrowRight className="h-4 w-4 mr-2" />
                    Delegate
                  </Button>
                  
                  <Button 
                    variant="outline" 
                    className="h-12"
                    onClick={() => takeAction(currentVector.id, 'defer')}
                    disabled={actionLoading === currentVector.id}
                  >
                    <Clock className="h-4 w-4 mr-2" />
                    Defer
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Navigation */}
      {vectors.length > 1 && (
        <div className="max-w-2xl mx-auto mt-8 flex justify-center gap-4">
          <Button 
            variant="outline" 
            onClick={() => setCurrentCardIndex(Math.max(0, currentCardIndex - 1))}
            disabled={currentCardIndex === 0}
          >
            Previous
          </Button>
          <Button 
            variant="outline"
            onClick={() => setCurrentCardIndex(Math.min(vectors.length - 1, currentCardIndex + 1))}
            disabled={currentCardIndex === vectors.length - 1}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  )
}
