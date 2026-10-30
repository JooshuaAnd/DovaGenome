import { useEffect, useMemo, useState } from 'react'
import { getISOWeek } from 'date-fns'
import { useNavigate, useLocation, Link } from 'react-router-dom'
import {
  CalendarDays,
  Clock,
  ExternalLink,
  Heart,
  MapPin,
  Minus,
  Plus,
  Search,
  ShieldAlert,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  Utensils,
  X,
} from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { useApi } from '@/hooks/useApi'
import { useAuth } from '@/hooks/useAuth'
import { useServiceWeek } from '@/hooks/useServiceWeek'
import { cn } from '@/lib/utils'
import { catalogService } from '@/services/catalog'
import { customersService } from '@/services/customers'
import { getErrorMessage } from '@/services/http'
import { ordersService } from '@/services/orders'
import { paymentsService, type PaymentIntent } from '@/services/payments'
import type { Menu, OrderDetail, Package, Passport, ServiceDay } from '@/types'

/* ── Kurasi Foto Makanan Resolusi Tinggi Sesuai Menu Dova Kitchen ──────────── */
const MENU_IMAGES: Record<string, string> = {
  'menu_senin_ayam-rosemary':
    'https://images.unsplash.com/photo-1598515214211-89d3c73ae83b?auto=format&fit=crop&w=800&q=80',
  'Ayam Panggang Rosemary & Ubi Madu':
    'https://images.unsplash.com/photo-1598515214211-89d3c73ae83b?auto=format&fit=crop&w=800&q=80',
  'Beef Bulgogi Wijen & Nasi Beras Cokelat':
    'https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=800&q=80',
  'Tumis Tahu Jamur Saus Teriyaki (Vegetarian)':
    'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=800&q=80',
  'Sup Daging Sapi Jamur Rempah':
    'https://images.unsplash.com/photo-1547592166-23ac45744acd?auto=format&fit=crop&w=800&q=80',
  'Ayam Fillet Crispy Saus Salted Egg':
    'https://images.unsplash.com/photo-1562967914-608f82629710?auto=format&fit=crop&w=800&q=80',
  'Fillet Dori Panggang Lemon & Salad Jagung':
    'https://images.unsplash.com/photo-1519708227418-c8fd9a32b7a2?auto=format&fit=crop&w=800&q=80',
  'Ayam Suwir Sambal Matah & Urap Sayur':
    'https://images.unsplash.com/photo-1569058242253-92a9c755a0ec?auto=format&fit=crop&w=800&q=80',
  'Ikan Kakap Bakar Kunyit & Nasi Merah':
    'https://images.unsplash.com/photo-1534422298391-e4f8c172dddb?auto=format&fit=crop&w=800&q=80',
  'Gado-Gado Roll Saus Kacang Gurih':
    'https://images.unsplash.com/photo-1540420773420-3366772f4999?auto=format&fit=crop&w=800&q=80',
  'Tumis Ayam Jamur Brokoli Saus Bawang':
    'https://images.unsplash.com/photo-1512058564366-18510be2db19?auto=format&fit=crop&w=800&q=80',
  'Udang Bakar Madu Jimbaran & Nasi Merah':
    'https://images.unsplash.com/photo-1559737558-2f5a35f4523b?auto=format&fit=crop&w=800&q=80',
  'Rendang Daging Sapi Suwir & Buncis':
    'https://images.unsplash.com/photo-1555939594-58d7cb561ad1?auto=format&fit=crop&w=800&q=80',
  'Ayam Bakar Taliwang & Plecing Kangkung':
    'https://images.unsplash.com/photo-1527477378408-1bc0e2270921?auto=format&fit=crop&w=800&q=80',
  'Salmon Fillet Lemon Herb & Kentang Kukus':
    'https://images.unsplash.com/photo-1467003909585-2f8a72700288?auto=format&fit=crop&w=800&q=80',
  'Pasta Fusilli Ayam Pesto Keju':
    'https://images.unsplash.com/photo-1551183053-bf91a1d81141?auto=format&fit=crop&w=800&q=80',
  'Nasi Merah Ayam Bakar Madu Ketumbar':
    'https://images.unsplash.com/photo-1604908176997-125f25cc6f3d?auto=format&fit=crop&w=800&q=80',
  'Sup Tom Yum Udang & Ikan Kakap':
    'https://images.unsplash.com/photo-1569718212165-3a8278d5f624?auto=format&fit=crop&w=800&q=80',
  'Steak Tempe Lada Hitam (Vegetarian)':
    'https://images.unsplash.com/photo-1585238342024-78d387f4a707?auto=format&fit=crop&w=800&q=80',
}

const DEFAULT_FOOD_IMAGE =
  'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=800&q=80'

const DAYS_LIST: Record<string, { id: string; label: string; icon: string }> = {
  all: { id: 'all', label: 'Semua', icon: '🍽️' },
  Senin: { id: 'Senin', label: 'Senin', icon: '🍗' },
  Selasa: { id: 'Selasa', label: 'Selasa', icon: '🥩' },
  Rabu: { id: 'Rabu', label: 'Rabu', icon: '🐟' },
  Kamis: { id: 'Kamis', label: 'Kamis', icon: '🍤' },
  Jumat: { id: 'Jumat', label: 'Jumat', icon: '🥗' },
  Sabtu: { id: 'Sabtu', label: 'Sabtu', icon: '🍲' },
}

const cartKey = (menuId: string) => menuId

interface CartItem {
  menu: Menu
  quantity: number
  riskAccepted: boolean
  matchedAllergens: string[]
}

