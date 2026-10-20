import { configureStore } from '@reduxjs/toolkit'
import { authApi } from '../features/authApi'
import authReducer from '../features/authSlice'
import { historyApi } from '../features/historyApi'
import streamReducer from '../features/streamSlice'

export const store = configureStore({
  reducer: {
    auth: authReducer,
    stream: streamReducer,
    [authApi.reducerPath]: authApi.reducer,
    [historyApi.reducerPath]: historyApi.reducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware().concat(authApi.middleware, historyApi.middleware),
})

export type RootState = ReturnType<typeof store.getState>
export type AppDispatch = typeof store.dispatch
