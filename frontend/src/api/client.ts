import axios from 'axios'

const baseURL = import.meta.env.VITE_API_URL || ''

export const api = axios.create({
  baseURL,
  timeout: 15_000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// JWT interceptor — placeholder for Phase 2 auth
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('cotrader_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('cotrader_token')
      // Phase 2: redirect to login
    }
    return Promise.reject(error)
  },
)
