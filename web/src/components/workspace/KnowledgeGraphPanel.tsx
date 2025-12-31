'use client'

import { Share2, Maximize2, Minimize2 } from 'lucide-react'
import { cn } from '@/lib/utils'

interface KnowledgeGraphPanelProps {
  isMaximized?: boolean
  onMaximize?: () => void
}

const nodes = [
  { id: 1, label: 'DeFi', x: 50, y: 30, size: 'lg' },
  { id: 2, label: 'Stablecoins', x: 20, y: 50, size: 'md' },
  { id: 3, label: 'Smart Contracts', x: 80, y: 20, size: 'md' },
  { id: 4, label: 'Regulatory Landscape', x: 50, y: 70, size: 'md' },
  { id: 5, label: 'Yield', x: 15, y: 25, size: 'sm' },
  { id: 6, label: 'Security', x: 85, y: 55, size: 'sm' },
  { id: 7, label: 'Blockchain', x: 30, y: 80, size: 'sm' },
  { id: 8, label: 'Smart Contract', x: 70, y: 75, size: 'sm' },
]

const edges = [
  { from: 1, to: 2 },
  { from: 1, to: 3 },
  { from: 1, to: 4 },
  { from: 2, to: 5 },
  { from: 2, to: 7 },
  { from: 3, to: 6 },
  { from: 4, to: 7 },
  { from: 4, to: 8 },
]

export function KnowledgeGraphPanel({ isMaximized, onMaximize }: KnowledgeGraphPanelProps) {
  return (
    <div className={cn(
      "flex flex-col bg-slate-900 rounded-xl overflow-hidden border border-slate-700",
      isMaximized ? "h-full" : "h-full"
    )}>
      <div className="flex items-center justify-between px-3 py-2 bg-slate-800 border-b border-slate-700">
        <div className="flex items-center gap-2">
          <Share2 className="w-4 h-4 text-purple-400" />
          <span className="text-sm font-medium text-white">Knowledge Graph</span>
        </div>
        <button 
          onClick={onMaximize}
          className="p-1 text-slate-400 hover:text-white transition-colors"
        >
          {isMaximized ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
        </button>
      </div>

      <div className="flex-1 p-3 relative overflow-hidden">
        <svg className="w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet">
          {edges.map((edge, i) => {
            const fromNode = nodes.find(n => n.id === edge.from)
            const toNode = nodes.find(n => n.id === edge.to)
            if (!fromNode || !toNode) return null
            return (
              <line
                key={i}
                x1={fromNode.x}
                y1={fromNode.y}
                x2={toNode.x}
                y2={toNode.y}
                stroke="#475569"
                strokeWidth="0.3"
              />
            )
          })}
          {nodes.map((node) => (
            <g key={node.id}>
              <circle
                cx={node.x}
                cy={node.y}
                r={node.size === 'lg' ? 6 : node.size === 'md' ? 4 : 3}
                className={cn(
                  node.size === 'lg' ? "fill-purple-500" :
                  node.size === 'md' ? "fill-blue-500" : "fill-slate-500"
                )}
              />
              <text
                x={node.x}
                y={node.y + (node.size === 'lg' ? 10 : node.size === 'md' ? 8 : 6)}
                textAnchor="middle"
                className="fill-slate-400 text-[3px]"
              >
                {node.label}
              </text>
            </g>
          ))}
        </svg>
      </div>
    </div>
  )
}
