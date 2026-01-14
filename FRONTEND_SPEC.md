# DOCBOX FRONTEND COMPONENT SPEC
# Component tree for Windsurf AI agent

## APP STRUCTURE

```
App.tsx (Main Application)
├── AuthFlow
│   ├── LoginForm
│   ├── RegisterForm
│   └── NylasConnect (Multi-provider OAuth)
├── Dashboard
│   ├── Header (User info, navigation)
│   ├── ViewToggle (Inbox vs Decision Deck)
│   └── MainContent
│       ├── InboxView (STAT/TODAY/LATER tabs)
│       │   ├── MessageList
│       │   │   └── MessageItem
│       │   ├── SearchAndFilter
│       │   └── ZoneTabs
│       ├── MorningBrief (Decision Deck)
│       │   ├── CardStack
│       │   ├── DecisionCard
│       │   └── ActionButtons
│       └── MessageDetail
│           ├── EmailViewer (HTML rendering)
│           ├── AIAnalysisPanel
│           └── ReplyComposer
│               └── SmartCompose (AI suggestions)
├── Settings
│   ├── AccountSettings
│   ├── EmailConnections (NylasConnect)
│   └── Preferences
└── ErrorBoundary
```

## COMPONENT SPECIFICATIONS

### App.tsx
**Purpose**: Main application wrapper and state management
**State**: 
- `user: User | null`
- `token: string | null`
- `viewMode: 'inbox' | 'decision-deck'`
- `selectedMessage: Message | null`
- `replyMode: boolean`

**Props**: None
**Dependencies**: All child components

### NylasConnect
**Purpose**: Multi-provider OAuth integration
**State**:
- `grants: NylasGrant[]`
- `loading: boolean`
- `connecting: string | null`
- `error: string | null`

**Props**:
```typescript
interface NylasConnectProps {
  token: string | null
  onGrantConnected?: (grant: NylasGrant) => void
  onGrantDisconnected?: (grantId: string) => void
}
```

**Features**:
- Google, Microsoft, Yahoo, IMAP OAuth
- Popup-based OAuth flow
- Grant management (sync, disconnect)
- Real-time status updates
- Connection history

### InboxView
**Purpose**: Traditional inbox with zone-based organization
**State**:
- `messages: ZoneData`
- `loading: boolean`
- `searchQuery: string`
- `activeZone: 'all' | 'STAT' | 'TODAY' | 'THIS_WEEK' | 'LATER'`
- `selectedMessages: Set<string>`

**Props**:
```typescript
interface InboxViewProps {
  token: string | null
  onMessageSelect?: (message: Message) => void
  onReply?: (message: Message) => void
}
```

**Features**:
- Zone-based message organization
- Search and filtering
- Message actions (read, star, reply)
- AI analysis display
- Priority indicators
- Bulk actions

### MorningBrief (Decision Deck)
**Purpose**: Tinder-style card interface for prioritized decisions
**State**:
- `vectors: MessageStateVector[]`
- `loading: boolean`
- `currentCardIndex: number`
- `actionLoading: string | null`

**Props**:
```typescript
interface MorningBriefProps {
  token: string | null
}
```

**Features**:
- Card stack interface
- Swipe/decision actions
- Risk scoring display
- Deadline tracking
- Progress indicators

### EmailViewer
**Purpose**: Safe HTML email rendering
**State**:
- `fullContent: { raw_body?: string; raw_body_html?: string } | null`
- `loading: boolean`
- `showRawHtml: boolean`
- `sanitizedHtml: string`

**Props**:
```typescript
interface EmailViewerProps {
  message: Message
  token: string | null
  onReply?: (message: Message) => void
  onForward?: (message: Message) => void
}
```

**Features**:
- Safe HTML sanitization
- Raw/Formatted view toggle
- Attachment handling
- Security notices
- AI analysis display

### SmartCompose
**Purpose**: AI-powered reply composition
**State**:
- `replyText: string`
- `suggestions: Suggestion[]`
- `loading: boolean`
- `generating: boolean`
- `selectedTone: string`

**Props**:
```typescript
interface SmartComposeProps {
  message: Message
  token: string | null
  onSend?: (reply: string) => void
  onCancel?: () => void
}
```

**Features**:
- AI-generated suggestions
- Tone selection (Professional, Casual, Urgent, Detailed)
- Quick action templates
- Character count and read time
- Real-time generation

## SHARED TYPES

```typescript
// User types
interface User {
  id: string
  email: string
  name: string
  practice_name?: string
}

// Message types
interface Message {
  id: string
  user_id: string
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

// Zone data structure
interface ZoneData {
  STAT: Message[]
  TODAY: Message[]
  THIS_WEEK: Message[]
  LATER: Message[]
}

// Nylas grant types
interface NylasGrant {
  id: string
  grant_id: string
  email: string
  provider: string
  created_at: string
  last_sync_at?: string
  status?: 'active' | 'expired' | 'error'
}

// State vector types
interface MessageStateVector {
  id: string
  nylas_message_id: string
  grant_id: string
  intent_label: string
  risk_score: number
  context_blob: Record<string, any>
  summary?: string
  current_owner_role?: string
  deadline_at?: string
  lifecycle_state?: string
  is_overdue?: boolean
  created_at?: string
  updated_at?: string
}

// AI suggestion types
interface Suggestion {
  id: string
  type: 'professional' | 'casual' | 'urgent' | 'detailed'
  title: string
  content: string
  tone: string
}
```

## UI PATTERNS

