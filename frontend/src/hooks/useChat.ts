import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { parseIntent, ChatResponse } from '../components/chat/intentParser'

export interface ChatMsg {
  id: string
  role: 'user' | 'system'
  text: string
  timestamp: string
}

export function useChat() {
  const [messages, setMessages] = useState<ChatMsg[]>([
    {
      id: 'welcome',
      role: 'system',
      text: 'Welcome to CoTrader Chat. Ask me about your portfolio, agents, recommendations, or workflow. Type **help** for all commands.',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ])
  const [isProcessing, setIsProcessing] = useState(false)
  const navigate = useNavigate()

  const sendMessage = useCallback(async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed) return

    const userMsg: ChatMsg = {
      id: crypto.randomUUID(),
      role: 'user',
      text: trimmed,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }

    setMessages((prev) => [...prev, userMsg])
    setIsProcessing(true)

    let response: ChatResponse
    try {
      response = await parseIntent(trimmed)
    } catch {
      response = { text: 'Sorry, something went wrong processing your request.' }
    }

    const sysMsg: ChatMsg = {
      id: crypto.randomUUID(),
      role: 'system',
      text: response.text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }

    setMessages((prev) => [...prev, sysMsg])
    setIsProcessing(false)

    if (response.action === 'navigate' && response.navigateTo) {
      navigate(response.navigateTo)
    }
  }, [navigate])

  const clearMessages = useCallback(() => {
    setMessages([{
      id: 'welcome',
      role: 'system',
      text: 'Chat cleared. How can I help?',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }])
  }, [])

  return { messages, sendMessage, clearMessages, isProcessing }
}
