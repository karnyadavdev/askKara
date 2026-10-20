import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react'
import type { RootState } from '../app/store'

export interface ConversationItem {
  id: number
  title: string
  updated_at: string
}

export interface TurnItem {
  id: number
  question: string
  answer: string
  sources: Source[]
  provider: string
  created_at: string
}

export interface Source {
  title: string
  url: string
}

const baseQuery = fetchBaseQuery({
  baseUrl: '/api',
  prepareHeaders: (headers, { getState }) => {
    const token = (getState() as RootState).auth.token
    if (token) {
      headers.set('Authorization', `Bearer ${token}`)
    }
    return headers
  },
})

export const historyApi = createApi({
  reducerPath: 'historyApi',
  baseQuery,
  tagTypes: ['History'],
  endpoints: (builder) => ({
    getConversations: builder.query<{ items: ConversationItem[] }, void>({
      query: () => '/conversations',
      providesTags: ['History'],
    }),
    getConversation: builder.query<{ items: TurnItem[] }, number>({
      query: (id) => `/conversations/${id}`,
      providesTags: ['History'],
    }),
  }),
})

export const { useGetConversationsQuery, useLazyGetConversationQuery } = historyApi