const DEFAULT_FALLBACK_MENUS: Menu[] = [
  {
    menu_id: 'menu_senin_ayam-rosemary',
    hari: 'Senin',
    nama_menu: 'Ayam Panggang Rosemary & Ubi Madu',
    deskripsi: 'Ayam fillet panggang rempah herba segar tanpa tepung dengan ubi madu oven.',
    alat_dapur_steril: ['Oven Station 1 (Khusus Non-Gluten)', 'Talenan Polimer Hijau #1', 'Pisau Stainless 316'],
    bahan_detail: [
      { nama: 'Fillet Dada Ayam', sumber: 'Organik segar', potensi_alergen: 'Aman', is_critical_allergen: false },
      { nama: 'Rosemary & Oregano', sumber: 'Herba segar', potensi_alergen: 'Aman', is_critical_allergen: false },
      { nama: 'Minyak Zaitun Extra Virgin', sumber: 'Cold-pressed', potensi_alergen: 'Aman', is_critical_allergen: false },
      { nama: 'Ubi Madu Cilembu', sumber: 'Lokal panggang', potensi_alergen: 'Bebas Gluten', is_critical_allergen: false },
    ],
    allergen_labels: ['Bebas Gluten', 'Bebas Seafood'],
    allergen_codes: [],
    published: true,
    package_codes: [],
    option_index: 0,
  },
  {
    menu_id: 'menu_senin_beef-bulgogi',
    hari: 'Senin',
    nama_menu: 'Beef Bulgogi Wijen & Nasi Beras Cokelat',
    deskripsi: 'Daging sapi iris bumbu bulgogi wijen panggang disajikan dengan nasi beras cokelat.',
    alat_dapur_steril: ['Wok Wajan Sapi #1', 'Talenan Merah #2', 'Spatula Stainless Steril'],
    bahan_detail: [
      { nama: 'Daging Sapi Has Dalam', sumber: 'Grass-fed', potensi_alergen: 'Aman', is_critical_allergen: false },
      { nama: 'Minyak Wijen & Biji Wijen', sumber: 'Wijen panggang murni', potensi_alergen: '⚠️ Wijen', is_critical_allergen: true },
      { nama: 'Kecap Asin Kedelai', sumber: 'Kedelai fermentasi', potensi_alergen: '⚠️ Kedelai', is_critical_allergen: true },
      { nama: 'Beras Cokelat Organik', sumber: 'Pecah kulit', potensi_alergen: 'Bebas Gluten', is_critical_allergen: false },
    ],
    allergen_labels: ['Wijen', 'Kedelai'],
    allergen_codes: ['alg_kedelai'],
    published: true,
    package_codes: [],
    option_index: 1,
  },
  {
    menu_id: 'menu_senin_tumis-tahu-teriyaki',
    hari: 'Senin',
    nama_menu: 'Tumis Tahu Jamur Saus Teriyaki (Vegetarian)',
    deskripsi: 'Tahu sutra organik & aneka jamur segar ditumis dengan saus teriyaki gurih.',
    alat_dapur_steril: ['Wok Vegetarian Hijau #1', 'Talenan Hijau #3', 'Spatula Kayu Jati Steril'],
    bahan_detail: [
      { nama: 'Tahu Sutra Organik', sumber: 'Non-GMO', potensi_alergen: '⚠️ Kedelai', is_critical_allergen: true },
      { nama: 'Jamur Tiram & Shitake', sumber: 'Hidroponik', potensi_alergen: 'Aman', is_critical_allergen: false },
      { nama: 'Saus Teriyaki Alami', sumber: 'Bumbu alami non-MSG', potensi_alergen: '⚠️ Kedelai', is_critical_allergen: true },
    ],
    allergen_labels: ['Vegetarian', 'Kedelai'],
    allergen_codes: ['alg_kedelai'],
    published: true,
    package_codes: [],
    option_index: 2,
  },
  {
    menu_id: 'menu_selasa_sup-daging-rempah',
    hari: 'Selasa',
    nama_menu: 'Sup Daging Sapi Jamur Rempah',
    deskripsi: 'Kaldu sapi rebusan lambat 12 jam dengan jamur kancing dan rempah aromatik.',
    alat_dapur_steril: ['Stock Pot Stainless Steel #3', 'Sendok Sayur Stainless', 'Talenan Kuning #2'],
    bahan_detail: [
      { nama: 'Daging Sapi Sandung Lamur', sumber: 'Lokal grass-fed', potensi_alergen: 'Aman', is_critical_allergen: false },
      { nama: 'Kaldu Tulang Sapi', sumber: 'Rebusan murni tanpa MSG', potensi_alergen: 'Aman', is_critical_allergen: false },
      { nama: 'Jamur Tiram & Kancing', sumber: 'Budidaya higienis', potensi_alergen: 'Aman', is_critical_allergen: false },
      { nama: 'Wortel & Daun Bawang', sumber: 'Sayur hidroponik', potensi_alergen: 'Aman', is_critical_allergen: false },
    ],
    allergen_labels: ['Bebas Gluten', 'Bebas Susu/Laktosa'],
    allergen_codes: [],
    published: true,
    package_codes: [],
    option_index: 0,
  },
  {
    menu_id: 'menu_selasa_ayam-salted-egg',
    hari: 'Selasa',
    nama_menu: 'Ayam Fillet Crispy Saus Salted Egg',
    deskripsi: 'Fillet ayam tepung beras renyah disiram saus kuning telur asin harum daun kari.',
    alat_dapur_steril: ['Deep Fryer Station Bebas Gandum', 'Talenan Polimer Hijau #2', 'Saringan Stainless Steril'],
    bahan_detail: [
      { nama: 'Dada Ayam Fillet', sumber: 'Probiotik', potensi_alergen: 'Aman', is_critical_allergen: false },
      { nama: 'Kuning Telur Asin', sumber: 'Telur bebek pilihan', potensi_alergen: '⚠️ Telur', is_critical_allergen: true },
      { nama: 'Tepung Beras & Maizena', sumber: 'Non-gandum murni', potensi_alergen: 'Bebas Gluten', is_critical_allergen: false },
      { nama: 'Daun Kari Segar', sumber: 'Kebun herbal', potensi_alergen: 'Aman', is_critical_allergen: false },
    ],
    allergen_labels: ['Telur', 'Bebas Gluten'],
    allergen_codes: ['alg_telur'],
    published: true,
    package_codes: [],
    option_index: 1,
  },
  {
    menu_id: 'menu_selasa_dori-lemon',
    hari: 'Selasa',
    nama_menu: 'Fillet Dori Panggang Lemon & Salad Jagung',
    deskripsi: 'Fillet ikan dori lembut dipanggang butter herbal dengan pendamping salad jagung manis.',
    alat_dapur_steril: ['Pan Khusus Ikan Biru #1', 'Talenan Biru #1', 'Capitan Silikon'],
    bahan_detail: [
      { nama: 'Fillet Dori Laut', sumber: 'Tangkapan segar', potensi_alergen: '⚠️ Seafood/Ikan', is_critical_allergen: true },
      { nama: 'Lemon Segar & Butter', sumber: 'Dairy butter murni', potensi_alergen: '⚠️ Susu/Laktosa', is_critical_allergen: true },
      { nama: 'Jagung Manis Pipil & Selada', sumber: 'Hidroponik', potensi_alergen: 'Aman', is_critical_allergen: false },
    ],
    allergen_labels: ['Seafood/Ikan', 'Susu/Laktosa'],
    allergen_codes: ['alg_seafood', 'alg_dairy'],
    published: true,
    package_codes: [],
    option_index: 2,
  },
  {
    menu_id: 'menu_rabu_ayam-suwir-matah',
    hari: 'Rabu',
    nama_menu: 'Ayam Suwir Sambal Matah & Urap Sayur',
    deskripsi: 'Ayam kukus suwir disiram sambal matah Bali segar dengan pelengkap urap sayur kelapa sangrai.',
    alat_dapur_steril: ['Steamer Unggas Stainless #1', 'Talenan Putih #1', 'Pisau Khusus Sayur'],
    bahan_detail: [
      { nama: 'Dada Ayam Ungkep', sumber: 'Rempah kuning alami', potensi_alergen: 'Aman', is_critical_allergen: false },
      { nama: 'Bawang Merah & Cabai Rawit', sumber: 'Segar lokal', potensi_alergen: 'Aman', is_critical_allergen: false },
      { nama: 'Kelapa Parut Bumbu Urap', sumber: 'Kelapa muda segar', potensi_alergen: 'Aman', is_critical_allergen: false },
    ],
    allergen_labels: ['Bebas Gluten', 'Bebas Seafood'],
    allergen_codes: [],
    published: true,
    package_codes: [],
    option_index: 0,
  },
  {
    menu_id: 'menu_rabu_kakap-bakar',
    hari: 'Rabu',
    nama_menu: 'Ikan Kakap Bakar Kunyit & Nasi Merah',
    deskripsi: 'Fillet kakap putih bakar bumbu kunyit lengkuas rempah disajikan bersama nasi beras merah pulen.',
    alat_dapur_steril: ['Grill Pan Biru #1 (Zona Terisolasi)', 'Talenan Biru #3', 'Spatula Silikon Seafood'],
    bahan_detail: [
      { nama: 'Fillet Kakap Putih', sumber: 'Tangkapan harian', potensi_alergen: '⚠️ Seafood/Ikan', is_critical_allergen: true },
      { nama: 'Bumbu Kunyit Lengkuas', sumber: 'Ulekan alami', potensi_alergen: 'Aman', is_critical_allergen: false },
      { nama: 'Nasi Merah Organik', sumber: 'Beras merah pecah kulit', potensi_alergen: 'Bebas Gluten', is_critical_allergen: false },
    ],
    allergen_labels: ['Seafood/Ikan', 'Bebas Gluten'],
    allergen_codes: ['alg_seafood'],
    published: true,
    package_codes: [],
    option_index: 1,
  },
  {
    menu_id: 'menu_rabu_gado-gado',
    hari: 'Rabu',
    nama_menu: 'Gado-Gado Roll Saus Kacang Gurih',
    deskripsi: 'Gulungan sayuran segar, lontong, dan tempe dengan saus kacang tanah kental resep istimewa.',
    alat_dapur_steril: ['Prep Table Sayur Higienis', 'Talenan Putih #2', 'Blender Saus Khusus Kacang'],
    bahan_detail: [
      { nama: 'Sayuran Campur & Tauge', sumber: 'Ozon steril', potensi_alergen: 'Aman', is_critical_allergen: false },
      { nama: 'Tempe Kedelai Kukus', sumber: 'Kedelai lokal', potensi_alergen: '⚠️ Kedelai', is_critical_allergen: true },
      { nama: 'Saus Kacang Tanah Mede', sumber: 'Kacang sangrai murni', potensi_alergen: '⚠️ Kacang Tanah', is_critical_allergen: true },
    ],
    allergen_labels: ['Kacang Tanah', 'Kedelai'],
    allergen_codes: ['alg_kacang', 'alg_kedelai'],
    published: true,
    package_codes: [],
    option_index: 2,
  },
  {
    menu_id: 'menu_kamis_tumis-ayam-jamur',
    hari: 'Kamis',
    nama_menu: 'Tumis Ayam Jamur Brokoli Saus Bawang',
    deskripsi: 'Tumis ayam probiotik dan brokoli hijau dengan saus bawang putih bening ramah alergen.',
    alat_dapur_steril: ['Wok Wajan Hijau #2 (Alergen-Free Zone)', 'Talenan Putih #1', 'Spatula Kayu Jati Steril'],
    bahan_detail: [
      { nama: 'Dada Ayam Fillet', sumber: 'Probiotik segar', potensi_alergen: 'Aman', is_critical_allergen: false },
      { nama: 'Brokoli Organik', sumber: 'Dicuci air garam ozon', potensi_alergen: 'Aman', is_critical_allergen: false },
      { nama: 'Jamur Kancing', sumber: 'Segar higienis', potensi_alergen: 'Aman', is_critical_allergen: false },
      { nama: 'Saus Bawang Putih Alami', sumber: 'Kaldu ayam & garam murni', potensi_alergen: 'Aman', is_critical_allergen: false },
    ],
    allergen_labels: ['Bebas Gluten', 'Bebas Kacang Tanah'],
    allergen_codes: [],
    published: true,
    package_codes: [],
    option_index: 0,
  },
  {
    menu_id: 'menu_kamis_udang-madu',
    hari: 'Kamis',
    nama_menu: 'Udang Bakar Madu Jimbaran & Nasi Merah',
    deskripsi: 'Udang windu segar berbalut glaze madu karamel dan rempah khas Jimbaran disajikan dengan nasi merah.',
    alat_dapur_steril: ['Grill Station Seafood Biru', 'Talenan Biru #2', 'Kuas Silikon Steril'],
    bahan_detail: [
      { nama: 'Udang Windu Segar', sumber: 'Tangkapan muara', potensi_alergen: '⚠️ Seafood/Udang', is_critical_allergen: true },
      { nama: 'Madu Hutan & Rempah', sumber: 'Madu murni', potensi_alergen: 'Aman', is_critical_allergen: false },
      { nama: 'Nasi Merah Organik', sumber: 'Pecah kulit', potensi_alergen: 'Bebas Gluten', is_critical_allergen: false },
    ],
    allergen_labels: ['Seafood/Udang', 'Bebas Gluten'],
    allergen_codes: ['alg_seafood'],
    published: true,
    package_codes: [],
    option_index: 1,
  },
  {
    menu_id: 'menu_kamis_rendang-suwir',
    hari: 'Kamis',
    nama_menu: 'Rendang Daging Sapi Suwir & Buncis',
    deskripsi: 'Daging sapi suwir karamel santan rempah Minang dipadu buncis muda rebus segar.',
    alat_dapur_steril: ['Wajan Khusus Daging Merah #1', 'Talenan Merah #1', 'Sendok Pengaduk Kayu'],
    bahan_detail: [
      { nama: 'Daging Sapi Has Dalam', sumber: 'Grass-fed lokal', potensi_alergen: 'Aman', is_critical_allergen: false },
      { nama: 'Santan Kelapa Murni', sumber: 'Kelapa tua peras pertama', potensi_alergen: 'Aman', is_critical_allergen: false },
      { nama: 'Bumbu Rempah Rendang', sumber: 'Rempah asli tanpa MSG', potensi_alergen: 'Aman', is_critical_allergen: false },
      { nama: 'Buncis Baby Rebus', sumber: 'Hidroponik', potensi_alergen: 'Aman', is_critical_allergen: false },
    ],
    allergen_labels: ['Bebas Gluten', 'Bebas Susu/Laktosa'],
    allergen_codes: [],
    published: true,
    package_codes: [],
    option_index: 2,
  },
  {
    menu_id: 'menu_jumat_ayam-taliwang',
    hari: 'Jumat',
    nama_menu: 'Ayam Bakar Taliwang & Plecing Kangkung',
    deskripsi: 'Ayam bakar bumbu pedas manis Taliwang aromatik disajikan dengan plecing kangkung segar.',
    alat_dapur_steril: ['Grill Station Unggas #2', 'Talenan Hijau #2', 'Kuas Panggang Khusus'],
    bahan_detail: [
      { nama: 'Ayam Kampung Panggang', sumber: 'Segar non-suntik', potensi_alergen: 'Aman', is_critical_allergen: false },
      { nama: 'Cabai, Terasi, Jeruk Limau', sumber: 'Bumbu Taliwang', potensi_alergen: '⚠️ Terasi/Seafood', is_critical_allergen: true },
      { nama: 'Kangkung Segar Rebus', sumber: 'Hidroponik', potensi_alergen: 'Aman', is_critical_allergen: false },
    ],
    allergen_labels: ['Terasi/Seafood', 'Bebas Gluten'],
    allergen_codes: ['alg_seafood'],
    published: true,
    package_codes: [],
    option_index: 0,
  },
  {
    menu_id: 'menu_jumat_salmon-lemon',
    hari: 'Jumat',
    nama_menu: 'Salmon Fillet Lemon Herb & Kentang Kukus',
    deskripsi: 'Norwegian salmon panggang butter lemon segar disajikan bersama kentang baby kukus dan buncis.',
    alat_dapur_steril: ['Pan Stainless Khusus Salmon', 'Talenan Biru #2', 'Kukusan Stainless Bebas Gluten'],
    bahan_detail: [
      { nama: 'Norwegian Salmon Fillet', sumber: 'Grade sashimi', potensi_alergen: '⚠️ Seafood/Ikan', is_critical_allergen: true },
      { nama: 'Lemon Segar & Butter', sumber: 'Dairy butter murni', potensi_alergen: '⚠️ Susu/Laktosa', is_critical_allergen: true },
      { nama: 'Kentang Baby Kukus', sumber: 'Kukusan uap murni', potensi_alergen: 'Bebas Gluten', is_critical_allergen: false },
    ],
    allergen_labels: ['Seafood/Ikan', 'Susu/Laktosa'],
    allergen_codes: ['alg_seafood', 'alg_dairy'],
    published: true,
    package_codes: [],
    option_index: 1,
  },
  {
    menu_id: 'menu_jumat_pasta-fusilli-pesto',
    hari: 'Jumat',
    nama_menu: 'Pasta Fusilli Ayam Pesto Keju',
    deskripsi: 'Fusilli al dente dengan saus pesto kemangi harum, potongan ayam panggang, dan taburan keju parmesan.',
    alat_dapur_steril: ['Pasta Boiler Khusus #1', 'Talenan Putih #3', 'Spatula Silikon'],
    bahan_detail: [
      { nama: 'Fusilli Semolina Gandum', sumber: 'Gandum durum', potensi_alergen: '⚠️ Gluten', is_critical_allergen: true },
      { nama: 'Dada Ayam Panggang', sumber: 'Fillet ayam', potensi_alergen: 'Aman', is_critical_allergen: false },
      { nama: 'Pesto Kemangi & Kacang Kenari', sumber: 'Herbal pesto', potensi_alergen: '⚠️ Kacang', is_critical_allergen: true },
      { nama: 'Keju Parmesan', sumber: 'Dairy cheese', potensi_alergen: '⚠️ Susu/Laktosa', is_critical_allergen: true },
    ],
    allergen_labels: ['Gluten', 'Susu/Laktosa', 'Kacang'],
    allergen_codes: ['alg_gluten', 'alg_dairy', 'alg_kacang'],
    published: true,
    package_codes: [],
    option_index: 2,
  },
  {
    menu_id: 'menu_sabtu_ayam-madu',
    hari: 'Sabtu',
    nama_menu: 'Nasi Merah Ayam Bakar Madu Ketumbar',
    deskripsi: 'Ayam bakar karamel madu hutan asli dan biji ketumbar sangrai murni disajikan dengan nasi merah.',
    alat_dapur_steril: ['Panggangan Arang Stainless', 'Kuas Silikon Khusus', 'Talenan Hijau #2'],
    bahan_detail: [
      { nama: 'Ayam Kampung Potong', sumber: 'Segar non-suntik', potensi_alergen: 'Aman', is_critical_allergen: false },
      { nama: 'Madu Hutan Asli', sumber: 'Madu mentah alami', potensi_alergen: 'Aman', is_critical_allergen: false },
      { nama: 'Biji Ketumbar Sangrai', sumber: 'Rempah asli murni', potensi_alergen: 'Aman', is_critical_allergen: false },
      { nama: 'Nasi Merah Pulen', sumber: 'Beras lokal organik', potensi_alergen: 'Bebas Gluten', is_critical_allergen: false },
    ],
    allergen_labels: ['Bebas Gluten', 'Bebas Seafood'],
    allergen_codes: [],
    published: true,
    package_codes: [],
    option_index: 0,
  },
  {
    menu_id: 'menu_sabtu_tom-yum',
    hari: 'Sabtu',
    nama_menu: 'Sup Tom Yum Udang & Ikan Kakap',
    deskripsi: 'Sup asam pedas segar kaldu udang dan ikan kakap dengan serai, lengkuas, dan daun jeruk purut.',
    alat_dapur_steril: ['Soup Pot Seafood Biru #2', 'Talenan Biru #3', 'Sendok Sayur Stainless'],
    bahan_detail: [
      { nama: 'Udang Segar & Kakap', sumber: 'Tangkapan laut harian', potensi_alergen: '⚠️ Seafood', is_critical_allergen: true },
      { nama: 'Serai, Daun Jeruk, Cabai', sumber: 'Bumbu rempah tom yum', potensi_alergen: 'Aman', is_critical_allergen: false },
      { nama: 'Jamur Kancing & Tomat', sumber: 'Sayur hidroponik', potensi_alergen: 'Aman', is_critical_allergen: false },
    ],
    allergen_labels: ['Seafood', 'Bebas Gluten'],
    allergen_codes: ['alg_seafood'],
    published: true,
    package_codes: [],
    option_index: 1,
  },
  {
    menu_id: 'menu_sabtu_steak-tempe',
    hari: 'Sabtu',
    nama_menu: 'Steak Tempe Lada Hitam (Vegetarian)',
    deskripsi: 'Steak tempe kedelai non-GMO panggang lembut berpadu siraman saus lada hitam aromatik.',
    alat_dapur_steril: ['Grill Pan Vegetarian Hijau #1', 'Talenan Hijau #3', 'Spatula Kayu'],
    bahan_detail: [
      { nama: 'Tempe Organik Non-GMO', sumber: 'Kedelai lokal alami', potensi_alergen: '⚠️ Kedelai', is_critical_allergen: true },
      { nama: 'Saus Lada Hitam Alami', sumber: 'Lada hitam & kaldu sayur', potensi_alergen: 'Aman', is_critical_allergen: false },
      { nama: 'Wortel & Buncis Rebus', sumber: 'Sayur segar kukus', potensi_alergen: 'Aman', is_critical_allergen: false },
    ],
    allergen_labels: ['Vegetarian', 'Kedelai'],
    allergen_codes: ['alg_kedelai'],
    published: true,
    package_codes: [],
    option_index: 2,
  },
]

