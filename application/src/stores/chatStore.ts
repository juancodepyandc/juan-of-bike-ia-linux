import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type {
  AssistantRunState,
  AssistantStage,
  AssistantTimelineItem,
  AssistantTurnAnalysis,
  AssistantTurnVerification,
  ChatMessage,
} from '../types/app'

function createEmptyRunState(): AssistantRunState {
  return {
    stage: 'idle',
    label: 'Pret',
    detail: 'Le copilote attend une demande.',
    progress: 0,
    startedAt: null,
    finishedAt: null,
    analysis: null,
    verification: null,
    timeline: [],
    lastError: null,
  }
}

interface ChatState {
  messages: ChatMessage[]
  isStreaming: boolean
  streamContent: string
  runState: AssistantRunState

  addMessage: (msg: Omit<ChatMessage, 'id' | 'timestamp'>) => void
  setStreaming: (v: boolean) => void
  setStreamContent: (c: string) => void
  appendStreamContent: (chunk: string) => void
  startRun: () => void
  setRunStage: (
    stage: AssistantStage,
    label: string,
    detail: string,
    progress: number,
    timelineStatus?: AssistantTimelineItem['status'],
  ) => void
  setRunAnalysis: (analysis: AssistantTurnAnalysis) => void
  setRunVerification: (verification: AssistantTurnVerification) => void
  finishRun: () => void
  failRun: (error: string) => void
  resetRun: () => void
  clearMessages: () => void
  popLastAssistantTurn: () => string | null

  /** Edit a single message's content. */
  updateMessage: (id: string, newContent: string) => void
  /** Remove a message (and optionally the assistant turn right after). */
  removeMessage: (id: string, cascade?: boolean) => void
  /** Toggle pinned state on a message. */
  togglePinned: (id: string) => void
  /** Remove all messages AFTER a given id (so a user can regen from there). */
  truncateAfter: (id: string) => void
}

let msgCounter = 0

export const useChatStore = create<ChatState>()(
  persist(
    (set) => ({
  messages: [],
  isStreaming: false,
  streamContent: '',
  runState: createEmptyRunState(),

  addMessage: (msg) =>
    set((s) => ({
      messages: [
        ...s.messages,
        { ...msg, id: `msg-${++msgCounter}-${Date.now()}`, timestamp: Date.now() },
      ].slice(-100),
    })),

  setStreaming: (v) => set({ isStreaming: v }),
  setStreamContent: (c) => set({ streamContent: c }),
  appendStreamContent: (chunk) => set((s) => ({ streamContent: s.streamContent + chunk })),
  startRun: () =>
    set({
      runState: {
        ...createEmptyRunState(),
        stage: 'understand',
        label: 'Analyse',
        detail: 'Lecture de la demande.',
        progress: 5,
        startedAt: Date.now(),
        timeline: [
          {
            id: `run-${Date.now()}`,
            stage: 'understand',
            label: 'Analyse',
            detail: 'Lecture de la demande.',
            status: 'running',
            timestamp: Date.now(),
          },
        ],
      },
    }),
  setRunStage: (stage, label, detail, progress, timelineStatus = 'running') =>
    set((state) => {
      const timelineItem: AssistantTimelineItem = {
        id: `${stage}-${Date.now()}-${state.runState.timeline.length}`,
        stage,
        label,
        detail,
        status: timelineStatus,
        timestamp: Date.now(),
      }

      return {
        runState: {
          ...state.runState,
          stage,
          label,
          detail,
          progress,
          timeline: [...state.runState.timeline, timelineItem].slice(-8),
        },
      }
    }),
  setRunAnalysis: (analysis) =>
    set((state) => ({
      runState: {
        ...state.runState,
        analysis,
      },
    })),
  setRunVerification: (verification) =>
    set((state) => ({
      runState: {
        ...state.runState,
        verification,
      },
    })),
  finishRun: () =>
    set((state) => ({
      runState: {
        ...state.runState,
        stage: 'done',
        label: 'Termine',
        detail: 'Reponse livree.',
        progress: 100,
        finishedAt: Date.now(),
      },
    })),
  failRun: (error) =>
    set((state) => {
      const errorTimelineItem: AssistantTimelineItem = {
        id: `error-${Date.now()}`,
        stage: 'error',
        label: 'Erreur',
        detail: error,
        status: 'error',
        timestamp: Date.now(),
      }

      return {
        runState: {
          ...state.runState,
          stage: 'error',
          label: 'Erreur',
          detail: error,
          progress: state.runState.progress || 0,
          finishedAt: Date.now(),
          lastError: error,
          timeline: [
            ...state.runState.timeline,
            errorTimelineItem,
          ].slice(-8),
        },
      }
    }),
  resetRun: () => set({ runState: createEmptyRunState() }),
  clearMessages: () => set({ messages: [], streamContent: '', runState: createEmptyRunState() }),
  popLastAssistantTurn: () => {
    let lastUserContent: string | null = null
    set((state) => {
      const messages = state.messages
      let lastUserIndex = -1
      for (let index = messages.length - 1; index >= 0; index -= 1) {
        if (messages[index].role === 'user') {
          lastUserIndex = index
          break
        }
      }
      if (lastUserIndex === -1) {
        return state
      }
      lastUserContent = messages[lastUserIndex].content
      return {
        messages: messages.slice(0, lastUserIndex),
        streamContent: '',
        runState: createEmptyRunState(),
      }
    })
    return lastUserContent
  },

  updateMessage: (id, newContent) =>
    set((state) => ({
      messages: state.messages.map((m) =>
        m.id === id ? { ...m, content: newContent, edited: true } : m,
      ),
    })),
  removeMessage: (id, cascade) =>
    set((state) => {
      const idx = state.messages.findIndex((m) => m.id === id)
      if (idx === -1) return state
      // Cascade = also drop the assistant reply immediately after if the
      // deleted message was a user turn (so you can cleanly redo the turn).
      let end = idx + 1
      if (cascade && state.messages[idx].role === 'user' && state.messages[idx + 1]?.role === 'assistant') {
        end = idx + 2
      }
      return { messages: [...state.messages.slice(0, idx), ...state.messages.slice(end)] }
    }),
  togglePinned: (id) =>
    set((state) => ({
      messages: state.messages.map((m) =>
        m.id === id ? { ...m, pinned: !m.pinned } : m,
      ),
    })),
  truncateAfter: (id) =>
    set((state) => {
      const idx = state.messages.findIndex((m) => m.id === id)
      if (idx === -1) return state
      return {
        messages: state.messages.slice(0, idx + 1),
        streamContent: '',
        runState: createEmptyRunState(),
      }
    }),
    }),
    {
      name: 'aurora-chat-store',
      version: 1,
      partialize: (state) => ({
        messages: state.messages.slice(-80),
      }),
    },
  ),
)
