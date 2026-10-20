import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react'
import type { RootState } from '../app/store'

export interface UserOut {
  id: number
  email: string
}

export interface TokenOut {
  access_token: string
  user: UserOut
}

export interface Credentials {
  email: string
  password: string
}

const baseQuery = fetchBaseQuery({
  baseUrl: '/api/auth',
  prepareHeaders: (headers, { getState }) => {
    const token = (getState() as RootState).auth.token
    if (token) {
      headers.set('Authorization', `Bearer ${token}`)
    }
    return headers
  },
})

export const authApi = createApi({
  reducerPath: 'authApi',
  baseQuery,
  tagTypes: ['AuthUser'],
  endpoints: (builder) => ({
    register: builder.mutation<TokenOut, Credentials>({
      query: (body) => ({ url: '/register', method: 'POST', body }),
    }),
    login: builder.mutation<TokenOut, Credentials>({
      query: (body) => ({ url: '/login', method: 'POST', body }),
    }),
    me: builder.query<UserOut, void>({
      query: () => '/me',
      providesTags: ['AuthUser'],
    }),
  }),
})

export const { useRegisterMutation, useLoginMutation, useMeQuery } = authApi
