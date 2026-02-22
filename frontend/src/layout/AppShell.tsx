import { ReactNode } from 'react'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'
import { StatusBar } from './StatusBar'
import { ChatPanel } from '../components/chat/ChatPanel'

interface AppShellProps {
  children: ReactNode
}

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <div className="flex flex-col flex-1 overflow-hidden">
          <TopBar />
          <main className="flex-1 overflow-auto bg-bg-secondary p-3">
            <div className="max-w-[1600px] mx-auto">
              {children}
            </div>
          </main>
          <StatusBar />
        </div>
      </div>
      <ChatPanel />
    </div>
  )
}
