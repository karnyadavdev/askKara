import { createSlice } from '@reduxjs/toolkit'
import type { PayloadAction } from '@reduxjs/toolkit'
import type { Source } from './historyApi'

interface StreamState {
  question: string
  stage: string
  answer: string
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
      state.stage = action.payload
    },
    token(state, action: PayloadAction<string>) {
      state.answer += action.payload
      state.streamed = true
    },
    streamReset(state) {
      state.answer = ''
      state.streamed = false
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

export const { start, stage, token, streamReset, answer, fail, toggleDeep, reset, goHome, setConversation } = streamSlice.actions
export default streamSlice.reducer