### Zone Configuration
```typescript
const zoneConfig = {
  STAT: { 
    label: 'CRITICAL', 
    icon: AlertTriangle, 
    color: 'text-red-500', 
    bgColor: 'bg-red-50 border-red-200' 
  },
  TODAY: { 
    label: 'HIGH', 
    icon: Clock, 
    color: 'text-orange-500', 
    bgColor: 'bg-orange-50 border-orange-200' 
  },
  THIS_WEEK: { 
    label: 'ROUTINE', 
    icon: Calendar, 
    color: 'text-blue-500', 
    bgColor: 'bg-blue-50 border-blue-200' 
  },
  LATER: { 
    label: 'FYI', 
    icon: Archive, 
    color: 'text-gray-500', 
    bgColor: 'bg-gray-50 border-gray-200' 
  }
}
```

### Provider Configuration
```typescript
const providers = [
  { id: 'google', name: 'Gmail', icon: '📧', color: 'bg-red-500' },
  { id: 'microsoft', name: 'Outlook', icon: '📨', color: 'bg-blue-500' },
  { id: 'yahoo', name: 'Yahoo', icon: '📬', color: 'bg-purple-500' },
  { id: 'imap', name: 'IMAP/Other', icon: '⚙️', color: 'bg-gray-500' }
]
```

### Tone Configuration
```typescript
const toneOptions = [
  { id: 'professional', label: 'Professional', icon: '👔', description: 'Formal, clinical tone' },
  { id: 'casual', label: 'Casual', icon: '😊', description: 'Friendly, approachable' },
  { id: 'urgent', label: 'Urgent', icon: '🚨', description: 'Time-sensitive, direct' },
  { id: 'detailed', label: 'Detailed', icon: '📋', description: 'Comprehensive, thorough' }
]
```

## ROUTING STRUCTURE

```typescript
// URL patterns
/ - Login/Register
/dashboard - Main dashboard (default)
/dashboard/inbox - Traditional inbox view
/dashboard/decision-deck - Decision deck view
/dashboard/message/:id - Message detail
/settings - Account settings
/settings/email - Email connections
/settings/preferences - User preferences
```

## STATE MANAGEMENT

### Global State (Context)
```typescript
interface AppContext {
  user: User | null
  token: string | null
  viewMode: 'inbox' | 'decision-deck'
  selectedMessage: Message | null
  replyMode: boolean
  
  // Actions
  login: (credentials: LoginCredentials) => Promise<void>
  logout: () => void
  setViewMode: (mode: 'inbox' | 'decision-deck') => void
  selectMessage: (message: Message) => void
  startReply: () => void
  cancelReply: () => void
}
```

### Local State Patterns
- Use `useState` for component-specific state
- Use `useEffect` for data fetching
- Use `useCallback` for event handlers
- Use `useMemo` for expensive computations

## API INTEGRATION

### Base API Client
```typescript
class ApiClient {
  private baseURL: string
  private token: string | null
  
  constructor(baseURL: string) {
    this.baseURL = baseURL
    this.token = null
  }
  
  setToken(token: string) {
    this.token = token
  }
  
  private async request(endpoint: string, options: RequestInit = {}) {
    const url = `${this.baseURL}${endpoint}`
    const headers = {
      'Content-Type': 'application/json',
      ...(this.token && { 'Authorization': `Bearer ${this.token}` }),
      ...options.headers
    }
    
    return fetch(url, { ...options, headers })
  }
  
  // Auth methods
  async login(credentials: LoginCredentials) { /* ... */ }
  async register(userData: RegisterData) { /* ... */ }
  
  // Message methods
  async getMessages(params?: MessageParams) { /* ... */ }
  async getMessage(id: string) { /* ... */ }
  async getFullMessage(id: string) { /* ... */ }
  async replyToMessage(id: string, content: string) { /* ... */ }
  
  // Nylas methods
  async getAuthUrl(provider: string) { /* ... */ }
  async getGrants() { /* ... */ }
  async disconnectGrant(grantId: string) { /* ... */ }
  
  // Briefing methods
  async getDailyDeck(role?: string) { /* ... */ }
  async takeAction(vectorId: string, action: string) { /* ... */ }
}
```

## ERROR HANDLING

### Error Boundary
```typescript
interface ErrorBoundaryState {
  hasError: boolean
  error?: Error
}

class ErrorBoundary extends Component<Props, ErrorBoundaryState> {
  // Catch and display errors gracefully
  // Provide retry mechanisms
  // Log errors for debugging
}
```

### Loading States
- Skeleton loaders for message lists
- Spinners for async operations
- Progress indicators for long-running tasks
- Empty states for no data

## ACCESSIBILITY

### ARIA Labels
- All interactive elements have proper labels
- Screen reader support for navigation
- Keyboard navigation support
- High contrast mode support

### Responsive Design
- Mobile-first approach
- Tablet and desktop layouts
- Touch-friendly interactions
- Proper viewport meta tags

## PERFORMANCE OPTIMIZATIONS

### Code Splitting
- Lazy load route components
- Dynamic imports for large libraries
- Split vendor bundles

### Memoization
- `React.memo` for expensive components
- `useMemo` for computed values
- `useCallback` for event handlers

### Virtual Scrolling
- For large message lists
- Windowed rendering
- Infinite scroll pagination

## TESTING STRATEGY

### Unit Tests
- Component rendering
- State management
- API client methods

### Integration Tests
- Component interactions
- API integration
- Authentication flow

### E2E Tests
- Critical user journeys
- OAuth flow
- Message processing

## DEPLOYMENT CONFIG

### Environment Variables
```typescript
const config = {
  apiUrl: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  environment: import.meta.env.MODE || 'development',
  enableDebugTools: import.meta.env.DEV
}
```

### Build Optimization
- Tree shaking
- Minification
- Asset optimization
- Bundle analysis
