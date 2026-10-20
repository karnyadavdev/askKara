import { createSlice } from '@reduxjs/toolkit'
import type { PayloadAction } from '@reduxjs/toolkit'

export const TOKEN_KEY = 'kara_token'

interface AuthState {
  token: string
}

const initialState: AuthState = {
  token: localStorage.getItem(TOKEN_KEY) || '',
}

const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    setToken(state, action: PayloadAction<string>) {
      state.token = action.payload
    },
  },
})

export const { setToken } = authSlice.actions
export default authSlice.reducer
