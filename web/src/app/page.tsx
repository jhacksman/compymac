'use client'

import { Panel, Group as PanelGroup, Separator as PanelResizeHandle } from 'react-resizable-panels'
import { HistorySidebar } from '@/components/layout/HistorySidebar'
import { ConversationPanel } from '@/components/layout/ConversationPanel'
import { AgentWorkspace } from '@/components/workspace/AgentWorkspace'
import { StatusBar } from '@/components/layout/StatusBar'

export default function Home() {
  return (
    <div className="h-screen flex flex-col bg-slate-950">
      <div className="flex-1 flex min-h-0">
        <HistorySidebar />
        <PanelGroup direction="horizontal" className="flex-1">
          <Panel defaultSize={40} minSize={30}>
            <ConversationPanel />
          </Panel>
          <PanelResizeHandle className="w-1 bg-slate-800 hover:bg-blue-500 transition-colors cursor-col-resize" />
          <Panel defaultSize={60} minSize={40}>
            <AgentWorkspace />
          </Panel>
        </PanelGroup>
      </div>
      <StatusBar />
    </div>
  )
}
