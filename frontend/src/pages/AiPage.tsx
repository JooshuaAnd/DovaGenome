import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  ArrowRight,
  Bot,
  CheckCircle2,
  Send,
  ShieldCheck,
  Sparkles,
  User,
} from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useAuth } from '@/hooks/useAuth'
import { cn } from '@/lib/utils'
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
  'Menu apa yang 100% aman dari alergi saya?',
  'Rekomendasikan menu makan siang paling bergizi',
  'Kenapa hari Jumat pesanan paling ramai & apa menu terlaris?',
  'Bagaimana katering Dova menjamin nol kontaminasi silang?',
  'Cek bahan dan resep Ayam Panggang Rosemary',
]

const SAMPLE_SAFE_MENUS = [
  {
    name: 'Ayam Panggang Rosemary & Ubi Madu',
    day: 'Senin',
    calories: '480 kcal',
    price: 42000,
    safeTag: 'Bebas Kacang & Seafood',
    image:
      'https://images.unsplash.com/photo-1598515214211-89d3c73ae83b?auto=format&fit=crop&w=600&q=80',
  },
  {
    name: 'Beef Bulgogi Wijen & Nasi Beras Cokelat',
    day: 'Selasa',
    calories: '520 kcal',
    price: 42000,
    safeTag: 'Tinggi Protein Presisi',
    image:
      'https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=600&q=80',
  },
  {
    name: 'Fillet Dori Panggang Lemon & Salad Jagung',
    day: 'Kamis',
    calories: '450 kcal',
    price: 42000,
    safeTag: 'Rendah Karbohidrat Sehat',
    image:
      'https://images.unsplash.com/photo-1519708227418-c8fd9a32b7a2?auto=format&fit=crop&w=600&q=80',
  },
]

