import { useState, useRef, useEffect } from 'react'
import {
  Bot,
  X,
  Send,
  Sparkles,
  ChevronRight,
  RefreshCw,
  Utensils,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { aiService } from '@/services/ai'
import { useAuth } from '@/hooks/useAuth'
import { cn } from '@/lib/utils'

interface ChatMessage {
  id: string
  sender: 'user' | 'ai'
  text: string
  timestamp: string
}

const QUICK_PROMPTS = [
  'Rekomendasi menu apa yang cocok buat saya?',
  'Menu apa yang paling laris & hari apa paling ramai?',
  'Apakah Ayam Panggang Rosemary aman dari alergi?',
  'Bagaimana prediksi demand & menu harian AI?',
]

export function DovaChatbot() {
  const { customer } = useAuth()
  const [isOpen, setIsOpen] = useState(false)
  const [inputMessage, setInputMessage] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome-1',
      sender: 'ai',
      text: `Halo ${customer?.display_name || 'Kak'}! 👨‍🍳 Saya Chef BOB, asisten katering presisi pribadimu di Dova Kitchen. Mau cari rekomendasi menu yang 100% aman dari alergi, cek menu paling laris, atau tanya prediksi tren pesanan minggu ini? Tanya ke Chef BOB yuk!`,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ])

  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, isOpen])

  async function handleSendMessage(textToSend?: string) {
    const text = (textToSend || inputMessage).trim()
    if (!text || isLoading) return

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }

    setMessages((prev) => [...prev, userMsg])
    setInputMessage('')
    setIsLoading(true)

    try {
      const res = await aiService.consult({
        message: text,
        session_id: customer?.customer_id || `guest-${Date.now()}`,
        context: {
          customer_name: customer?.display_name || customer?.username || 'Pelanggan',
        },
      })

      const aiMsg: ChatMessage = {
        id: `ai-${Date.now()}`,
        sender: 'ai',
        text: res.reply || 'Maaf, saya tidak dapat memahami pertanyaan tersebut. Bisa ulangi kembali?',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      }
      setMessages((prev) => [...prev, aiMsg])
    } catch {
      const fallbackMsg: ChatMessage = {
        id: `ai-err-${Date.now()}`,
        sender: 'ai',
        text: 'Halo! Chef BOB di Dova Kitchen selalu memastikan hidangan sehatmu bebas dari risiko kontaminasi alergi. Silakan langsung pilih menu harian favoritmu!',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      }
      setMessages((prev) => [...prev, fallbackMsg])
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <>
      {/* Floating Trigger Button */}
      <div className="fixed bottom-20 right-4 z-50 md:bottom-6 md:right-6">
        <button
          type="button"
          onClick={() => setIsOpen(!isOpen)}
          className={cn(
            'group relative flex items-center gap-2.5 rounded-full px-4 py-3 shadow-xl transition-all duration-300 hover:scale-105 active:scale-95',
            isOpen
              ? 'bg-slate-800 text-white'
              : 'bg-gradient-to-r from-red-600 via-rose-600 to-amber-600 text-white shadow-rose-600/30'
          )}
          aria-label="Tanya Chef BOB"
        >
          {isOpen ? (
            <>
              <X className="size-5 transition-transform group-hover:rotate-90" />
              <span className="font-medium text-sm">Tutup Chat</span>
            </>
          ) : (
            <>
              <div className="relative">
                <Bot className="size-6 text-white animate-bounce" />
                <span className="absolute -top-1 -right-1 flex size-2.5">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-300 opacity-75"></span>
                  <span className="relative inline-flex size-2.5 rounded-full bg-amber-400"></span>
                </span>
              </div>
              <div className="text-left">
                <div className="flex items-center gap-1 font-bold text-sm tracking-tight leading-tight">
                  Tanya Chef BOB
                  <Sparkles className="size-3 text-amber-300" />
                </div>
                <div className="text-[11px] text-white/80 font-normal leading-none">Online & Cepat</div>
              </div>
            </>
          )}
        </button>
      </div>

      {/* Chat Window Dialog */}
      {isOpen && (
        <div className="fixed inset-x-2 bottom-36 z-50 max-h-[80vh] sm:inset-x-auto sm:right-6 sm:bottom-20 sm:w-[420px] rounded-3xl bg-white shadow-2xl border border-stone-200 overflow-hidden flex flex-col animate-in fade-in slide-in-from-bottom-5 duration-300">
          {/* Header */}
          <div className="bg-gradient-to-r from-red-600 to-rose-700 p-4 text-white flex items-center justify-between shadow-md">
            <div className="flex items-center gap-3">
              <div className="relative flex size-11 items-center justify-center rounded-2xl bg-white/15 backdrop-blur-md border border-white/20">
                <Utensils className="size-5 text-amber-300" />
                <span className="absolute -bottom-0.5 -right-0.5 size-3 rounded-full bg-emerald-400 border-2 border-rose-700" />
              </div>
              <div>
                <h3 className="font-bold text-base leading-tight flex items-center gap-1.5">
                  Chef BOB
                  <Badge className="bg-amber-400/20 text-amber-200 border-amber-300/30 text-[10px] px-1.5 py-0 h-4">
                    AI Precision Chef
                  </Badge>
                </h3>
                <p className="text-xs text-white/80">Katering Presisi • Siap Konsultasi</p>
              </div>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="rounded-full p-1.5 text-white/80 hover:bg-white/20 hover:text-white transition-colors"
            >
              <X className="size-5" />
            </button>
          </div>

          {/* Quick Prompts Carousel */}
          <div className="bg-stone-50/90 border-b border-stone-200/80 px-3 py-2 overflow-x-auto no-scrollbar flex gap-2">
            {QUICK_PROMPTS.map((prompt, idx) => (
              <button
                key={idx}
                onClick={() => handleSendMessage(prompt)}
                disabled={isLoading}
                className="whitespace-nowrap text-xs bg-white text-stone-700 hover:text-rose-600 hover:border-rose-300 border border-stone-200 rounded-full px-3 py-1 transition-all flex items-center gap-1 shadow-2xs active:scale-95"
              >
                <span>{prompt}</span>
                <ChevronRight className="size-3 text-stone-400" />
              </button>
            ))}
          </div>

          {/* Message History */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3.5 max-h-[380px] bg-stone-50/40">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={cn('flex flex-col', msg.sender === 'user' ? 'items-end' : 'items-start')}
              >
                <div
                  className={cn(
                    'max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-2xs',
                    msg.sender === 'user'
                      ? 'bg-rose-600 text-white rounded-tr-xs'
                      : 'bg-white text-stone-800 border border-stone-200/90 rounded-tl-xs whitespace-pre-line'
                  )}
                >
                  {msg.text}
                </div>
                <span className="text-[10px] text-stone-400 mt-1 px-1">{msg.timestamp}</span>
              </div>
            ))}

            {isLoading && (
              <div className="flex items-center gap-2 text-stone-500 bg-white border border-stone-200 rounded-2xl px-4 py-2.5 text-xs w-fit">
                <RefreshCw className="size-3.5 animate-spin text-rose-500" />
                <span>AI Chef sedang menganalisis menu & bahan...</span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Footer */}
          <form
            onSubmit={(e) => {
              e.preventDefault()
              handleSendMessage()
            }}
            className="p-3 bg-white border-t border-stone-200 flex items-center gap-2"
          >
            <Input
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              placeholder="Tanya alergi, menu, atau nutrisi..."
              className="flex-1 rounded-full border-stone-300 bg-stone-50/80 px-4 text-sm focus-visible:ring-rose-500"
              disabled={isLoading}
            />
            <Button
              type="submit"
              size="icon"
              disabled={!inputMessage.trim() || isLoading}
              className="rounded-full bg-rose-600 hover:bg-rose-700 text-white size-10 shrink-0 shadow-md shadow-rose-600/20"
            >
              <Send className="size-4" />
            </Button>
          </form>
        </div>
      )}
    </>
  )
}
