import { create } from 'zustand'

export type ToastType = 'success' | 'error' | 'warning' | 'info'

interface Toast {
  id: string
  message: string
  type: ToastType
  duration?: number
}

interface UIState {
  // Toast notifications
  toasts: Toast[]

  // Global loading state
  isGlobalLoading: boolean
  globalLoadingMessage: string

  // Modal states
  activeModal: string | null
  modalData: Record<string, unknown> | null | undefined

  // Sidebar state
  isSidebarOpen: boolean

  // Theme (future)
  theme: 'light' | 'dark' | 'system'

  // Actions
  addToast: (message: string, type: ToastType, duration?: number) => void
  removeToast: (id: string) => void
  clearAllToasts: () => void

  setGlobalLoading: (loading: boolean, message?: string) => void

  openModal: (modalName: string, data?: Record<string, unknown> | null) => void
  closeModal: () => void

  toggleSidebar: () => void
  setSidebarOpen: (open: boolean) => void

  setTheme: (theme: 'light' | 'dark' | 'system') => void
}

export const useUIStore = create<UIState>((set, get) => ({
  // Initial state
  toasts: [],
  isGlobalLoading: false,
  globalLoadingMessage: '',
  activeModal: null,
  modalData: null,
  isSidebarOpen: true,
  theme: 'light',

  // Actions
  addToast: (message, type, duration = 5000) => {
    const id = Math.random().toString(36).substring(2, 9)
    const toast: Toast = { id, message, type, duration }

    set((state) => ({ toasts: [...state.toasts, toast] }))

    // Auto-remove after duration
    if (duration > 0) {
      setTimeout(() => {
        get().removeToast(id)
      }, duration)
    }
  },

  removeToast: (id) => {
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    }))
  },

  clearAllToasts: () => {
    set({ toasts: [] })
  },

  setGlobalLoading: (loading, message = '') => {
    set({ isGlobalLoading: loading, globalLoadingMessage: message })
  },

  openModal: (modalName, data = null) => {
    set({ activeModal: modalName, modalData: data })
  },

  closeModal: () => {
    set({ activeModal: null, modalData: null })
  },

  toggleSidebar: () => {
    set((state) => ({ isSidebarOpen: !state.isSidebarOpen }))
  },

  setSidebarOpen: (open) => {
    set({ isSidebarOpen: open })
  },

  setTheme: (theme) => {
    set({ theme })
  },
}))