export function AiPage() {
  const { customer, isAuthenticated } = useAuth()
  const navigate = useNavigate()
  const [passport, setPassport] = useState<Passport | null>(null)
  const [rfmSegment, setRfmSegment] = useState<string>('Champions')
  const [inputText, setInputText] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      sender: 'bob',
      text: `Halo! 👋 Saya Chef BOB, asisten kuliner & katering presisi pribadimu di Dova Kitchen. Saya siap membantumu memilih menu lezat yang 100% aman dari riwayat alergimu, menganalisis gizi, dan merencanakan katering mingguan. Ada yang bisa saya bantu hari ini?`,
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

    const cid = customer?.customer_id || 'cust_ml_001'
    customersService
      .getRfm(cid)
      .then((data) => {
        if (data && data.segment) {
          setRfmSegment(data.segment)
        }
      })
      .catch(() => null)
  }, [isAuthenticated, customer])

  // Auto-scroll to bottom of chat
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const userAllergens = passport?.allergies?.map((a) => a.label || a.code) || []

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
        },
      })

      const bobMsg: Message = {
        id: `bob-${Date.now()}`,
        sender: 'bob',
        text:
          response.reply ||
          'Terima kasih telah bertanya kepada Chef BOB. Semua menu Dova Kitchen disiapkan di workstation steril higienis dengan pemisahan bahan alergen ketat.',
        time: new Date().toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' }),
      }

      setMessages((prev) => [...prev, bobMsg])
    } catch {
      toast.error('Gagal terhubung dengan Chef BOB.')
      const errorMsg: Message = {
        id: `bob-err-${Date.now()}`,
        sender: 'bob',
        text:
          'Maaf, koneksi ke mesin AI Chef sedang sibuk. Namun Anda dapat yakin bahwa seluruh menu Dova Kitchen selalu melewati filter keamanan resep otomatis sebelum disajikan.',
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
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-stone-900 via-rose-950 to-stone-900 p-6 md:p-8 text-white shadow-xl shadow-rose-950/10 border border-rose-900/40">
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="flex items-start gap-4">
            <div className="size-16 rounded-2xl bg-gradient-to-tr from-amber-400 to-rose-500 flex items-center justify-center text-stone-950 shadow-lg shadow-amber-500/20 shrink-0">
              <Bot className="size-8" />
            </div>

            <div className="space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-xl md:text-2xl font-black tracking-tight text-white">
                  Chef BOB
                </h1>
                <Badge className="bg-amber-400 text-stone-950 font-black text-[10px] tracking-wider px-2 py-0.5 border-none">
                  AI PRECISION CHEF
                </Badge>
                <Badge className="bg-white/10 text-rose-300 font-mono text-[10px] border border-rose-400/30">
                  Powered by IBM BOB Engine
                </Badge>
              </div>

              <p className="text-xs md:text-sm text-stone-300 max-w-xl">
                Asisten kecerdasan kuliner presisi yang memahami Dietary Passport kesehatan Anda,
                riwayat transaksi, dan keamanan resep tanpa kompromi.
              </p>
            </div>
          </div>

          {/* Customer Personal Health & Loyalty Pill */}
          <div className="bg-white/10 backdrop-blur-md rounded-2xl p-3.5 border border-white/10 flex flex-col gap-2 shrink-0 md:min-w-[260px]">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-medium text-stone-300">Profil Pelanggan:</span>
              <Badge
                className={cn(
                  'text-[10px] font-bold px-2 py-0.5 border-none',
                  rfmSegment === 'Champions'
                    ? 'bg-amber-400 text-stone-950'
                    : rfmSegment === 'At Risk'
                    ? 'bg-rose-500 text-white animate-pulse'
                    : 'bg-emerald-500 text-white'
                )}
              >
                {rfmSegment}
              </Badge>
            </div>

            <div className="flex items-center gap-2 text-xs font-bold text-white">
              <ShieldCheck className="size-4 text-emerald-400 shrink-0" />
              <span className="truncate">
                {userAllergens.length > 0
                  ? `Proteksi: ${userAllergens.join(', ')}`
                  : 'Diet Bebas Alergen Sehat'}
              </span>
            </div>

            <div className="flex items-center justify-between pt-1 border-t border-white/10 text-[10px] text-stone-300">
              <span>{customer?.display_name || 'Pelanggan Tamu'}</span>
              <Link to="/passport" className="text-amber-300 underline hover:text-amber-200">
                Ubah Alergi →
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
            <h2 className="font-extrabold text-base text-stone-900 flex items-center gap-2">
              <Sparkles className="size-4 text-amber-500" />
              Rekomendasi Menu Presisi Hari Ini
            </h2>
            <Link to="/order" className="text-xs font-bold text-rose-600 hover:underline">
              Lihat Semua →
            </Link>
          </div>

          <div className="space-y-3">
            {SAMPLE_SAFE_MENUS.map((menu, idx) => (
              <div
                key={idx}
                className="rounded-3xl bg-white border border-stone-200/90 p-4 shadow-2xs hover:border-rose-400 transition-all flex items-center gap-4 group"
              >
                <img
                  src={menu.image}
                  alt={menu.name}
                  className="size-20 rounded-2xl object-cover shrink-0 group-hover:scale-105 transition-transform"
                />

                <div className="min-w-0 flex-1 space-y-1">
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="text-[10px] font-bold border-stone-200">
                      {menu.day}
                    </Badge>
                    <span className="text-[10px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full">
                      {menu.safeTag}
                    </span>
                  </div>

                  <h3 className="font-bold text-xs text-stone-900 leading-snug truncate">
                    {menu.name}
                  </h3>

                  <div className="flex items-center justify-between pt-1">
                    <span className="font-black text-rose-600 text-xs">
                      Rp {menu.price.toLocaleString('id-ID')}
                    </span>

                    <Button
                      size="sm"
                      onClick={() => navigate('/order')}
                      className="rounded-full bg-rose-600 hover:bg-rose-700 text-white font-bold text-[10px] h-7 px-3 gap-1 shadow-2xs"
                    >
                      Pesan
                      <ArrowRight className="size-3" />
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="p-4 rounded-3xl bg-amber-500/10 border border-amber-300/80 text-amber-950 space-y-1.5 text-xs">
            <div className="flex items-center gap-2 font-bold text-amber-900">
              <CheckCircle2 className="size-4 text-amber-600" />
              <span>Garansi Keamanan Resep Katering Dova</span>
            </div>
            <p className="text-[11px] text-amber-900/80 leading-relaxed">
              Setiap menu yang Anda pesan diverifikasi silang dengan algoritma eliminasi alergen
              terhadap 9 kelompok alergen utama. Bebas kontaminasi, aman untuk keluarga.
            </p>
          </div>
        </div>

        {/* Right Column: Live Interactive Conversation with Chef BOB (lg: 7 cols) */}
        <div className="lg:col-span-7 bg-white rounded-3xl border border-stone-200/90 shadow-2xs flex flex-col h-[650px] overflow-hidden">
          {/* Chat Header */}
          <div className="px-5 py-4 border-b border-stone-100 flex items-center justify-between bg-stone-50/50">
            <div className="flex items-center gap-3">
              <div className="size-10 rounded-2xl bg-stone-900 text-amber-300 flex items-center justify-center font-black">
                <Bot className="size-5" />
              </div>
              <div>
                <h3 className="font-extrabold text-sm text-stone-900 flex items-center gap-1.5">
                  Chef BOB
                  <span className="size-2 rounded-full bg-emerald-500 animate-pulse" />
                </h3>
                <p className="text-[11px] text-stone-500">Live AI Assistant • Siap Menjawab</p>
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