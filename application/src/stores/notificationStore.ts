import { create } from 'zustand'

export type NotificationLevel = 'info' | 'success' | 'warning' | 'error'

export interface Notification {
  id: string
  level: NotificationLevel
  message: string
  detail?: string
  duration?: number
}

interface NotificationState {
  notifications: Notification[]
  push: (notification: Omit<Notification, 'id'>) => void
  dismiss: (id: string) => void
}

export const useNotificationStore = create<NotificationState>()((set) => ({
  notifications: [],
  push: (notification) => {
    const id = `notif-${Date.now()}-${Math.random().toString(36).slice(2)}`
    set((state) => ({ notifications: [...state.notifications, { id, ...notification }] }))
    const duration = notification.duration ?? (notification.level === 'error' ? 8000 : 4000)
    setTimeout(() => {
      set((state) => ({ notifications: state.notifications.filter((n) => n.id !== id) }))
    }, duration)
  },
  dismiss: (id) => {
    set((state) => ({ notifications: state.notifications.filter((n) => n.id !== id) }))
  },
}))