// Kept as a migration reference for the old visual catalog; it is never used
// as a runtime fallback. Customer-facing cards must come from the API.
void DEFAULT_FALLBACK_MENUS

export function OrderPage() {
  const { customer, isAuthenticated, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  // Data fetching
  const {
    data: menuData,
    loading: menuLoading,
    error: menuError,
  } = useApi<Menu[]>((signal) => catalogService.listMenus(signal))
  const {
    week: serviceWeek,
    days: serviceDays,
    loading: serviceWeekLoading,
    error: serviceWeekError,
    refetch: refetchServiceWeek,
  } = useServiceWeek()
  const { data: packageData } = useApi<Package[]>((signal) =>
    catalogService.listPackages(signal),
    { enabled: isAuthenticated },
  )
  const packages = useMemo(
    () => (Array.isArray(packageData) ? packageData.filter((item) => item.active) : []),
    [packageData],
  )
  const menuList = useMemo(() => {
    const datedById = new Map(serviceDays.flatMap((day) =>
      day.options.map((menu) => [menu.menu_id, { service_date: day.service_date, date_label: day.date_label }] as const),
    ))
    const catalogMenus = Array.isArray(menuData) ? menuData : []
    const source = catalogMenus.length > 0
      ? catalogMenus
      : serviceDays.flatMap((day) => day.options)
    return source.map((menu) => ({ ...menu, ...datedById.get(menu.menu_id) }))
  }, [menuData, serviceDays])

  const menuDateById = useMemo(
    () => new Map(serviceDays.flatMap((day) => day.options.map((menu) => [menu.menu_id, day] as const))),
    [serviceDays],
  )

  const { data: passport, refetch: refetchPassport } = useApi<Passport>(
    (signal) => customersService.getPassport(signal),
    { enabled: isAuthenticated }
  )

  useEffect(() => {
    const refresh = () => {
      void refetchPassport()
      refetchServiceWeek()
    }
    window.addEventListener('dova:passport-updated', refresh)
    return () => window.removeEventListener('dova:passport-updated', refresh)
  }, [refetchPassport, refetchServiceWeek])

  // Filters & Search
  const [selectedDay, setSelectedDay] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [favorites, setFavorites] = useState<string[]>([])
  const [aiRecommendations, setAiRecommendations] = useState<any[]>([])

  // Load customer likes and recommendations for precision personalization
  useEffect(() => {
    if (!isAuthenticated || !customer?.customer_id) {
      setFavorites([])
      setAiRecommendations([])
      return
    }
    const cid = customer.customer_id
    customersService
      .getLikes(cid)
      .then((likedIds) => {
        if (Array.isArray(likedIds) && likedIds.length > 0) {
          setFavorites(likedIds)
        }
      })
      .catch(() => null)

    customersService
      .getRecommendations(cid)
      .then((recs) => {
        if (Array.isArray(recs)) {
          setAiRecommendations(recs)
        }
      })
      .catch(() => null)
  }, [customer, isAuthenticated])

  // Cart & UI State
  const [cart, setCart] = useState<Record<string, CartItem>>({})
  const [isCartOpen, setIsCartOpen] = useState(false)
  // Retained only for the legacy hidden block below; customer navigation is bottom-nav based.
  const [isSideMenuOpen, setIsSideMenuOpen] = useState(false)
  const [selectedMenu, setSelectedMenu] = useState<Menu | null>(null)

  useEffect(() => {
    const openCart = () => setIsCartOpen(true)
    window.addEventListener('dova:open-cart', openCart)
    return () => window.removeEventListener('dova:open-cart', openCart)
  }, [])

  useEffect(() => {
    if (location.search.includes('openCart=1')) {
      setIsCartOpen(true)
      navigate(location.pathname, { replace: true })
    }
  }, [location.pathname, location.search, navigate])

  // SweetAlert: Allergen Conflict Warning Dialog
  const [conflictMenu, setConflictMenu] = useState<{
    menu: Menu
    matchedAllergens: string[]
  } | null>(null)

  // Checkout & Payment State
  const [isPaymentOpen, setIsPaymentOpen] = useState(false)
  const [paymentTimer, setPaymentTimer] = useState(600) // 10 minutes in seconds
  const [deliveryAddress, setDeliveryAddress] = useState('')
  const [courierNotes, setCourierNotes] = useState('Titip di depan pintu/resepsionis.')
  const [paymentMethod, setPaymentMethod] = useState<'qris' | 'va'>('qris')
  const [selectedPackageCode, setSelectedPackageCode] = useState('')
  const [checkoutOrder, setCheckoutOrder] = useState<OrderDetail | null>(null)
  const [paymentIntent, setPaymentIntent] = useState<PaymentIntent | null>(null)
  const [isCheckoutLoading, setIsCheckoutLoading] = useState(false)

  // Payment Countdown Timer
  useEffect(() => {
    let interval: ReturnType<typeof setInterval>
    if (isPaymentOpen && !paymentIntent && paymentTimer > 0) {
      interval = setInterval(() => {
        setPaymentTimer((prev) => prev - 1)
      }, 1000)
    }
    return () => clearInterval(interval)
  }, [isPaymentOpen, paymentIntent, paymentTimer])

  const formatTimer = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
  }

  // Active customer allergens
  const userAllergens = useMemo(() => {
    if (!passport) return []
    return passport.allergies?.map((allergy) => allergy.label) ?? []
  }, [passport])

  const dislikedTerms = useMemo(() => {
    const saved = (passport?.avoided_ingredients ?? []).map((item) => item.toLowerCase().trim()).filter(Boolean)
    const terms = new Set(saved)
    if (saved.some((item) => /pedas|sambal|cabai|cabe|rawit/.test(item))) {
      ;['pedas', 'sambal', 'cabai', 'cabe', 'rawit'].forEach((term) => terms.add(term))
    }
    if (saved.some((item) => /ayam/.test(item))) terms.add('ayam')
    if (saved.some((item) => /sayur|vegetarian/.test(item))) {
      ;[
        'sayur', 'sayuran', 'vegetarian', 'tahu', 'tempe', 'gado-gado', 'urap', 'salad', 'brokoli',
        'wortel', 'buncis', 'selada', 'kangkung', 'bayam', 'sawi', 'tauge', 'toge',
        'jagung', 'kol', 'kubis', 'kembang kol', 'terong', 'terung', 'paprika',
        'labu', 'timun', 'mentimun', 'asparagus', 'kacang panjang', 'rebung',
        'vegetable',
      ].forEach((term) => terms.add(term))
    }
    return [...terms]
  }, [passport?.avoided_ingredients])

  function openDietaryPassport() {
    if (!isAuthenticated) {
      navigate('/login?next=%2Forder')
      return
    }
    window.dispatchEvent(new Event('dova:open-passport'))
  }

  // Check if a menu item has allergen conflicts
  function checkMenuConflict(menu: Menu): string[] {
    if (userAllergens.length === 0) return []
    const savedAllergies = passport?.allergies ?? []
    const allergyCodes = new Set(savedAllergies.map((allergy) => allergy.code))
    const matchedCodes = (menu.allergen_codes ?? []).filter((code) => allergyCodes.has(code))
    if (matchedCodes.length > 0) {
      return matchedCodes.map((code) =>
        savedAllergies.find((allergy) => allergy.code === code)?.label ||
        menu.allergen_labels.find((label) => label.toLowerCase().includes(code.toLowerCase())) || code,
      )
    }
    const conflicts: string[] = []
    const menuContent = [
      menu.nama_menu,
      menu.deskripsi,
      ...menu.bahan_detail.map((b) => `${b.nama} ${b.potensi_alergen}`),
      ...menu.allergen_labels,
    ]
      .join(' ')
      .toLowerCase()

    for (const alg of userAllergens) {
      const algLower = alg.toLowerCase()
      if (menuContent.includes(algLower)) {
        conflicts.push(alg)
      }
    }
    return Array.from(new Set(conflicts))
  }

  function matchingDislikes(menu: Menu): string[] {
    const searchable = menu.bahan_detail
      .filter((item) => item.sumber === 'recipe_component' && item.ingredient_id)
      .map((item) => item.nama)
      .join(' ')
      .toLowerCase()
    return dislikedTerms.filter((term) => term && searchable.includes(term))
  }

  // Handle Add to Cart with Allergen Conflict Check
  function handleAddToCartClick(menu: Menu) {
    if (checkoutOrder) {
      toast.info('Order sudah dibuat. Tunggu status payment intent/webhook sebelum mengubah cart.')
      return
    }
    const conflicts = checkMenuConflict(menu)

    // Jika ada bentrok dengan profil alergi user -> Munculkan SweetAlert peringatan!
    if (conflicts.length > 0) {
      setConflictMenu({ menu, matchedAllergens: conflicts })
      return
    }

    // Jika aman -> Tambahkan langsung ke keranjang
    executeAddToCart(menu, false, [])
  }

  function executeAddToCart(
    menu: Menu,
    riskAccepted: boolean,
    matchedAllergens: string[],
  ) {
    const key = cartKey(menu.menu_id)
    setCart((prev) => {
      const existing = prev[key]
      const newQty = existing ? existing.quantity + 1 : 1
      return {
        ...prev,
        [key]: {
          menu,
          quantity: newQty,
          riskAccepted,
          matchedAllergens,
        },
      }
    })

    // Catat interaksi keranjang ke Supabase untuk AI ML
    if (customer?.customer_id) {
      customersService.trackCartEvent({
        menu_id: menu.menu_id,
        quantity: 1,
        action: 'add',
        customer_id: customer.customer_id,
      }).catch(() => null)
    }

    toast.success(`${menu.nama_menu} ditambahkan ke keranjang!`, {
      description: `Porsi: ${cart[key] ? cart[key].quantity + 1 : 1} · ${menu.hari}`,
    })

    setConflictMenu(null)
  }

  function updateQuantity(menuId: string, delta: number) {
    if (checkoutOrder) {
      toast.info('Order sudah dibuat. Cart dikunci sampai payment intent selesai.')
      return
    }
    if (customer?.customer_id) {
      customersService.trackCartEvent({
        menu_id: menuId,
        quantity: Math.abs(delta),
        action: delta > 0 ? 'add' : 'remove',
        customer_id: customer.customer_id,
      }).catch(() => null)
    }

    const key = cartKey(menuId)
    setCart((prev) => {
      const existing = prev[key]
      if (!existing) return prev
      const updatedQty = existing.quantity + delta
      if (updatedQty <= 0) {
        const next = { ...prev }
        delete next[key]
        return next
      }
      return {
        ...prev,
        [key]: { ...existing, quantity: updatedQty },
      }
    })
  }

  async function toggleFavorite(menuId: string) {
    if (!isAuthenticated || !customer?.customer_id) {
      navigate('/login?next=%2Forder')
      return
    }
    const isCurrentlyFav = favorites.includes(menuId)
    setFavorites((prev) =>
      isCurrentlyFav ? prev.filter((id) => id !== menuId) : [...prev, menuId]
    )
    const cid = customer.customer_id
    try {
      const res = await customersService.toggleLike(menuId, cid)
      if (res.liked) {
        toast.success('Disukai! AI Chef mencatat preferensimu untuk rekomendasi presisi.', {
          icon: '❤️',
        })
      }
    } catch {
      // silent fallback
    }
  }


  // Filtered menus
  const filteredMenus = useMemo(() => {
    return menuList.filter((m) => {
      const matchDay = selectedDay === 'all' || m.hari === selectedDay
      const matchSearch =
        searchQuery.trim() === '' ||
        m.nama_menu.toLowerCase().includes(searchQuery.toLowerCase()) ||
        m.deskripsi.toLowerCase().includes(searchQuery.toLowerCase()) ||
        m.bahan_detail.some((b) => b.nama.toLowerCase().includes(searchQuery.toLowerCase()))
      return matchDay && matchSearch
    })
  }, [menuList, selectedDay, searchQuery, dislikedTerms])

  const personalizedPicks = useMemo(() => {
    const safeMenuIds = new Set(serviceDays.flatMap((day) =>
      day.safety.filter((safety) => safety.level === 'safe' && safety.is_recommended).map((safety) => safety.menu_id),
    ))
    const recommendedIds = aiRecommendations.map((item) => item.menu_id)
    const historyPicks = menuList
      .filter((menu) => safeMenuIds.has(menu.menu_id))
      .filter((menu) => favorites.includes(menu.menu_id) || recommendedIds.includes(menu.menu_id))
      .filter((menu) => matchingDislikes(menu).length === 0)
      .filter((menu) => checkMenuConflict(menu).length === 0)
      .slice(0, 4)
    if (historyPicks.length > 0 || !passport?.structured) return historyPicks
    return menuList
      .filter((menu) => safeMenuIds.has(menu.menu_id))
      .filter((menu) => matchingDislikes(menu).length === 0)
      .filter((menu) => checkMenuConflict(menu).length === 0)
      .slice(0, 4)
  }, [menuList, favorites, aiRecommendations, dislikedTerms, passport, serviceDays])

  const catalogLoading = serviceWeekLoading || menuLoading
  const catalogError = serviceWeekError ?? menuError
  const batchNumber = serviceWeek?.week_start
    ? getISOWeek(new Date(`${serviceWeek.week_start}T12:00:00`))
    : null
  const batchDateRange = serviceDays.length > 0
    ? `${serviceDays[0].date_label} — ${serviceDays[serviceDays.length - 1].date_label}`
    : serviceWeek?.week_start ?? 'Katalog mingguan'

  // Cart calculations
  const cartItemsArray = Object.values(cart)
  const cartItemCount = cartItemsArray.reduce((acc, curr) => acc + curr.quantity, 0)
  const cartGroups = Object.keys(DAYS_LIST)
    .filter((day) => day !== 'all')
    .map((day) => ({
      day: day as ServiceDay,
      items: cartItemsArray.filter(({ menu }) => menu.hari === day),
    }))
    .filter((group) => group.items.length > 0)
  const selectedPackage = packages.find((item) => item.code === selectedPackageCode) ?? null
  const cartSubtotal = selectedPackage?.price ?? 0
  const deliveryFee = cartItemCount > 0 ? 0 : 0 // Free ongkir promo
  const cartGrandTotal = cartSubtotal + deliveryFee
  const payableTotal = selectedPackage?.price ?? cartGrandTotal

  useEffect(() => {
    if (!selectedPackageCode && packages.length > 0) {
      setSelectedPackageCode(packages[0].code)
    }
  }, [packages, selectedPackageCode])

  async function handleBeginCheckout(): Promise<boolean> {
    if (!isAuthenticated) {
      toast.error('Masuk terlebih dahulu untuk checkout.')
      navigate('/login?next=%2Forder')
      return false
    }
    if (!selectedPackage) {
      toast.error('Pilih paket layanan dari data katalog live terlebih dahulu.')
      return false
    }
    if (deliveryAddress.trim().length < 8) {
      toast.error('Isi alamat pengantaran yang lengkap terlebih dahulu.')
      return false
    }
    if (selectedPackage.price === null || selectedPackage.price <= 0) {
      toast.error('Harga paket belum tersedia dari server. Checkout ditahan.')
      return false
    }
    if (!Array.isArray(menuData) || menuData.length === 0) {
      toast.error('Katalog live belum tersedia. Checkout ditahan.')
      return false
    }

    const liveMenuIds = new Set(menuData.map((menu) => menu.menu_id))
    const invalidMenu = cartItemsArray.find(({ menu }) => !liveMenuIds.has(menu.menu_id))
    if (invalidMenu) {
      toast.error('Ada menu lokal/fallback di keranjang. Muat ulang katalog live lalu pilih ulang.')
      return false
    }

    const selectedDays = Array.from(new Set(cartItemsArray.map(({ menu }) => menu.hari)))
    if (cartItemsArray.length === 0) {
      toast.error('Keranjang masih kosong.')
      return false
    }

    setIsCheckoutLoading(true)
    try {
      let order = checkoutOrder
      if (!order) {
        order = await ordersService.create({
          package_code: selectedPackage.code,
          schedule_days: selectedDays,
          selections: cartItemsArray.map(({ menu, quantity }) => ({
            hari: menu.hari,
            menu_id: menu.menu_id,
            quantity,
          })),
          selected_allergen_codes: passport?.critical_codes ?? [],
          customer_note: courierNotes,
          delivery_address: deliveryAddress.trim(),
          apply_passport: true,
        })
        setCheckoutOrder(order)
      }

      const intent = await paymentsService.createIntent(order.order_id, {
        provider: paymentMethod,
        idempotency_key: `web-${order.order_id}`,
      })
      setPaymentIntent(intent)
      setIsPaymentOpen(true)
      setPaymentTimer(600)
      toast.success('Payment intent dibuat dari server.', {
        description: 'Pembayaran hanya dianggap lunas setelah webhook provider terverifikasi.',
      })
      return true
    } catch (error) {
      toast.error('Checkout ditahan oleh server.', { description: getErrorMessage(error) })
      return false
    } finally {
      setIsCheckoutLoading(false)
    }
  }

  const homePreferenceAlerts = [
    passport?.allergies?.length
      ? `Alergi: ${passport.allergies.map((item) => item.label || item.code).join(', ')}`
      : '',
    passport?.avoided_ingredients?.length
      ? `Dihindari: ${passport.avoided_ingredients.join(', ')}`
      : '',
    passport?.nutrition_goal === 'high_fat_high_protein'
      ? 'Target lemak & protein tinggi; kecocokan menu menunggu data makro terverifikasi'
      : passport?.nutrition_goal === 'high_protein'
        ? 'Fokus protein; rekomendasi makro menunggu data terverifikasi'
        : passport?.nutrition_goal === 'high_fat'
          ? 'Fokus lemak; rekomendasi makro menunggu data terverifikasi'
          : passport?.nutrition_goal === 'low_fat'
            ? 'Target rendah lemak; data lemak menu belum terverifikasi'
            : passport?.nutrition_goal === 'fat_loss'
              ? 'Target mengurangi lemak tubuh; nutrisi menu belum terverifikasi'
              : passport?.nutrition_goal === 'lighter'
                ? 'Fokus makan lebih ringan; data kalori menu belum terverifikasi'
                : '',
  ].filter(Boolean)
  const hasMacroGoal = ['high_fat_high_protein', 'high_protein', 'high_fat'].includes(passport?.nutrition_goal ?? '')

  return (
    <div className="min-h-screen bg-canvas text-ink font-sans flex antialiased selection:bg-gold-500/30 selection:text-forest-900">
      {/* ── Center Content Column ── */}
      <div className="flex-1 flex flex-col min-w-0 pb-20 overflow-y-auto">
        {/* ── 1. Top Mobile / Desktop Header ───────────────── */}
        <header className="sticky top-0 z-40 bg-canvas/95 backdrop-blur-md border-b border-line px-4 py-3">
        <div className="w-full max-w-[1600px] mx-auto flex items-center justify-between gap-3">
          {/* Center: Greeting & Brand Logo */}
          <div className="flex flex-col items-center text-center">
            <span className="text-[11px] font-medium text-stone-500">
              Halo, {customer?.display_name || 'Food Lover'}! 👋
            </span>
            <div className="flex items-center gap-1.5 font-black text-forest-900 text-lg md:text-xl tracking-tighter">
              DOVA KITCHEN
              <span className="inline-block size-1.5 rounded-full bg-gold-600"></span>
            </div>
          </div>

          <button type="button" onClick={() => setIsCartOpen(true)} aria-label="Buka keranjang" className="relative flex size-10 items-center justify-center rounded-full border border-line bg-surface text-forest-900 shadow-sm">
            <ShoppingBag className="size-4" />
            {cartItemCount > 0 && <span className="absolute -right-1 -top-1 flex size-5 items-center justify-center rounded-full bg-rose-700 text-[10px] font-bold text-white">{cartItemCount}</span>}
          </button>
        </div>

        {/* ── Search Bar (Clean Pill) ────────────────────────────────────────── */}
        <div className="w-full max-w-[1600px] mx-auto mt-3">
          <div className="relative flex items-center">
            <Search className="absolute left-4 size-4 text-stone-400" />
            <Input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Cari menu sehat, bahan, atau pantangan..."
              className="w-full rounded-full bg-surface border-line pl-11 pr-10 py-2 text-sm shadow-hairline focus-visible:ring-forest-600"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-3.5 text-stone-400 hover:text-stone-600"
              >
                <X className="size-4" />
              </button>
            )}
          </div>
        </div>
      </header>

      {/* ── Main Content Area ──────────────────────────────────────────────── */}
      <main className="w-full max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8 pt-4 space-y-6">
        {/* ── 2. Hero Promo Banner (Inspired by KFC "CRISPY. JUICY. IRRESISTIBLE.") ── */}
        <div className="relative overflow-hidden rounded-[2rem] bg-[radial-gradient(circle_at_84%_12%,rgba(251,191,151,.24),transparent_33%),linear-gradient(122deg,#681d27,#9f2735_58%,#c5423b)] p-6 md:p-8 text-white shadow-2xl shadow-rose-950/20">
          <div className="absolute right-0 top-0 bottom-0 w-1/2 opacity-25 md:opacity-40 mix-blend-overlay pointer-events-none">
            <img
              src="https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=1000&q=80"
              alt="Culinary"
              className="h-full w-full object-cover"
            />
          </div>

          <div className="relative z-10 max-w-md space-y-3">
            <Badge className="bg-[#f5d8ca] text-[#681d27] font-bold uppercase tracking-wider text-[10px] px-2.5 py-0.5">
              MENU MINGGU INI · CEK BAHAN & PANTANGAN
            </Badge>

            <h1 className="text-2xl md:text-4xl font-black tracking-tight leading-tight uppercase">
              MENU ENAK, <br />
              <span className="text-[#f6d8bc]">PILIHANMU.</span>
            </h1>

            <p className="text-xs md:text-sm text-white/90 font-normal leading-relaxed">
              Jelajahi menu minggu ini. Bahan dan status verifikasi resep ditampilkan sebelum kamu memesan.
            </p>

            <div className="pt-2 flex items-center gap-3">
              <Button
                onClick={() => {
                  setSelectedDay('all')
                  const el = document.getElementById('food-catalog-grid')
                  el?.scrollIntoView({ behavior: 'smooth' })
                }}
                className="rounded-full bg-[#fff8f1] text-[#781f2d] hover:bg-[#f7dfd3] font-bold px-6 shadow-md shadow-black/20 active:scale-95 transition-all text-xs md:text-sm"
              >
                Pesan Sekarang →
              </Button>

              {userAllergens.length > 0 ? (
                <div className="flex items-center gap-1.5 text-xs text-white/90 bg-white/10 backdrop-blur-md px-3 py-1.5 rounded-full border border-white/20">
                  <ShieldCheck className="size-4 text-emerald-300 shrink-0" />
                  <span className="truncate max-w-[150px]">
                    Proteksi: {userAllergens.join(', ')}
                  </span>
                </div>
              ) : (
                <button
                  onClick={openDietaryPassport}
                  className="text-xs text-white/90 underline hover:text-white"
                >
                  Atur Pantangan Alergi
                </button>
              )}
            </div>
          </div>
        </div>

        {/* ── 3. Category & Day Filter Pills (Horizontal Scroll) ─────────────── */}
        {isAuthenticated && customer && (
          <section className="flex flex-col gap-4 rounded-[1.5rem] border border-[#e8c9bd] bg-[#fff8f2] p-4 sm:px-6">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-start gap-3">
                <span className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-[#7e2933] text-[#fff8f2]"><Sparkles className="size-5" /></span>
                <div>
                  <p className="font-display text-lg font-bold text-[#421f22]">Chef BOB menyapa, {customer.display_name || 'Food Lover'}!</p>
                  <p className="text-sm text-[#806a63]">{homePreferenceAlerts.length ? 'Beranda dan pilihan menu mengikuti catatan profilmu.' : 'Ceritakan alergi dan seleramu ke Chef BOB agar beranda bisa menyesuaikan.'}</p>
                </div>
              </div>
              <button type="button" onClick={() => navigate('/ai')} className="shrink-0 self-start rounded-full border border-[#b76a63] px-4 py-2 text-sm font-bold text-[#7e2933] hover:bg-[#f8e6df]">Ngobrol dengan Chef BOB →</button>
            </div>
            {homePreferenceAlerts.length > 0 && (
              <div className="flex flex-wrap gap-2" aria-label="Peringatan dan preferensi makanan tersimpan">
                {homePreferenceAlerts.map((alert) => (
                  <span key={alert} className="inline-flex items-center gap-1.5 rounded-full border border-[#e7c1a0] bg-[#fff0dd] px-3 py-1.5 text-xs font-semibold text-[#713a25]">
                    <ShieldAlert className="size-3.5 shrink-0" />{alert}
                  </span>
                ))}
              </div>
            )}
          </section>
        )}

        {personalizedPicks.length > 0 && (
          <section className="space-y-3"><div><p className="text-[10px] font-black uppercase tracking-[.2em] text-[#ae3d38]">Pilihan lolos pantangan dan safety</p><h2 className="font-display text-2xl font-bold text-[#301d1b]">{hasMacroGoal ? 'Pilihan aman untuk profilmu' : 'Rekomendasi buat kamu'}</h2>{hasMacroGoal && <p className="text-xs text-[#806a63]">Makro per porsi belum terverifikasi, jadi pilihan ini belum dinilai untuk target gizimu.</p>}</div><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{personalizedPicks.map((menu) => <button type="button" key={menu.menu_id} onClick={() => { setSelectedDay(menu.hari); document.getElementById('food-catalog-grid')?.scrollIntoView({ behavior: 'smooth' }) }} className="flex items-center gap-3 rounded-2xl border border-[#ead9d0] bg-white p-3 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"><img src={MENU_IMAGES[menu.menu_id] || MENU_IMAGES[menu.nama_menu] || DEFAULT_FOOD_IMAGE} alt="" className="size-16 rounded-xl object-cover"/><span><span className="block text-[10px] font-bold uppercase tracking-wider text-[#ae3d38]">{hasMacroGoal ? 'Lolos safety · makro belum dicek' : favorites.includes(menu.menu_id) ? 'Favoritmu · lolos safety' : aiRecommendations.some((item) => item.menu_id === menu.menu_id) ? 'Saran akun · lolos safety' : 'Cocok dengan profil'}</span><span className="mt-1 block text-sm font-bold leading-snug text-[#392a27]">{menu.nama_menu}</span><span className="text-xs text-stone-500">{menu.hari} · resep terverifikasi</span></span></button>)}</div></section>
        )}
        {isAuthenticated && passport?.structured && personalizedPicks.length === 0 && !catalogLoading && (
          <section className="flex items-start gap-3 rounded-2xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950">
            <ShieldAlert className="mt-0.5 size-5 shrink-0" />
            <p>Belum ada menu yang lolos seluruh pantangan dan verifikasi resep untuk rekomendasi. Profilmu tetap diterapkan saat menu diperiksa; buka detail menu sebelum memesan.</p>
          </section>
        )}

        <section className="overflow-hidden rounded-[1.75rem] border border-[#ead9d0] bg-[#fffaf6] shadow-[0_18px_50px_rgba(82,35,31,.08)]">
          <div className="flex flex-wrap items-end justify-between gap-4 border-b border-[#ead9d0] px-5 py-5 md:px-7">
            <div>
              <p className="text-[10px] font-black uppercase tracking-[.24em] text-[#ae3d38]">Dova · menu edition {batchNumber ? `W${String(batchNumber).padStart(2, '0')}` : ''}</p>
              <h2 className="mt-1 font-display text-2xl font-bold tracking-tight text-[#301d1b] md:text-3xl">Kalender menu</h2>
              <p className="mt-1 text-xs text-[#806a63]">{batchDateRange} <span className="mx-1.5 text-[#c7a99c]">/</span> pilih hari untuk melihat menunya</p>
            </div>
            <button type="button" onClick={() => setSelectedDay('all')} className={cn('inline-flex items-center gap-2 rounded-full border px-4 py-2.5 text-xs font-bold transition', selectedDay === 'all' ? 'border-[#8f2833] bg-[#8f2833] text-white shadow-md shadow-[#8f2833]/15' : 'border-[#dfc7bc] bg-white text-[#713a39] hover:border-[#b84b48]')}>
              <CalendarDays className="size-4" /> Seluruh minggu <span className="rounded-full bg-white/15 px-2 py-0.5">{menuList.length}</span>
            </button>
          </div>

          <div className="grid grid-cols-2 gap-3 p-4 sm:grid-cols-3 md:gap-3.5 md:p-6 lg:grid-cols-4 2xl:grid-cols-7">
            {Object.values(DAYS_LIST).filter((day) => day.id !== 'all').map((day) => {
              const isActive = selectedDay === day.id
              const dateInfo = serviceDays.find((entry) => entry.hari === day.id)
              const dayMenus = menuList.filter((menu) => menu.hari === day.id)
              const featuredMenu = dayMenus[0]
              const imageUrl = featuredMenu ? MENU_IMAGES[featuredMenu.menu_id] || MENU_IMAGES[featuredMenu.nama_menu] || DEFAULT_FOOD_IMAGE : DEFAULT_FOOD_IMAGE
              return (
                <button key={day.id} type="button" onClick={() => setSelectedDay(day.id)} className={cn('group relative flex min-h-[178px] flex-col overflow-hidden rounded-2xl border text-left transition-all duration-200 hover:-translate-y-1 hover:shadow-lg active:scale-[.99]', isActive ? 'border-[#8f2833] bg-[#8f2833] text-white shadow-lg shadow-[#8f2833]/15' : 'border-[#ead9d0] bg-white text-[#513b36] hover:border-[#c55a50]')}>
                  <div className="relative h-[82px] w-full overflow-hidden bg-[#f2e3db]">
                    <img src={imageUrl} alt={featuredMenu?.nama_menu || `Menu ${day.label}`} loading="lazy" className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105" />
                    <span className="absolute left-2.5 top-2.5 rounded-full bg-[#fffaf6]/95 px-2.5 py-1 text-[9px] font-black uppercase tracking-wide text-[#7e2933] shadow-sm">{dateInfo?.date_label?.split(' ').slice(-2).join(' ') || day.label}</span>
                    {isActive && <span className="absolute right-2 top-2 rounded-full bg-[#8f2833] px-2 py-1 text-[9px] font-bold text-white">Dipilih</span>}
                  </div>
                  <div className="flex flex-1 flex-col px-3 py-3">
                    <span className="font-display text-lg font-bold leading-tight">{day.label}</span>
                    <span className={cn('mt-1 line-clamp-2 text-[10px] leading-snug', isActive ? 'text-white/80' : 'text-[#806a63]')}>{featuredMenu?.nama_menu || 'Menu akan segera hadir'}</span>
                    <span className={cn('mt-auto pt-2 text-[9px] font-black uppercase tracking-[.12em]', isActive ? 'text-[#f6d8bc]' : 'text-[#ae3d38]')}>{dayMenus.length ? `${dayMenus.length} pilihan menu` : 'Segera'}</span>
                  </div>
                </button>
              )
            })}
          </div>
        </section>

        {/* ── 4. Popular Food Grid (Like "Popular Combos" in KFC App) ───────── */}
        <div id="food-catalog-grid" className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <h2 className="font-black text-stone-900 text-lg tracking-tight">
                {selectedDay === 'all' ? 'Semua Menu Pilihan Minggu Ini' : `Menu Hari ${selectedDay}`}
              </h2>
              <p className="text-xs text-stone-500">
                Pilih makanan favoritmu dan klik tanda + untuk memesan
              </p>
            </div>
            <span className="text-xs font-bold text-stone-400">
              {filteredMenus.length} Hidangan di Katalog
            </span>
          </div>

          {catalogLoading && menuList.length === 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4" aria-live="polite">
              {Array.from({ length: 3 }, (_, index) => (
                <div
                  key={index}
                  className="h-[360px] animate-pulse rounded-[1.75rem] border border-slate-200/90 bg-white shadow-[0_10px_35px_rgba(15,23,42,.06)]"
                  aria-label="Memuat menu"
                />
              ))}
            </div>
          ) : catalogError && menuList.length === 0 ? (
            <div className="rounded-3xl border border-rose-200 bg-rose-50 p-8 text-center space-y-3">
              <ShieldAlert className="size-10 text-rose-600 mx-auto" />
              <h3 className="font-bold text-rose-900">Katalog live belum tersedia</h3>
              <p className="text-xs text-rose-800">{catalogError.message}</p>
            </div>
          ) : filteredMenus.length === 0 ? (
            <div className="rounded-3xl border border-dashed border-stone-300 p-12 text-center bg-white space-y-3">
              <Utensils className="size-10 text-stone-400 mx-auto" />
              <h3 className="font-bold text-stone-700">Tidak ada menu yang sesuai</h3>
              <p className="text-xs text-stone-500">Coba ubah kata kunci pencarian atau pilih hari lain.</p>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setSelectedDay('all')
                  setSearchQuery('')
                }}
              >
                Reset Filter
              </Button>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {filteredMenus.map((menu) => {
                const conflicts = checkMenuConflict(menu)
                const hasConflict = conflicts.length > 0
                const dislikeMatches = matchingDislikes(menu)
                const recipeComponents = menu.bahan_detail.filter((item) => item.sumber === 'recipe_component' && item.ingredient_id)
                const recipePreferenceUnverified = dislikedTerms.length > 0 && (
                  menu.recipe_verification_status !== 'VERIFIED' ||
                  menu.recipe_has_unresolved_components !== false ||
                  recipeComponents.length === 0 ||
                  recipeComponents.some((item) => item.verification_status !== 'VERIFIED')
                )
                const menuDay = menuDateById.get(menu.menu_id)
                const menuSafety = menuDay?.safety.find((entry) => entry.menu_id === menu.menu_id)
                const isFavorite = favorites.includes(menu.menu_id)
                const imageUrl =
                  MENU_IMAGES[menu.menu_id] || MENU_IMAGES[menu.nama_menu] || DEFAULT_FOOD_IMAGE
                const cartItem = cart[cartKey(menu.menu_id)]
                const qtyInCart = cartItem?.quantity || 0

                return (
                  <Card
                    key={menu.menu_id}
                    role="button"
                    tabIndex={0}
                    onClick={() => setSelectedMenu(menu)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault()
                        setSelectedMenu(menu)
                      }
                    }}
                    className={cn(
                      'group cursor-pointer overflow-hidden rounded-[1.75rem] bg-white shadow-[0_10px_35px_rgba(15,23,42,.06)] transition-all duration-300 hover:-translate-y-1 hover:shadow-[0_18px_45px_rgba(15,23,42,.12)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-forest-600/40 flex flex-col justify-between',
                      hasConflict ? 'border-2 border-rose-600 ring-2 ring-rose-200/80' :
                        dislikeMatches.length > 0 ? 'border-2 border-amber-400 ring-1 ring-amber-100' :
                          'border border-slate-200/90 hover:border-forest-200',
                    )}
                  >
                    {/* Top Food Image Container */}
                    <div className="relative aspect-4/3 w-full overflow-hidden bg-stone-100">
                      <img
                        src={imageUrl}
                        alt={menu.nama_menu}
                        className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                        loading="lazy"
                      />

                      {/* Day Pill Tag & AI Recommendation Tag */}
                      <div className="absolute top-3 left-3 flex items-center gap-1.5">
                        <Badge className="bg-slate-950/80 backdrop-blur-md text-white text-[11px] font-semibold border-none">
                          <CalendarDays className="size-3 mr-1" />
                          {menuDateById.get(menu.menu_id)?.date_label || menu.date_label || menu.hari}
                        </Badge>
                        {(() => {
                          const rec = aiRecommendations.find((r) => r.menu_id === menu.menu_id)
                          if (rec && rec.score >= 50) {
                            return (
                              <Badge className="bg-amber-400 text-stone-950 font-black text-[10px] border-none shadow-xs flex items-center gap-1">
                                <Sparkles className="size-3 text-stone-900" />
                                <span>{Math.round(rec.score)}% Match AI</span>
                              </Badge>
                            )
                          }
                          return null
                        })()}

                      </div>

                      {/* Allergen Warning / Safe Badge */}
                      {hasConflict ? (
                        <Badge className="absolute bottom-3 left-3 bg-rose-600 text-white text-[10px] font-bold border-none shadow-md flex items-center gap-1 animate-pulse">
                          <ShieldAlert className="size-3" />
                          <span>Waspada: {conflicts.join(', ')}</span>
                        </Badge>
                      ) : dislikeMatches.length > 0 ? (
                        <Badge className="absolute bottom-3 left-3 bg-amber-500 text-stone-950 text-[10px] font-bold border-none shadow-md flex items-center gap-1">
                          <Heart className="size-3" />
                          <span>Kamu menghindari ini</span>
                        </Badge>
                      ) : menuSafety?.level === 'safe' ? (
                        <Badge className="absolute bottom-3 left-3 bg-emerald-700 text-white text-[10px] font-bold border-none shadow-md flex items-center gap-1">
                          <ShieldCheck className="size-3" />
                          <span>Cocok Untukmu</span>
                        </Badge>
                      ) : null}

                      {/* Wishlist Heart Toggle */}
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation()
                          toggleFavorite(menu.menu_id)
                        }}
                        className="absolute top-3 right-3 size-9 rounded-full bg-white/90 backdrop-blur-md flex items-center justify-center text-stone-700 hover:text-rose-600 active:scale-90 transition-all shadow-sm"
                        aria-label="Favorit"
                      >
                        <Heart
                          className={cn(
                            'size-4 transition-colors',
                            isFavorite ? 'fill-rose-600 text-rose-600' : 'text-stone-600'
                          )}
                        />
                      </button>
                    </div>

                    {/* Card Content & Details */}
                    <div className="p-4 space-y-2.5 flex-1 flex flex-col justify-between">
                      <div className="space-y-1.5">
                        <div className="flex items-start justify-between gap-2">
                          <h3 className="font-bold text-stone-900 text-base leading-snug group-hover:text-forest-700 transition-colors">
                            {menu.nama_menu}
                          </h3>
                        </div>

                        {hasConflict && (
                          <div role="alert" className="flex items-start gap-2 rounded-xl border border-rose-300 bg-rose-50 p-3 text-xs leading-relaxed text-rose-900">
                            <ShieldAlert className="mt-0.5 size-4 shrink-0 text-rose-700" />
                            <span><strong>Kamu tercatat alergi {conflicts.join(', ')}.</strong> Chef BOB menyarankan pilih menu lain.</span>
                          </div>
                        )}
                        {!hasConflict && dislikeMatches.length > 0 && (
                          <div className="flex items-start gap-2 rounded-xl border border-amber-300 bg-amber-50 p-3 text-xs leading-relaxed text-amber-950">
                            <Heart className="mt-0.5 size-4 shrink-0 text-amber-700" />
                            <span><strong>Kamu pernah bilang menghindari {dislikeMatches.join(', ')}.</strong> Mungkin ada pilihan lain yang lebih cocok.</span>
                          </div>
                        )}
                        {!hasConflict && dislikeMatches.length === 0 && recipePreferenceUnverified && (
                          <div className="flex items-start gap-2 rounded-xl border border-amber-300 bg-amber-50 p-3 text-xs leading-relaxed text-amber-950">
                            <ShieldAlert className="mt-0.5 size-4 shrink-0 text-amber-700" />
                            <span>Bahan resep belum terverifikasi lengkap; kecocokan dengan seleramu belum bisa dipastikan.</span>
                          </div>
                        )}

                        {/* Ingredients snippet */}
                        <p className="text-xs text-stone-500 line-clamp-2 leading-relaxed">
                          {menu.deskripsi ||
                            menu.bahan_detail.map((b) => b.nama).join(', ')}
                        </p>

                        {/* Allergen Tags / Badges */}
                        {menu.allergen_labels.length > 0 ? (
                          <div className="flex flex-wrap gap-1 pt-1">
                            {menu.allergen_labels.map((alg) => (
                              <span
                                key={alg}
                                className="text-[10px] bg-amber-50 text-amber-800 border border-amber-200/80 px-2 py-0.5 rounded-full font-medium"
                              >
                                {alg}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <div className="pt-1">
                            <span className="text-[10px] bg-emerald-50 text-emerald-800 border border-emerald-200 px-2 py-0.5 rounded-full font-medium">
                              Bebas Alergen Mayor
                            </span>
                          </div>
                        )}
                      </div>

                      {/* Verified metadata only; no synthetic rating/calorie claims. */}
                      <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-slate-500 pt-1">
                        <span className="rounded-full bg-slate-100 px-2 py-1">
                          {menu.bahan_detail.length} bahan tercatat
                        </span>
                        {menu.recipe_verification_status && (
                          <span className="rounded-full bg-emerald-50 px-2 py-1 text-emerald-700">
                            Resep {menu.recipe_verification_status.toLowerCase()}
                          </span>
                        )}
                        {menu.calories != null && <span>{menu.calories} kkal</span>}
                        {menu.protein_g != null && <span>{menu.protein_g}g protein</span>}
                      </div>

                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation()
                          setSelectedMenu(menu)
                        }}
                        className="w-fit text-xs font-bold text-forest-700 transition-colors hover:text-forest-900"
                      >
                        Lihat detail menu →
                      </button>

                      {/* Price & Action Row */}
                      <div className="pt-2 border-t border-stone-100 flex items-center justify-between">
                        <div>
                          <div className="text-[10px] uppercase font-bold text-stone-400">Harga</div>
                          <div className="font-black text-base text-stone-900 tracking-tight">
                            {menu.price != null
                              ? `Rp ${menu.price.toLocaleString('id-ID')}`
                              : 'Harga mengikuti paket'}
                          </div>
                        </div>

                        {/* Quantity Stepper if in cart, or circular Plus button */}
                        {qtyInCart > 0 ? (
                          <div className="flex items-center gap-2 bg-stone-100 rounded-full p-1 border border-stone-200">
                            <button
                              type="button"
                              onClick={(event) => {
                                event.stopPropagation()
                                updateQuantity(menu.menu_id, -1)
                              }}
                              className="size-7 rounded-full bg-white flex items-center justify-center text-stone-700 hover:bg-stone-200 active:scale-90 transition-all"
                            >
                              <Minus className="size-3.5" />
                            </button>
                            <span className="font-bold text-xs px-1 text-stone-900">{qtyInCart}</span>
                            <button
                              type="button"
                              onClick={(event) => {
                                event.stopPropagation()
                                handleAddToCartClick(menu)
                              }}
                              className="size-7 rounded-full bg-forest-900 text-white flex items-center justify-center hover:bg-forest-800 active:scale-90 transition-all shadow-xs"
                            >
                              <Plus className="size-3.5" />
                            </button>
                          </div>
                        ) : (
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation()
                              handleAddToCartClick(menu)
                            }}
                            className="size-10 rounded-full bg-forest-900 text-white flex items-center justify-center shadow-md shadow-forest-900/30 hover:bg-forest-800 hover:scale-105 active:scale-95 transition-all"
                            aria-label={`Tambah ${menu.nama_menu}`}
                          >
                            <Plus className="size-5 stroke-[2.5]" />
                          </button>
                        )}
                      </div>
                    </div>
                  </Card>
                )
              })}
            </div>
          )}
        </div>
      </main>
      </div>

      {/* ── Desktop Right Column: Order Menu (Cart & Checkout matching Image 2) ── */}
      {false && (
      <aside className="hidden xl:flex flex-col w-96 bg-white border-l border-stone-200/80 shrink-0 h-screen sticky top-0 p-5 overflow-y-auto justify-between z-10 shadow-2xs">
        <div className="space-y-4">
          {/* Dova Pay is intentionally removed; this column starts with the cart context. */}
          <div className="hidden space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-extrabold text-stone-800">Your Balance</span>
              <button
                onClick={() => toast.info('Dova Pay belum terhubung ke provider live.')}
                className="text-[11px] font-bold text-amber-600 hover:underline"
              >
                Top Up
              </button>
            </div>
            <div className="rounded-3xl bg-gradient-to-tr from-orange-600 via-amber-600 to-rose-600 p-4 text-white shadow-md relative overflow-hidden">
              <div className="flex justify-between items-start">
                <span className="text-[10px] font-extrabold uppercase tracking-widest text-amber-200">
                  Dova Pay • Belum Terhubung
                </span>
                <div className="size-6 rounded-md bg-amber-400/40 border border-amber-300 flex items-center justify-center text-[10px]">
                  💳
                </div>
              </div>
              <div className="my-3 font-mono text-xs tracking-widest text-white/90">
                Provider pembayaran belum terhubung
              </div>
              <div className="flex justify-between items-end">
                <div>
                  <span className="text-[9px] uppercase tracking-wider text-white/70 block">
                    Status
                  </span>
                  <span className="font-extrabold text-sm text-white">Saldo belum tersedia</span>
                </div>
                <span className="text-[10px] font-mono text-white/80">—</span>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-[#ead9d0] bg-[#fffaf6] p-3.5 space-y-2">
            <span className="text-xs font-bold text-[#513b36] flex items-center gap-1.5"><MapPin className="size-3.5 text-[#a7353d]" />Alamat pengantaran</span>
            <p className="text-xs font-semibold text-stone-700">{deliveryAddress || 'Tambahkan alamat tujuan sebelum checkout.'}</p>
          </div>

          {/* Order Menu Items List (Image 2 right middle) */}
          <div className="space-y-2">
            <div className="flex items-center justify-between pb-1.5 border-b border-stone-100">
              <span className="text-xs font-extrabold text-stone-900 flex items-center gap-1.5">
                <ShoppingBag className="size-3.5 text-forest-700" /> Keranjang
              </span>
              <Badge className="bg-forest-50 text-forest-700 text-[10px] font-bold">
                {cartItemCount} Items
              </Badge>
            </div>

            <div className="space-y-2 max-h-[260px] overflow-y-auto pr-1">
              {cartItemsArray.length === 0 ? (
                <div className="text-center py-8 text-xs text-stone-400">
                  Keranjangmu kosong. Klik tanda '+' untuk memilih menu.
                </div>
              ) : (
                <div className="space-y-4">
                  {cartGroups.map(({ day, items }) => (
                    <section key={day} className="space-y-2">
                      <div className="flex items-center justify-between border-b border-stone-100 pb-1">
                        <h4 className="text-[11px] font-extrabold uppercase tracking-wider text-stone-700">
                          {DAYS_LIST[day].label}
                        </h4>
                        <span className="text-[10px] font-semibold text-stone-400">
                          {items.length} menu
                        </span>
                      </div>
                      <div className="space-y-2">
                        {items.map(({ menu, quantity }) => (
                          <div
                            key={cartKey(menu.menu_id)}
                            className="flex items-center justify-between gap-2.5 rounded-2xl border border-stone-200/60 bg-stone-50 p-2"
                          >
                            <img
                              src={
                                MENU_IMAGES[menu.menu_id] ||
                                MENU_IMAGES[menu.nama_menu] ||
                                DEFAULT_FOOD_IMAGE
                              }
                              alt={menu.nama_menu}
                              className="size-11 shrink-0 rounded-xl object-cover"
                            />
                            <div className="min-w-0 flex-1">
                              <p className="truncate text-xs font-bold text-stone-900">{menu.nama_menu}</p>
                              <p className="text-[11px] font-black text-forest-700">
                                {menu.price != null
                                  ? `Rp ${(menu.price * quantity).toLocaleString('id-ID')}`
                                  : 'Termasuk paket layanan'}
                              </p>
                            </div>
                            <div className="flex items-center gap-1 rounded-full border border-stone-200 bg-white p-0.5">
                              <button
                                onClick={() => updateQuantity(menu.menu_id, -1)}
                                className="flex size-5 items-center justify-center rounded-full text-stone-600 hover:bg-stone-100"
                              >
                                <Minus className="size-2.5" />
                              </button>
                              <span className="px-1 text-xs font-bold">{quantity}</span>
                              <button
                                onClick={() => handleAddToCartClick(menu)}
                                className="flex size-5 items-center justify-center rounded-full bg-forest-900 text-white hover:bg-forest-800"
                              >
                                <Plus className="size-2.5" />
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </section>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Pricing breakdown & Checkout Button (Image 2 bottom right) */}
        {cartItemsArray.length > 0 && (
          <div className="space-y-2.5 pt-3 border-t border-stone-200 text-xs">
            <div className="flex justify-between text-stone-600">
              <span>Subtotal ({cartItemCount} porsi):</span>
              <span className="font-bold text-stone-900">
                {selectedPackage
                  ? `Rp ${cartSubtotal.toLocaleString('id-ID')}`
                  : 'Pilih paket live'}
              </span>
            </div>
            <div className="hidden space-y-1.5 rounded-xl bg-stone-50 p-2.5 border border-stone-200">
              <label htmlFor="desktop-checkout-package" className="text-[11px] font-bold text-stone-600">
                Paket layanan dari server
              </label>
              <select
                id="desktop-checkout-package"
                value={selectedPackageCode}
                onChange={(event) => setSelectedPackageCode(event.target.value)}
                disabled={isCheckoutLoading || Boolean(checkoutOrder)}
                className="w-full rounded-lg border border-stone-200 bg-white px-2 py-1.5 text-xs font-semibold text-stone-800"
              >
                <option value="">Pilih paket live...</option>
                {packages.map((item) => (
                  <option key={item.code} value={item.code}>
                    {item.name} — Rp {(item.price ?? 0).toLocaleString('id-ID')}
                  </option>
                ))}
              </select>
              <select
                aria-label="Metode pembayaran"
                value={paymentMethod}
                onChange={(event) => setPaymentMethod(event.target.value as 'qris' | 'va')}
                disabled={isCheckoutLoading || Boolean(checkoutOrder)}
                className="w-full rounded-lg border border-stone-200 bg-white px-2 py-1.5 text-xs text-stone-700"
              >
                <option value="qris">QRIS (provider webhook)</option>
                <option value="va">Virtual Account (provider webhook)</option>
              </select>
            </div>
            <div className="flex justify-between text-sm font-black text-stone-900 pt-1.5 border-t border-stone-100">
              <span>{selectedPackage ? 'Total paket:' : 'Estimasi cart:'}</span>
                <span className="text-forest-700 text-base">
                {selectedPackage
                  ? `Rp ${payableTotal.toLocaleString('id-ID')}`
                  : 'Pilih paket live'}
              </span>
            </div>

            <Button
              onClick={handleBeginCheckout}
              disabled={isCheckoutLoading}
              className="w-full rounded-2xl bg-amber-500 hover:bg-amber-600 text-stone-950 font-black h-11 text-xs shadow-md shadow-amber-500/20 mt-1"
            >
              {isCheckoutLoading ? 'Membuat order...' : 'Lanjutkan Pembayaran'}
            </Button>
          </div>
        )}
      </aside>
      )}

      {/* ── 5. SweetAlert: Post-Login Dietary Profile Dialog ───────────────── */}
      {/* ── 6. SweetAlert: Conflict Warning Dialog (When Clicking + on Risk Item) ── */}
      <MenuDetailModal
        menu={selectedMenu}
        imageUrl={selectedMenu ? MENU_IMAGES[selectedMenu.menu_id] || MENU_IMAGES[selectedMenu.nama_menu] || DEFAULT_FOOD_IMAGE : DEFAULT_FOOD_IMAGE}
        hasConflict={selectedMenu ? checkMenuConflict(selectedMenu).length > 0 : false}
        conflictLabels={selectedMenu ? checkMenuConflict(selectedMenu) : []}
        dislikeLabels={selectedMenu ? matchingDislikes(selectedMenu) : []}
        onClose={() => setSelectedMenu(null)}
        onAdd={() => {
          if (selectedMenu) {
            const menu = selectedMenu
            setSelectedMenu(null)
            handleAddToCartClick(menu)
          }
        }}
      />

      {conflictMenu && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-950/60 backdrop-blur-xs p-4 animate-in fade-in duration-200">
          <Card className="w-full max-w-md overflow-hidden rounded-3xl bg-white shadow-2xl border-none animate-in zoom-in-95 duration-200">
            <div className="bg-gradient-to-r from-red-600 to-rose-800 p-6 text-white text-center">
              <div className="size-14 rounded-2xl bg-white/20 backdrop-blur-md mx-auto flex items-center justify-center mb-3 animate-bounce">
                <ShieldAlert className="size-8 text-amber-300" />
              </div>
              <h3 className="font-black text-xl tracking-tight">PERINGATAN ALERGI!</h3>
              <p className="text-xs text-white/80 mt-1">
                Menu ini bertentangan dengan profil kesehatanmu
              </p>
            </div>

            <div className="p-6 space-y-4">
              <div className="rounded-2xl bg-rose-50 border border-rose-200 p-4 space-y-2">
                <div className="font-bold text-sm text-rose-950">
                  {conflictMenu.menu.nama_menu}
                </div>
                <div className="text-xs text-rose-800 leading-relaxed">
                  Menu ini mengandung bahan yang bentrok dengan alergimu:
                </div>
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {conflictMenu.matchedAllergens.map((alg) => (
                    <Badge
                      key={alg}
                      className="bg-rose-600 text-white font-bold text-xs px-2.5 py-1 border-none"
                    >
                      ⚠️ {alg}
                    </Badge>
                  ))}
                </div>
                <p className="text-[11px] text-rose-700 pt-2 leading-relaxed">
                  Dapur Dova Kitchen menyarankan untuk menghindari menu ini demi keselamatanmu. Bila
                  tetap memesan, tiket dapur akan ditandai dengan sorotan risiko khusus.
                </p>
              </div>

              <div className="flex flex-col gap-2 pt-2">
                <Button
                  onClick={() => setConflictMenu(null)}
                  variant="outline"
                  className="rounded-full border-stone-300 text-stone-700 h-11 text-sm font-semibold"
                >
                  Batalkan & Pilih Menu Lain
                </Button>

                <Button
                  onClick={() => executeAddToCart(
                    conflictMenu.menu,
                    true,
                    conflictMenu.matchedAllergens,
                  )}
                  className="rounded-full bg-rose-600 hover:bg-rose-700 text-white font-bold h-11 text-xs shadow-md shadow-rose-600/20"
                >
                  Saya Paham Risikonya, Tetap Tambahkan
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* ── 7. Shopping Cart Drawer (Slide-Over Sheet) ──────────────────────── */}
      {isCartOpen && (
        <div className="fixed inset-0 z-50 overflow-hidden">
          <div
            className="absolute inset-0 bg-stone-950/50 backdrop-blur-2xs transition-opacity"
            onClick={() => setIsCartOpen(false)}
          />

          <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
            <div className="w-screen max-w-md bg-white shadow-2xl flex flex-col justify-between rounded-l-3xl overflow-hidden animate-in slide-in-from-right duration-300">
              {/* Cart Header */}
              <div className="p-5 border-b border-stone-200 flex items-center justify-between bg-stone-50">
                <div className="flex items-center gap-2">
                  <ShoppingBag className="size-5 text-forest-700" />
                  <h3 className="font-bold text-lg text-stone-900">Keranjang Pesanan</h3>
                  <Badge className="bg-forest-50 text-forest-700 text-xs">{cartItemCount} item</Badge>
                </div>
                <button
                  onClick={() => setIsCartOpen(false)}
                  className="size-8 rounded-full bg-white border border-stone-200 flex items-center justify-center text-stone-500 hover:text-stone-800"
                >
                  <X className="size-4" />
                </button>
              </div>

              {/* Cart Items List */}
              <div className="flex-1 overflow-y-auto p-5 space-y-4">
                {cartItemsArray.length === 0 ? (
                  <div className="py-16 text-center space-y-3">
                    <ShoppingBag className="size-12 text-stone-300 mx-auto" />
                    <h4 className="font-bold text-stone-700">Keranjangmu masih kosong</h4>
                    <p className="text-xs text-stone-500">Pilih menu mingguan lezat di katalog.</p>
                    <Button
                      onClick={() => setIsCartOpen(false)}
                      className="rounded-full bg-forest-900 text-white text-xs font-bold"
                    >
                      Mulai Memilih
                    </Button>
                  </div>
                ) : (
                  <>
                    <div className="space-y-4">
                      {cartGroups.map(({ day, items }) => (
                        <section key={day} className="space-y-2">
                          <div className="flex items-center justify-between border-b border-stone-100 pb-1">
                            <h4 className="text-[11px] font-extrabold uppercase tracking-wider text-stone-700">
                              {DAYS_LIST[day].label}
                            </h4>
                            <span className="text-[10px] font-semibold text-stone-400">
                              {items.length} menu
                            </span>
                          </div>
                          <div className="space-y-3">
                      {items.map(({ menu, quantity, riskAccepted, matchedAllergens }) => (
                        <div
                          key={cartKey(menu.menu_id)}
                          className="flex gap-3 p-3 rounded-2xl border border-stone-200 bg-white shadow-2xs items-center justify-between"
                        >
                          <img
                            src={
                              MENU_IMAGES[menu.menu_id] ||
                              MENU_IMAGES[menu.nama_menu] ||
                              DEFAULT_FOOD_IMAGE
                            }
                            alt={menu.nama_menu}
                            className="size-16 rounded-xl object-cover shrink-0"
                          />

                          <div className="flex-1 min-w-0 space-y-1">
                            <div className="flex items-center gap-1.5">
                              <Badge className="bg-stone-100 text-stone-700 text-[10px] px-1.5 py-0">
                                {menu.hari}
                              </Badge>
                              {riskAccepted && (
                                <Badge className="bg-rose-100 text-rose-700 text-[9px] px-1 py-0">
                                  ⚠️ {matchedAllergens.join(', ')}
                                </Badge>
                              )}
                            </div>
                            <h4 className="font-bold text-xs text-stone-900 truncate">
                              {menu.nama_menu}
                            </h4>
                            <div className="font-black text-xs text-forest-700">
                              {menu.price != null
                                ? `Rp ${(menu.price * quantity).toLocaleString('id-ID')}`
                                : 'Termasuk paket layanan'}
                            </div>
                          </div>

                          <div className="flex items-center gap-1.5 bg-stone-100 rounded-full p-1 border border-stone-200 shrink-0">
                            <button
                              onClick={() => updateQuantity(menu.menu_id, -1)}
                              className="size-6 rounded-full bg-white flex items-center justify-center text-stone-700 hover:bg-stone-200"
                            >
                              <Minus className="size-3" />
                            </button>
                            <span className="font-bold text-xs px-1 text-stone-900">{quantity}</span>
                            <button
                              onClick={() => handleAddToCartClick(menu)}
                              className="size-6 rounded-full bg-forest-900 text-white flex items-center justify-center hover:bg-forest-800"
                            >
                              <Plus className="size-3" />
                            </button>
                          </div>
                        </div>
                      ))}
                          </div>
                        </section>
                      ))}
                    </div>

                    {/* Delivery Address Selection */}
                    <div className="rounded-2xl bg-stone-50 border border-stone-200 p-4 space-y-2.5">
                      <label htmlFor="delivery-address" className="text-xs font-bold text-[#513b36] flex items-center gap-1.5"><MapPin className="size-3.5 text-[#a7353d]" />Alamat pengantaran</label>
                      <Input
                        id="delivery-address"
                        value={deliveryAddress}
                        onChange={(event) => setDeliveryAddress(event.target.value)}
                        placeholder="Nama jalan, nomor, gedung, kecamatan, kota"
                        autoComplete="street-address"
                        className="h-11 rounded-xl border-[#e4ccc2] bg-white text-sm focus-visible:ring-[#a7353d]"
                      />
                      {deliveryAddress.trim().length >= 8 && <a href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(deliveryAddress.trim())}`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-[11px] font-semibold text-[#9b2d36] hover:underline">Pratinjau tujuan di Maps<ExternalLink className="size-3" /></a>}

                      <div>
                        <label className="text-[11px] text-stone-500 font-medium">Catatan Kurir:</label>
                        <Input
                          value={courierNotes}
                          onChange={(e) => setCourierNotes(e.target.value)}
                          className="h-8 text-xs mt-1 rounded-lg bg-white"
                        />
                      </div>
                    </div>
                  </>
                )}
              </div>

              {/* Cart Footer */}
              {cartItemsArray.length > 0 && (
                <div className="p-5 border-t border-stone-200 bg-white space-y-3 shadow-lg">
                  <div className="space-y-1.5 text-xs text-stone-600">
                    <div className="flex justify-between">
                      <span>Subtotal ({cartItemCount} porsi)</span>
                      <span className="font-bold text-stone-900">
                        {selectedPackage
                          ? `Rp ${cartSubtotal.toLocaleString('id-ID')}`
                          : 'Pilih paket live'}
                      </span>
                    </div>
                    <div className="hidden space-y-1.5 rounded-xl bg-stone-50 p-2.5 border border-stone-200">
                      <label htmlFor="mobile-checkout-package" className="text-[11px] font-bold text-stone-600">
                        Paket layanan dari server
                      </label>
                      <select
                        id="mobile-checkout-package"
                        value={selectedPackageCode}
                        onChange={(event) => setSelectedPackageCode(event.target.value)}
                        disabled={isCheckoutLoading || Boolean(checkoutOrder)}
                        className="w-full rounded-lg border border-stone-200 bg-white px-2 py-1.5 text-xs font-semibold text-stone-800"
                      >
                        <option value="">Pilih paket live...</option>
                        {packages.map((item) => (
                          <option key={item.code} value={item.code}>
                            {item.name} — Rp {(item.price ?? 0).toLocaleString('id-ID')}
                          </option>
                        ))}
                      </select>
                      <select
                        aria-label="Metode pembayaran"
                        value={paymentMethod}
                        onChange={(event) => setPaymentMethod(event.target.value as 'qris' | 'va')}
                        disabled={isCheckoutLoading || Boolean(checkoutOrder)}
                        className="w-full rounded-lg border border-stone-200 bg-white px-2 py-1.5 text-xs text-stone-700"
                      >
                        <option value="qris">QRIS (provider webhook)</option>
                        <option value="va">Virtual Account (provider webhook)</option>
                      </select>
                    </div>
                    <div className="flex justify-between font-black text-sm text-stone-900 pt-2 border-t border-stone-100">
                      <span>{selectedPackage ? 'Total paket' : 'Estimasi cart'}</span>
                      <span className="text-forest-700 text-base">
                        {selectedPackage
                          ? `Rp ${payableTotal.toLocaleString('id-ID')}`
                          : 'Pilih paket live'}
                      </span>
                    </div>
                  </div>

                  <Button
                    onClick={async () => {
                      if (await handleBeginCheckout()) setIsCartOpen(false)
                    }}
                    disabled={isCheckoutLoading}
              className="w-full rounded-full bg-forest-900 hover:bg-forest-800 text-white font-bold h-12 shadow-lg shadow-forest-900/30 text-sm"
                  >
                    {isCheckoutLoading
                      ? 'Membuat order...'
                      : selectedPackage
                        ? 'Lanjutkan Pembayaran →'
                        : 'Lanjutkan Pembayaran →'}
                  </Button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── 8. Payment Modal (server intent; lunas hanya dari webhook) ─────── */}
      {isPaymentOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-950/70 backdrop-blur-xs p-4 animate-in fade-in duration-200">
          <Card className="w-full max-w-md overflow-hidden rounded-3xl bg-white shadow-2xl border-none animate-in zoom-in-95 duration-200">
            {/* Header */}
            <div className="bg-gradient-to-r from-red-600 to-rose-700 p-5 text-white flex items-center justify-between">
              <div>
                <h3 className="font-black text-lg">Pembayaran Pesanan</h3>
                <p className="text-xs text-white/80">Selesaikan sebelum waktu habis</p>
              </div>
              {/* Countdown Pill */}
              <div className="flex items-center gap-1.5 bg-black/30 backdrop-blur-md px-3 py-1.5 rounded-full text-xs font-mono font-bold text-amber-300 border border-white/20">
                <Clock className="size-3.5" />
                <span>{formatTimer(paymentTimer)}</span>
              </div>
            </div>

            <div className="p-6 space-y-4">
              <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 space-y-2 text-sm">
                <div className="font-black text-amber-900">Payment intent {paymentIntent?.status ?? 'belum tersedia'}</div>
                <div className="flex justify-between text-xs text-amber-900">
                  <span>Order</span>
                  <span className="font-mono font-bold">{paymentIntent?.order_id ?? '—'}</span>
                </div>
                <div className="flex justify-between text-xs text-amber-900">
                  <span>Metode</span>
                  <span className="font-bold uppercase">{paymentIntent?.provider ?? paymentMethod}</span>
                </div>
                <div className="flex justify-between text-xs text-amber-900">
                  <span>Total server</span>
                  <span className="font-black">Rp {(paymentIntent?.amount ?? payableTotal).toLocaleString('id-ID')}</span>
                </div>
                <p className="pt-2 text-xs leading-relaxed text-amber-800">
                  Provider QRIS/VA belum terhubung di runtime ini. Jangan gunakan QR/VA simulasi dan jangan menandai sukses dari browser.
                  Status menjadi <strong>PAID</strong> hanya setelah webhook bertanda tangan diterima backend.
                </p>
              </div>

              {/* Action Buttons */}
              <div className="flex flex-col gap-2 pt-2">
                <Button
                  onClick={() => navigate('/orders')}
                  className="rounded-full bg-stone-900 hover:bg-stone-800 text-white font-bold h-12 shadow-lg text-sm"
                >
                  Lihat Pesanan & Status Pembayaran
                </Button>

                <Button
                  variant="ghost"
                  onClick={() => setIsPaymentOpen(false)}
                  className="rounded-full text-stone-500 h-9 text-xs"
                >
                  Tutup / Bayar Nanti
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* ── 9. Side Navigation Drawer ───────────────────────────────────────── */}
      {false && isSideMenuOpen && (
        <div className="fixed inset-0 z-50 overflow-hidden">
          <div
            className="absolute inset-0 bg-stone-950/50 backdrop-blur-2xs transition-opacity"
            onClick={() => setIsSideMenuOpen(false)}
          />

          <div className="fixed inset-y-0 left-0 max-w-full flex pr-10">
            <div className="w-screen max-w-xs bg-white shadow-2xl flex flex-col justify-between p-6 rounded-r-3xl animate-in slide-in-from-left duration-300">
              <div className="space-y-6">
                <div className="flex items-center justify-between pb-4 border-b border-stone-200">
                  <div className="flex items-center gap-2 font-black text-forest-900 text-lg">
                    DOVA KITCHEN
                  </div>
                  <button
                    onClick={() => setIsSideMenuOpen(false)}
                    className="size-8 rounded-full bg-stone-100 flex items-center justify-center text-stone-500"
                  >
                    <X className="size-4" />
                  </button>
                </div>

                <div className="space-y-1">
                  <Link
                    to="/order"
                    onClick={() => setIsSideMenuOpen(false)}
                    className="flex items-center gap-3 p-3 rounded-2xl bg-forest-50 text-forest-900 font-bold text-sm"
                  >
                    <Utensils className="size-4" />
                    <span>Menu Mingguan</span>
                  </Link>
                  <Link
                    to="/orders"
                    onClick={() => setIsSideMenuOpen(false)}
                    className="flex items-center gap-3 p-3 rounded-2xl text-stone-700 hover:bg-stone-50 font-semibold text-sm"
                  >
                    <ShoppingBag className="size-4" />
                    <span>Pesanan Saya</span>
                  </Link>
                  <button
                    type="button"
                    onClick={() => {
                      setIsSideMenuOpen(false)
                      if (!isAuthenticated) {
                        navigate('/login?next=%2Forder')
                      } else {
                        openDietaryPassport()
                      }
                    }}
                    className="flex w-full items-center gap-3 rounded-2xl p-3 text-left text-sm font-semibold text-stone-700 hover:bg-stone-50"
                  >
                    <ShieldCheck className="size-4" />
                    <span>Dietary Passport</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setIsSideMenuOpen(false)
                      const btn = document.querySelector('[aria-label="Tanya Chef BOB"]') as HTMLButtonElement
                      if (btn) btn.click()
                      else navigate('/ai')
                    }}
                    className="w-full flex items-center gap-3 p-3 rounded-2xl text-stone-700 hover:bg-stone-50 font-semibold text-sm text-left"
                  >
                    <Sparkles className="size-4 text-amber-500" />
                    <span>Asisten AI Chef (BOB)</span>
                  </button>
                </div>
              </div>

              <div className="pt-6 border-t border-stone-200 space-y-3">
                {isAuthenticated ? (
                  <>
                    <div className="text-xs">
                      <div className="font-bold text-stone-900">{customer?.display_name}</div>
                      <div className="text-stone-500">@{customer?.username}</div>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={logout}
                      className="w-full rounded-full border-stone-300 text-stone-700 text-xs"
                    >
                      Keluar
                    </Button>
                  </>
                ) : (
                  <Button
                    onClick={() => navigate('/login')}
                    className="w-full rounded-full bg-forest-900 text-white text-xs font-bold"
                  >
                    Masuk Akun
                  </Button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── 10. Sticky Bottom Navigation Bar (Matching KFC mobile screenshot) ── */}

    </div>
  )
}

function MenuDetailModal({
  menu,
  imageUrl,
  hasConflict,
  conflictLabels,
  dislikeLabels,
  onClose,
  onAdd,
}: {
  menu: Menu | null
  imageUrl: string
  hasConflict: boolean
  conflictLabels: string[]
  dislikeLabels: string[]
  onClose: () => void
  onAdd: () => void
}) {
  if (!menu) return null

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-forest-950/70 p-4 backdrop-blur-sm animate-fade-in"
      role="dialog"
      aria-modal="true"
      aria-labelledby="menu-detail-title"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <Card className="relative max-h-[min(760px,calc(100dvh-2rem))] w-full max-w-2xl overflow-y-auto rounded-[2rem] border-line bg-surface p-0 shadow-float animate-rise-in">
        <div className="relative aspect-[16/8] overflow-hidden bg-sunken sm:aspect-[16/7]">
          <img src={imageUrl} alt={menu.nama_menu} className="h-full w-full object-cover" />
          <div className="absolute inset-0 bg-gradient-to-t from-forest-950/70 via-transparent to-transparent" />
          <div className="absolute bottom-5 left-5 right-5 flex items-end justify-between gap-3 text-white sm:left-7 sm:right-7">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-gold-200">{menu.hari}</p>
              <h2 id="menu-detail-title" className="mt-1 text-2xl leading-tight text-white sm:text-3xl">
                {menu.nama_menu}
              </h2>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="rounded-full border border-white/30 bg-black/20 p-2 text-white backdrop-blur-md transition-colors hover:bg-white/20"
              aria-label="Tutup detail menu"
            >
              <X className="size-5" />
            </button>
          </div>
        </div>

        <div className="space-y-5 p-5 sm:p-7">
          <p className="text-sm leading-relaxed text-muted-text">
            {menu.deskripsi || 'Detail menu belum memiliki deskripsi tambahan.'}
          </p>

          {hasConflict && (
            <div className="flex items-start gap-3 rounded-2xl border border-blocked-line bg-blocked-soft p-4 text-sm text-blocked-strong">
              <ShieldAlert className="mt-0.5 size-5 shrink-0" />
              <div>
                <p className="font-bold">Kamu tercatat alergi {conflictLabels.join(', ')}</p>
                <p className="mt-1 text-xs leading-relaxed">
                  Menu ini terdeteksi mengandung alergen tersebut. Chef BOB menyarankan kamu memilih menu lain.
                </p>
              </div>
            </div>
          )}

          {!hasConflict && dislikeLabels.length > 0 && (
            <div className="flex items-start gap-3 rounded-2xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950">
              <Heart className="mt-0.5 size-5 shrink-0 text-amber-700" />
              <div>
                <p className="font-bold">Kamu pernah bilang menghindari {dislikeLabels.join(', ')}</p>
                <p className="mt-1 text-xs leading-relaxed">Mungkin ada pilihan lain yang lebih cocok dengan seleramu.</p>
              </div>
            </div>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            <section className="rounded-2xl border border-line bg-sunken p-4">
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-sm font-bold text-ink">Bahan yang tercatat</h3>
                <span className="text-xs font-semibold text-muted-text">{menu.bahan_detail.length} bahan</span>
              </div>
              <ul className="mt-3 space-y-2">
                {menu.bahan_detail.map((ingredient) => (
                  <li key={`${ingredient.nama}-${ingredient.sumber}`} className="flex items-start gap-2 text-xs text-ink-soft">
                    <span className={`mt-1 size-1.5 shrink-0 rounded-full ${ingredient.is_critical_allergen ? 'bg-blocked' : 'bg-safe'}`} />
                    <span>
                      <span className="font-semibold">{ingredient.nama}</span>
                      <span className="block text-muted-text">{ingredient.sumber}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </section>

            <section className="rounded-2xl border border-line bg-sunken p-4">
              <h3 className="text-sm font-bold text-ink">Ringkasan nutrisi</h3>
              <div className="mt-3 grid grid-cols-2 gap-2">
                <Metric label="Kalori" value={menu.calories != null ? `${menu.calories} kkal` : 'Belum ada'} />
                <Metric label="Protein" value={menu.protein_g != null ? `${menu.protein_g} g` : 'Belum ada'} />
                <Metric label="Karbohidrat" value={menu.carbs_g != null ? `${menu.carbs_g} g` : 'Belum ada'} />
                <Metric label="Lemak" value={menu.fat_g != null ? `${menu.fat_g} g` : 'Belum ada'} />
              </div>
            </section>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {(menu.allergen_labels.length > 0 ? menu.allergen_labels : ['Bebas alergen mayor']).map((label) => (
              <span key={label} className="rounded-full bg-amber-50 px-3 py-1.5 text-xs font-semibold text-amber-900 ring-1 ring-inset ring-amber-200">
                {label}
              </span>
            ))}
            {menu.recipe_verification_status && (
              <span className="rounded-full bg-safe-soft px-3 py-1.5 text-xs font-semibold text-safe-strong ring-1 ring-inset ring-safe-line">
                Resep {menu.recipe_verification_status.toLowerCase()}
              </span>
            )}
          </div>

          <div className="flex flex-col-reverse gap-3 border-t border-line pt-5 sm:flex-row sm:items-center sm:justify-between">
            <Button type="button" variant="outline" onClick={onClose} className="rounded-xl">
              Tutup detail
            </Button>
            <Button type="button" onClick={onAdd} className="rounded-xl bg-forest-900 px-5 text-white hover:bg-forest-800">
              <Plus className="mr-2 size-4" /> Tambah ke keranjang
            </Button>
          </div>
        </div>
      </Card>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-surface p-3 ring-1 ring-inset ring-line">
      <p className="text-[10px] font-bold uppercase tracking-wider text-muted-text">{label}</p>
      <p className="mt-1 text-xs font-bold text-ink">{value}</p>
    </div>
  )
}
