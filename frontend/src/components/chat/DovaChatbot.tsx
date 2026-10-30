import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
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
import { rememberChatPreference } from '@/lib/chatPreferenceMemory'

interface ChatMessage {
  id: string
  sender: 'user' | 'ai'
  text: string
  timestamp: string
}

const QUICK_PROMPTS = [
  'Rekomendasi menu apa yang cocok buat saya?',
  'Menu apa yang paling laris & hari apa paling ramai?',
  'Cek menu terhadap alergi saya',
  'Bagaimana prediksi demand & menu harian AI?',
]

export function DovaChatbot() {
  const { customer } = useAuth()
  const navigate = useNavigate()
  const [isOpen, setIsOpen] = useState(false)
  const [inputMessage, setInputMessage] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [lastMode, setLastMode] = useState('Menunggu pertanyaan')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome-1',
      sender: 'ai',
      text: `Halo ${customer?.display_name || 'Kak'}! 👋 Saya Chef BOB, asisten menu Dova Kitchen. Tanyakan tentang menu atau alergi; saya akan merujuk ke katalog dan memberi tahu bila resep belum bisa diverifikasi.`,
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
          conversation_history: rememberChatPreference(customer?.customer_id || 'guest', text),
        },
      })
      if (res.reason_code === 'structured_preference_saved' || res.reason_code === 'structured_allergen_saved') {
        window.dispatchEvent(new Event('dova:passport-updated'))
      }

      const aiMsg: ChatMessage = {
        id: `ai-${Date.now()}`,
        sender: 'ai',
        text: res.degraded
          ? `${res.reply || 'Layanan AI belum tersedia.'}\n\nStatus: ${
              res.message || 'degraded; sumber AI perlu diverifikasi'
            }`
          : res.reply || 'Maaf, saya tidak dapat memahami pertanyaan tersebut. Bisa ulangi kembali?',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      }
      setLastMode(res.degraded
        ? res.provider === 'catalog_safety'
          ? 'Cek bahan · katalog live'
          : res.provider === 'catalog_preferences'
            ? 'Filter selera · katalog live'
            : 'AI sedang terbatas'
        : 'Siap menjawab')
      setMessages((prev) => [...prev, aiMsg])
    } catch {
      const fallbackMsg: ChatMessage = {
        id: `ai-err-${Date.now()}`,
        sender: 'ai',
        text: 'Chef BOB sedang tidak tersedia. Silakan coba lagi beberapa saat atau pilih menu setelah status AI kembali aktif.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      }
      setMessages((prev) => [...prev, fallbackMsg])
      setLastMode('Layanan AI tidak tersedia')
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
              ? 'bg-[#4b1720] text-white'
              : 'bg-gradient-to-r from-[#42151d] via-[#7e2933] to-[#a7353d] text-white shadow-rose-950/30'
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
                <Bot className="size-6 text-white" />
                <span className="absolute -top-1 -right-1 flex size-2.5">
                  <span className="absolute inline-flex h-full w-full rounded-full bg-amber-300/50"></span>
                  <span className="relative inline-flex size-2.5 rounded-full bg-amber-400"></span>
                </span>
              </div>
              <div className="text-left">
                <div className="flex items-center gap-1 font-bold text-sm tracking-tight leading-tight">
                  Tanya Chef BOB
                  <Sparkles className="size-3 text-amber-300" />
                </div>
                <div className="text-[11px] text-white/80 font-normal leading-none">Asisten menu Dova</div>
              </div>
            </>
          )}
        </button>
      </div>

      {/* Chat Window Dialog */}
      {isOpen && (
        <div className="fixed left-3 right-3 bottom-[calc(5.5rem+env(safe-area-inset-bottom))] z-50 flex h-[min(720px,calc(100dvh-8rem))] flex-col overflow-hidden rounded-3xl border border-[#ead9d0] bg-[#fffdfb] shadow-2xl animate-in fade-in slide-in-from-bottom-5 duration-300 sm:left-auto sm:right-6 sm:bottom-20 sm:w-[min(420px,calc(100vw-3rem))]">
          {/* Header */}
          <div className="bg-[radial-gradient(circle_at_80%_0%,rgba(246,198,167,.25),transparent_40%),linear-gradient(120deg,#3c1018,#8a2833)] p-4 text-white flex items-center justify-between shadow-md">
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
                <p className="text-xs text-white/80">Katering Presisi • {lastMode}</p>
              </div>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="rounded-full p-1.5 text-white/80 hover:bg-white/20 hover:text-white transition-colors"
            >
              <X className="size-5" />
            </button>
          </div>

          <div className="grid grid-cols-3 gap-2 border-b border-[#ead9d0] bg-[#fffdfb] p-3">
            {[
              { label: 'Lihat menu', path: '/order' },
              { label: 'Passport', path: '/passport' },
              { label: 'Pesanan', path: '/orders' },
            ].map((action) => (
              <button
                key={action.path}
                type="button"
                onClick={() => {
                  setIsOpen(false)
                  navigate(action.path)
                }}
                className="rounded-xl border border-[#ead9d0] bg-[#fff8f2] px-2 py-2 text-[11px] font-bold text-[#513b36] transition hover:border-[#c55a50] hover:bg-[#f8e6df] hover:text-[#7e2933]"
              >
                {action.label}
              </button>
            ))}
          </div>

          {/* Quick Prompts Carousel */}
          <div className="flex gap-2 overflow-x-auto border-b border-[#ead9d0] bg-[#fff8f2] px-3 py-2 no-scrollbar">
            {QUICK_PROMPTS.map((prompt, idx) => (
              <button
                key={idx}
                onClick={() => handleSendMessage(prompt)}
                disabled={isLoading}
                className="flex items-center gap-1 whitespace-nowrap rounded-full border border-[#ead9d0] bg-white px-3 py-1 text-xs text-[#513b36] shadow-sm transition-all hover:border-[#c55a50] hover:text-[#7e2933] active:scale-95"
              >
                <span>{prompt}</span>
                <ChevronRight className="size-3 text-stone-400" />
              </button>
            ))}
          </div>

          {/* Message History */}
          <div className="min-h-0 flex-1 space-y-3.5 overflow-y-auto bg-[#fffdfb] p-4">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={cn('flex flex-col', msg.sender === 'user' ? 'items-end' : 'items-start')}
              >
                <div
                  className={cn(
                    'max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-2xs',
                    msg.sender === 'user'
                      ? 'bg-[#9f2735] text-white rounded-tr-xs'
                      : 'bg-white text-[#392a27] border border-[#ead9d0] rounded-tl-xs whitespace-pre-line'
                  )}
                >
                  {msg.text}
                </div>
                <span className="text-[10px] text-stone-400 mt-1 px-1">{msg.timestamp}</span>
              </div>
            ))}

            {isLoading && (
              <div className="flex items-center gap-2 text-stone-500 bg-white border border-stone-200 rounded-2xl px-4 py-2.5 text-xs w-fit">
                <RefreshCw className="size-3.5 animate-spin text-[#9f2735]" />
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
              className="flex items-center gap-2 border-t border-[#ead9d0] bg-[#fffdfb] p-3"
          >
            <Input
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              placeholder="Tanya alergi, menu, atau nutrisi..."
              className="flex-1 rounded-full border-[#ead9d0] bg-[#fff8f2] px-4 text-sm focus-visible:ring-rose-500"
              disabled={isLoading}
            />
            <Button
              type="submit"
              size="icon"
              disabled={!inputMessage.trim() || isLoading}
              className="size-10 shrink-0 rounded-full bg-[#8f2833] text-white shadow-md shadow-rose-900/20 hover:bg-[#711f2b]"
            >
              <Send className="size-4" />
            </Button>
          </form>
        </div>
      )}
    </>
  )
}
