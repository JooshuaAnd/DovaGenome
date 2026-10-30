import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Bot,
  Send,
  ShieldCheck,
  Sparkles,
  User,
} from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { SafetyBadge } from '@/components/safety/SafetyBadge'
import { useAuth } from '@/hooks/useAuth'
import { useServiceWeek, zipDayOptions } from '@/hooks/useServiceWeek'
import { cn } from '@/lib/utils'
import { rememberChatPreference } from '@/lib/chatPreferenceMemory'
import { aiService } from '@/services/ai'
import { customersService } from '@/services/customers'
import type { Passport } from '@/types'

interface Message {
  id: string
  sender: 'bob' | 'user'
  text: string
  time: string
  isAction?: boolean
}

const QUICK_PROMPTS = [
  'Cek menu terhadap alergi saya',
  'Rekomendasikan menu makan siang paling bergizi',
  'Kenapa hari Jumat pesanan paling ramai & apa menu terlaris?',
  'Bagaimana saya mencatat alergi di profil?',
  'Cek bahan dan resep Ayam Panggang Rosemary',
]

export function AiPage() {
  const { customer, isAuthenticated } = useAuth()
  const navigate = useNavigate()
  const serviceWeek = useServiceWeek()
  const [passport, setPassport] = useState<Passport | null>(null)
  const [rfmSegment, setRfmSegment] = useState<string>('Belum tersedia')
  const [inputText, setInputText] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      sender: 'bob',
      text: `Halo! 👋 Saya Chef BOB, asisten menu Dova Kitchen. Tanyakan bahan, menu, atau pantanganmu. Saya akan merujuk ke data katalog yang tersedia dan memberi tahu kalau ada hal yang belum bisa dipastikan. Ada yang bisa saya bantu?`,
      time: 'Baru saja',
    },
  ])

  // Fetch dietary passport and customer loyalty status
  useEffect(() => {
    if (isAuthenticated) {
      customersService
        .getPassport()
        .then((p) => {
          if (p) setPassport(p)
        })
        .catch(() => null)
    }

    if (isAuthenticated && customer?.customer_id) {
      customersService
        .getRfm(customer.customer_id)
        .then((data) => {
          if (data && data.segment && data.segment !== 'NO_HISTORY') {
            setRfmSegment(data.segment)
          }
        })
        .catch(() => null)
    }
  }, [isAuthenticated, customer])

  // Auto-scroll to bottom of chat
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const userAllergens = passport?.allergies?.map((a) => a.label || a.code) || []
  const userAvoids = passport?.avoided_ingredients || []
  const menuRecommendations = serviceWeek.days.flatMap((day) =>
    zipDayOptions(day).map(({ menu, safety }) => ({ menu, day, safety })),
  ).filter((item) => item.safety?.level === 'safe' && item.safety.is_recommended).slice(0, 3)

  const handleSendMessage = async (textToSend?: string) => {
    const text = (textToSend || inputText).trim()
    if (!text || loading) return

    const userMsg: Message = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text,
      time: new Date().toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' }),
    }

    setMessages((prev) => [...prev, userMsg])
    setInputText('')
    setLoading(true)

    try {
      const response = await aiService.consult({
        message: text,
        session_id: customer?.customer_id || 'guest_web',
        context: {
          customer_name: customer?.display_name || customer?.username || 'Tamu',
          allergens: userAllergens.join(', '),
          loyalty_segment: rfmSegment,
          conversation_history: rememberChatPreference(customer?.customer_id || 'guest', text),
        },
      })
      if ((response.reason_code === 'structured_preference_saved' || response.reason_code === 'structured_allergen_saved') && isAuthenticated) {
        customersService.getPassport().then(setPassport).catch(() => null)
        window.dispatchEvent(new Event('dova:passport-updated'))
      }

      const degradedNote = response.degraded
        ? `\n\nStatus: ${response.message || 'Layanan AI utama sedang tidak tersedia.'}`
        : ''
      const bobMsg: Message = {
        id: `bob-${Date.now()}`,
        sender: 'bob',
        text: `${response.reply || 'Chef BOB belum punya jawaban untuk pertanyaan itu.'}${degradedNote}`,
        time: new Date().toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' }),
      }

      setMessages((prev) => [...prev, bobMsg])
    } catch {
      toast.error('Gagal terhubung dengan Chef BOB.')
      const errorMsg: Message = {
        id: `bob-err-${Date.now()}`,
        sender: 'bob',
        text:
          'Maaf, layanan chat sedang tidak tersambung. Aku belum bisa memastikan jawaban untuk pertanyaan ini. Coba kirim lagi sebentar lagi atau cek pantangan dan status resep di Passport/Menu.',
        time: new Date().toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' }),
      }
      setMessages((prev) => [...prev, errorMsg])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* ── 1. Top Executive Banner (Chef BOB & IBM BOB Engine) ── */}
      <div className="relative overflow-hidden rounded-3xl bg-[radial-gradient(circle_at_90%_10%,rgba(246,198,167,.24),transparent_33%),linear-gradient(120deg,#3c1018,#711f2b_58%,#a7353d)] p-6 md:p-8 text-white shadow-xl shadow-rose-950/15 border border-rose-900">
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="flex items-start gap-4">
            <div className="size-16 rounded-2xl bg-[#f2c7aa] flex items-center justify-center text-[#4a151e] shadow-lg shadow-black/20 shrink-0">
              <Bot className="size-8" />
            </div>

            <div className="space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-xl md:text-2xl font-black tracking-tight text-white">
                  Chef BOB
                </h1>
                <Badge className="bg-white/10 text-gold-200 font-semibold text-[10px] tracking-wider px-2 py-0.5 border border-white/15">
                  ASISTEN MENU
                </Badge>
              </div>

              <p className="text-xs md:text-sm text-slate-200 max-w-xl">
                Tanya menu, bahan, dan pantanganmu. Status kecocokan menu selalu diperiksa dari katalog dapur.
              </p>
            </div>
          </div>

          {/* Customer Personal Health & Loyalty Pill */}
          <div className="bg-black/15 backdrop-blur-md rounded-2xl p-3.5 border border-white/15 flex flex-col gap-2 shrink-0 md:min-w-[260px]">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-medium text-stone-300">Profil Pelanggan:</span>
              <Badge className="border-none bg-white/15 px-2 py-0.5 text-[10px] font-bold text-white">
                {rfmSegment}
              </Badge>
            </div>

            <div className="flex items-center gap-2 text-xs font-bold text-white">
              <ShieldCheck className="size-4 text-emerald-400 shrink-0" />
              <span className="truncate">
                {[
                  userAllergens.length ? `Alergi: ${userAllergens.join(', ')}` : '',
                  userAvoids.length ? `Tidak suka: ${userAvoids.join(', ')}` : '',
                  passport?.nutrition_goal === 'high_fat_high_protein' ? 'Target: tinggi lemak & protein' : '',
                  passport?.nutrition_goal === 'high_protein' ? 'Fokus protein' : '',
                  passport?.nutrition_goal === 'high_fat' ? 'Fokus lemak' : '',
                  passport?.nutrition_goal === 'low_fat' ? 'Pilihan rendah lemak' : '',
                  passport?.nutrition_goal === 'fat_loss' ? 'Target: mengurangi lemak tubuh' :
                    passport?.nutrition_goal === 'lighter' ? 'Fokus: makan lebih ringan' : '',
                ].filter(Boolean).join(' · ') || 'Belum ada pantangan tersimpan'}
              </span>
            </div>

            <div className="flex items-center justify-between pt-1 border-t border-white/10 text-[10px] text-stone-300">
              <span>{customer?.display_name || 'Pelanggan Tamu'}</span>
              <Link to="/passport" className="text-amber-300 underline hover:text-amber-200">
                Ubah Profil →
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* ── 2. Grid Layout: Safe Recommendations + Interactive Live Chat ── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Recommended Safe Dishes for User (lg: 5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          <div className="flex items-center justify-between">
              <h2 className="font-extrabold text-base text-ink flex items-center gap-2">
              <Sparkles className="size-4 text-amber-500" />
              Pilihan dari katalog live
            </h2>
            <Link to="/order" className="text-xs font-bold text-forest-800 hover:underline">
              Lihat Semua →
            </Link>
          </div>

          <div className="space-y-3">
            {serviceWeek.loading ? (
              <div className="rounded-2xl border border-line bg-surface p-5 text-sm text-muted-text">Memuat katalog dan status kecocokan…</div>
            ) : menuRecommendations.length > 0 ? menuRecommendations.map(({ menu, day, safety }) => (
              <article key={menu.menu_id} className="rounded-2xl border border-line bg-surface p-4 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-xs font-bold text-forest-700">{day.hari} · {day.date_label}</p>
                    <h3 className="mt-1 font-bold leading-snug text-ink">{menu.nama_menu}</h3>
                    <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-muted-text">{menu.deskripsi}</p>
                  </div>
                  {safety && <SafetyBadge level={safety.level} />}
                </div>
                {menu.allergen_labels.length > 0 && <p className="mt-3 text-xs text-muted-text">Mengandung: {menu.allergen_labels.join(', ')}</p>}
                <Button size="sm" onClick={() => navigate('/order')} className="mt-3 h-8 rounded-full bg-forest-900 px-4 text-xs text-white hover:bg-forest-800">Lihat di menu</Button>
              </article>
            )) : (
              <div className="rounded-2xl border border-caution-line bg-caution-soft p-5 text-sm text-caution-strong">
                {serviceWeek.error ? 'Menu live belum dapat dimuat. Coba lagi beberapa saat.' : 'Belum ada resep yang lolos untuk disebut aman. Status resep yang belum diverifikasi tetap ditampilkan di katalog.'}
                <Button variant="outline" size="sm" onClick={() => navigate('/order')} className="mt-3 block rounded-full">Buka katalog</Button>
              </div>
            )}
          </div>

          <div className="rounded-2xl border border-caution-line bg-caution-soft p-4 text-xs text-caution-strong">
            <p className="font-bold">Pemeriksaan alergi dari katalog dapur</p>
            <p className="mt-1 leading-relaxed">Resep yang belum diverifikasi tidak diberi label aman. Simpan pantangan di profil agar ikut diperiksa saat memesan.</p>
          </div>
        </div>

        {/* Right Column: Live Interactive Conversation with Chef BOB (lg: 7 cols) */}
        <div className="lg:col-span-7 bg-surface rounded-3xl border border-line shadow-sm flex flex-col min-h-[600px] h-[min(760px,calc(100dvh-12rem))] overflow-hidden">
          {/* Chat Header */}
          <div className="px-5 py-4 border-b border-line flex items-center justify-between bg-canvas/70">
            <div className="flex items-center gap-3">
              <div className="size-10 rounded-2xl bg-forest-900 text-gold-300 flex items-center justify-center font-black">
                <Bot className="size-5" />
              </div>
              <div>
                <h3 className="font-extrabold text-sm text-ink flex items-center gap-1.5">
                  Chef BOB
                </h3>
                <p className="text-[11px] text-muted-text">Asisten menu · jawaban berbasis layanan tersedia</p>
              </div>
            </div>

            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setMessages([
                  {
                    id: 'welcome-reset',
                    sender: 'bob',
                    text: `Percakapan baru dimulai! Halo ${
                      customer?.display_name || 'Kak'
                    }, apa yang ingin Anda tanyakan seputar menu dan diet sehat hari ini?`,
                    time: 'Baru saja',
                  },
                ])
              }}
              className="rounded-full text-xs border-stone-200 text-stone-600"
            >
              Reset Chat
            </Button>
          </div>

          {/* Quick Prompt Chips */}
          <div className="px-4 py-2.5 border-b border-stone-100 bg-white flex gap-2 overflow-x-auto no-scrollbar">
            {QUICK_PROMPTS.map((prompt, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => handleSendMessage(prompt)}
                disabled={loading}
                className="whitespace-nowrap text-[11px] font-semibold text-stone-700 bg-stone-100 hover:bg-amber-100 hover:text-amber-900 px-3 py-1.5 rounded-full transition-colors shrink-0"
              >
                {prompt}
              </button>
            ))}
          </div>

          {/* Messages Stream */}
          <div className="flex-1 p-5 overflow-y-auto space-y-4 bg-[#FAF7F2]/50">
            {messages.map((msg) => {
              const isBob = msg.sender === 'bob'
              return (
                <div
                  key={msg.id}
                  className={cn('flex gap-3 max-w-[88%]', isBob ? 'self-start' : 'ml-auto flex-row-reverse')}
                >
                  <div
                    className={cn(
                      'size-8 rounded-full flex items-center justify-center text-xs font-bold shrink-0 mt-0.5',
                      isBob
                        ? 'bg-stone-900 text-amber-300'
                        : 'bg-rose-600 text-white'
                    )}
                  >
                    {isBob ? <Bot className="size-4" /> : <User className="size-4" />}
                  </div>

                  <div className="space-y-1">
                    <div
                      className={cn(
                        'p-4 rounded-3xl text-xs md:text-sm leading-relaxed shadow-2xs whitespace-pre-line',
                        isBob
                          ? 'bg-white text-stone-800 border border-stone-200/80 rounded-tl-none'
                          : 'bg-rose-600 text-white rounded-tr-none font-medium'
                      )}
                    >
                      {msg.text}
                    </div>
                    <p
                      className={cn(
                        'text-[10px] text-stone-400 px-1',
                        !isBob && 'text-right'
                      )}
                    >
                      {msg.time}
                    </p>
                  </div>
                </div>
              )
            })}

            {loading && (
              <div className="flex gap-3 max-w-[80%]">
                <div className="size-8 rounded-full bg-stone-900 text-amber-300 flex items-center justify-center shrink-0">
                  <Bot className="size-4 animate-spin" />
                </div>
                <div className="p-4 rounded-3xl rounded-tl-none bg-white border border-stone-200 text-xs text-stone-500 flex items-center gap-1.5 shadow-2xs">
                  <span className="size-2 rounded-full bg-amber-400 animate-bounce" />
                  <span className="size-2 rounded-full bg-rose-500 animate-bounce [animation-delay:0.2s]" />
                  <span className="size-2 rounded-full bg-stone-800 animate-bounce [animation-delay:0.4s]" />
                  <span className="ml-1 font-medium">Chef BOB sedang meracik jawaban...</span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Box Footer */}
          <div className="p-4 bg-white border-t border-stone-100">
            <form
              onSubmit={(e) => {
                e.preventDefault()
                handleSendMessage()
              }}
              className="flex items-center gap-2"
            >
              <Input
                type="text"
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder="Tanya Chef BOB tentang menu, alergi, atau jadwal masak..."
                disabled={loading}
                className="flex-1 rounded-full bg-stone-50 border-stone-200 px-4 py-2.5 text-xs md:text-sm focus-visible:ring-rose-500"
              />
              <Button
                type="submit"
                disabled={!inputText.trim() || loading}
                className="size-10 rounded-full bg-rose-600 hover:bg-rose-700 text-white p-0 shrink-0 shadow-md shadow-rose-600/20"
              >
                <Send className="size-4" />
              </Button>
            </form>
          </div>
        </div>
      </div>
    </div>
  )
}
