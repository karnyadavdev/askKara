import { createSlice } from '@reduxjs/toolkit'
import type { PayloadAction } from '@reduxjs/toolkit'
import type { Source } from './historyApi'

interface StreamState {
  question: string
  stage: string
  answer: string
  steps: string[]
  stageArchived: boolean
  sources: Source[]
  status: 'idle' | 'running' | 'done' | 'error'
  error: string
  streamed: boolean
  deep: boolean
  conversationId: number | null
}

const initialState: StreamState = {
  question: '',
  stage: '',
  answer: '',
  steps: [],
  stageArchived: false,
  sources: [],
  status: 'idle',
  error: '',
  streamed: false,
  deep: false,
  conversationId: null,
}

const streamSlice = createSlice({
  name: 'stream',
  initialState,
  reducers: {
    start(state, action: PayloadAction<string>) {
      state.question = action.payload
      state.stage = ''
      state.answer = ''
      state.steps = []
      state.stageArchived = false
      state.sources = []
      state.status = 'running'
      state.error = ''
      state.streamed = false
      state.conversationId = null
    },
    setConversation(state, action: PayloadAction<number>) {
      state.conversationId = action.payload
    },
    stage(state, action: PayloadAction<string>) {
      const next = action.payload
      if (state.stage && state.stage !== next && !state.stageArchived) state.steps.push(state.stage)
      state.stage = next
      state.stageArchived = false
    },
    token(state, action: PayloadAction<string>) {
      state.answer += action.payload
      state.streamed = true
    },
    step(state, action: PayloadAction<string>) {
      const text = action.payload.trim()
      if (!text) return
      if (state.stage && !state.stageArchived) {
        state.steps.push(state.stage)
        state.stageArchived = true
      }
      state.steps.push(text)
    },
    answer(state, action: PayloadAction<{ answer: string; sources: Source[] }>) {
      state.answer = action.payload.answer
      state.sources = action.payload.sources
      state.status = 'done'
    },
    fail(state, action: PayloadAction<string>) {
      state.status = 'error'
      state.error = action.payload
    },
    toggleDeep(state) {
      state.deep = !state.deep
    },
    reset(state) {
      return { ...initialState, deep: state.deep }
    },
    goHome() {
      return { ...initialState }
    },
  },
})

export const { start, stage, token, step, answer, fail, toggleDeep, reset, goHome, setConversation } = streamSlice.actions
export default streamSlice.reducer
