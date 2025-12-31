'use client'

import { HardDrive, Battery, Wifi } from 'lucide-react'
import { useSessionStore } from '@/store/session'
import { cn } from '@/lib/utils'

export function StatusBar() {
  const { autonomyLevel } = useSessionStore()

  return (
    <div className="h-8 bg-slate-900 border-t border-slate-700 flex items-center justify-between px-4">
      <div className="flex items-center gap-4 text-xs text-slate-500">
        <div className="flex items-center gap-1.5">
          <HardDrive className="w-3.5 h-3.5" />
          <span>125 GB</span>
        </div>
        <div className="flex items-center gap-1.5">
          <Battery className="w-3.5 h-3.5" />
          <span>100%</span>
        </div>
        <div className="flex items-center gap-1.5">
          <Wifi className="w-3.5 h-3.5" />
          <span>Connected</span>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <div className={cn(
          "w-2 h-2 rounded-full",
          autonomyLevel === 'high' ? "bg-green-500" :
          autonomyLevel === 'medium' ? "bg-yellow-500" : "bg-red-500"
        )} />
        <span className="text-xs text-slate-400">
          AI Autonomy Level: <span className={cn(
            "font-medium",
            autonomyLevel === 'high' ? "text-green-400" :
            autonomyLevel === 'medium' ? "text-yellow-400" : "text-red-400"
          )}>
            {autonomyLevel.charAt(0).toUpperCase() + autonomyLevel.slice(1)}
          </span>
          {autonomyLevel === 'high' && (
            <span className="text-slate-500 ml-1">(User Oversight active)</span>
          )}
        </span>
      </div>
    </div>
  )
}
