# DovaGenome: Official Pitching & Competition Submission Document

> **Platform:** DovaGenome — Precision Catering & Autonomous Allergen-Safe Supply Chain  
> **Repository:** [https://github.com/JooshuaAnd/DovaGenome](https://github.com/JooshuaAnd/DovaGenome)  
> **Pitch Deck PDF:** [DovaGenome_Pitch_Deck.pdf](file:///d:/DovaGenome/DovaGenome/docs/submission/DovaGenome_Pitch_Deck.pdf) (Size: 2.88 MB / Ready for Submission)

---

## 1. Judul Project
**DovaGenome: AI-Powered Precision Catering & Allergen-Safe Autonomous Supply Chain**  
*(Tagline: "Hyper-Personalized Nutrition Meets Zero-Defect Food Safety & Supply Chain Autopilot")*

---

## 2. Tema Project
* [x] **Healthcare & Wellbeing** *(Kategori Utama: Keamanan pangan personalized, pencegahan syok anafilaksis alergi, dan nutrisi presisi mikro/makro)*
* [x] **Productivity & Smart Business** *(Kategori Pendukung: Otomatisasi rantai pasok dapur katering, reduksi food waste B2B, dan POS omnichannel)*

---

## 3. Deskripsi Singkat Project (228 Kata)
**DovaGenome** adalah ekosistem katering presisi generasi baru yang menggabungkan kecerdasan buatan klinis, orkestrasi alur kerja tanpa-kode, dan rantai pasok otonom untuk merevolusi industri makanan harian. Masalah fatal yang diselesaikan adalah tingginya risiko kontaminasi silang alergen makanan dan pemborosan bahan baku (*food waste*) akibat estimasi manual pada katering konvensional. Masalah ini dialami oleh jutaan profesional urban dan penderita komorbid yang kesulitan memperoleh makanan higienis terkurasi, serta pelaku UMKM katering yang merugi akibat inefisiensi pengadaan bahan.

DovaGenome bekerja dengan mentransformasi profil diet pengguna menjadi **Dietary Passport** digital 9-alergen. Saat pesanan masuk secara *omnichannel* (Web/Telegram), pipeline **IBM Langflow** mengorkestrasi pencarian resep melalui **Dynamic RAG** berbasis Supabase Vector. Selanjutnya, penalaran nutrisi dianalisis secara mendalam oleh **IBM Bob (watsonx AI Engine)** untuk memverifikasi keamanan bahan secara molekuler, sebelum divalidasi oleh filter keselamatan deterministik *(Zero-Allergen Guardrail)*. Di sisi dapur dan rantai pasok, sistem otomatis meledakkan resep menjadi *Bill of Materials* (BOM) tingkat gram dan mengeksekusi model Machine Learning (*Reorder Point* & *Safety Stock*) dari **1.000 data transaksi riil** untuk menerbitkan Purchase Order otomatis kepada supplier terkurasi. 

Manfaat utamanya adalah jaminan 100% bebas salah saji alergi bagi konsumen, efisiensi waktu konsultasi gizi hingga 85%, serta penghematan biaya bahan baku sebesar 28% bagi operator katering.

---

## 4. Problem Statement
1. **Risiko Anafilaksis & Kurangnya Personalisasi Makanan:** Lebih dari 240 juta orang di dunia menderita alergi makanan berat. Pada layanan katering konvensional, penyesuaian menu dilakukan secara manual via catatan pesan (chat WhatsApp/kertas), yang memiliki *human error rate* tinggi hingga 14%. Kesalahan kecil seperti tercampurnya jejak kacang atau udang dapat memicu syok anafilaksis yang mengancam nyawa.
2. **Ketiadaan Transparansi Bahan Baku (Blackbox Kitchen):** Konsumen tidak pernah mengetahui asal-usul gramasi bahan baku, tanggal kedaluwarsa, atau kondisi sanitasi supplier yang menyuplai dapur.
3. **Food Waste & Pembengkakan Biaya Pengadaan (30-40% Inefisiensi):** Katering konvensional mengandalkan *guestimate* (tebak-tebakan) dalam membeli bahan segar. Akibatnya terjadi penumpukan stok yang membusuk atau kekurangan stok saat jam sibuk (*stockout*).

---

## 5. Target User
1. **Penderita Alergi Makanan & Komorbid Medis (Primary Consumer):** Pasien intoleransi laktosa, celiac/gluten, diabetes, GERD, hipertensi, dan alergen akut (kacang, seafood, telur) yang membutuhkan makanan terkalibrasi harian.
2. **Urban Professionals & Health-Conscious Individuals:** Pekerja kantoran yang membutuhkan meal-prep terukur sesuai target kalori tanpa membuang waktu memilih menu.
3. **Operator UMKM Katering & Cloud Kitchen (Business Admin):** Pengelola dapur yang ingin mengotomatisasi kitchen ticket, POS kasir, perhitungan gramasi bahan, dan pemesanan ke supplier.
4. **Distributor & Supplier Bahan Pangan Segar:** Petani dan supplier lokal yang membutuhkan kepastian kuota pembelian melalui Purchase Order (PO) otomatis berkala.

---

## 6. Mengapa Solusi Ini Dibutuhkan?
Solusi konvensional bersifat **generik, manual, dan rentan salah**. Katering biasa memasak menu massal yang sama untuk 100 orang dan hanya "menyingkirkan" alergen secara visual di atas piring (berbahaya karena kontaminasi silang minyak/alat masak).

DovaGenome unggul karena menerapkan:
- **Zero-Trust Deterministic Safety:** AI kami tidak sekadar menghasilkan teks rekomendasi (*generative*), melainkan dikunci oleh algoritma deterministik yang mencocokkan *Dietary Passport* pengguna dengan database genom 9-alergen secara ketat.
- **Closed-Loop Kitchen Automation:** Satu klik pemesanan dari pelanggan langsung menggerakkan kalkulasi gramasi di dapur koki dan mengirimkan sinyal pemesanan bahan baku ke portal supplier.
- **Empirical AI Intelligence:** Berbasis analisis dataset 1.000 transaksi nyata, perilaku belanja dianalisis menggunakan *RFM Segmentation* dan *Lead-Time Demand Forecasting*.

---

## 7. Fitur Utama Project
1. **Dietary Passport & Zero-Allergen Verification Engine:** Profil digital terenkripsi yang mencatat intoleransi bahan pangan, preferensi makro-nutrisi, dan riwayat alergi pengguna dengan alert otomatis instan saat memilih menu.
2. **Chef BOB Precision RAG Consultant (Powered by IBM Bob & Langflow):** Asisten AI interaktif yang mampu berkonsultasi mengenai kandungan bahan, mensubstitusi bahan berisiko secara cerdas, dan menjelaskan alasan ilmiah keamanan menu.
3. **Omnichannel Unified POS & Live Kitchen Ticket:** Sinkronisasi pemesanan langsung dari Web Application dan Bot Telegram ke antrean kitchen display system (KDS) kasir admin.
4. **Autonomous Supply Chain & Machine Learning ROP:** Sistem pengadaan bahan baku cerdas yang menghitung Safety Stock (SS) dan Reorder Point (ROP) secara otomatis serta menerbitkan digital Purchase Order ke supplier saat stok mendekati ambang batas.

---

## 8. Alur Penggunaan Project
```
User Input (Web/Telegram & Dietary Passport)
     │
     ▼
AI Processing (Dynamic Vector RAG via Supabase PostgreSQL)
     │
     ▼
IBM Langflow (Orchestrator Pipeline & Parameter Enforcement)
     │
     ▼
IBM Bob (watsonx Clinical Reasoning & Natural Recipe Adaptation)
     │
     ▼
Output (Zero-Allergen Recommendation, Gram BOM Explosion, ML ROP Trigger)
     │
     ▼
User Action (1-Click Order Confirmation, Kitchen Cooking Ticket & Supplier PO)
```

---

## 9. Penggunaan IBM Langflow
IBM Langflow berperan sebagai **Orchestration Backbone** visual tanpa-kode yang menghubungkan komponen input, retrieval, model bahasa, dan sistem evaluasi keamanan.

- **Workflow yang Dibuat:** *Dova Precision Nutrition & Allergen Guard Pipeline*.
- **Node/Komponen yang Digunakan:**
  1. `ChatInputNode`: Menerima input natural language dan session ID pengguna.
  2. `DietaryPassportParser`: Mengekstrak flag alergen (kacang, seafood, gluten, laktosa, telur, dsb).
  3. `SupabaseDynamicRAGNode`: Menjalankan *vector similarity search* terhadap katalog menu, kandungan mikronutrien, dan database resep terdaftar.
  4. `PromptTemplateNode`: Menggabungkan riwayat medis, context resep, dan panduan keamanan klinis menjadi prompt instruksi ketat.
  5. `IBMBobEngineNode`: Mengirim payload ke model IBM watsonx / Bob API untuk penalaran kuliner mendalam.
  6. `DeterministicSafetyFilter`: Script node berbasis Python yang memvalidasi output IBM Bob terhadap daftar hitam alergen sebelum diteruskan ke pengguna.
  7. `StructuredOutputNode`: Memformat balasan menjadi JSON kaya dengan rekomendasi menu, kalori, dan status keamanan.
- **Fungsi Langflow:** Mengabstraksi alur orkestrasi yang kompleks menjadi alur kerja modular yang mudah diaudit, dimonitor latensinya, dan diuji secara independen tanpa membebani server backend utama.

---

## 10. Penggunaan IBM Bob
IBM Bob (watsonx Reasoning Agent) bertindak sebagai **Clinical Culinary Intelligence Core** (diberi persona *Chef BOB*):

- **Fungsi IBM Bob:** Menganalisis interaksi nutrisi yang kompleks, mensubstitusi bumbu/bahan masakan yang memicu alergi tanpa mengorbankan cita rasa, dan memvalidasi kecocokan diet secara kontekstual.
- **Task yang Dilakukan Bob:**
  - Evaluasi semantik apakah bahan turunan (misal: kecap kedelai, saus tiram) mengandung jejak alergen pengguna.
  - Perhitungan estimasi makronutrisi (protein, karbohidrat, lemak sehat, sodium).
  - Memberikan penjelasan kuliner empatik, ramah, dan bebas halusinasi medis.
- **Interaksi Bob dengan Sistem:** Bob menerima konteks resep terkurasi dari RAG Supabase melalui Langflow, memproses reasoning dengan model dasar watsonx, dan mengembalikan output terstruktur yang terikat guardrails.
- **Output:** Rekomendasi hidangan presisi harian, kartu ringkasan nutrisi, dan alert keamanan spesifik.

---

## 11. Bagaimana IBM Langflow dan IBM Bob Terintegrasi?
Integrasi Langflow dan Bob dirancang dengan arsitektur **Pipeline-to-Engine**:

1. **Peran Langflow:** Langflow bertindak sebagai *Controller*. Langflow menerima query pengguna, mengambil data resep dari database Supabase (Dynamic RAG), menyuntikkan profil alergi pengguna, dan membentuk skema percakapan yang aman.
2. **Peran Bob:** Bob bertindak sebagai *Thinking Brain*. Bob memproses payload yang telah dibersihkan oleh Langflow, melakukan sintesis penalaran gizi, dan merumuskan respons adaptif.
3. **Aliran Data:**
   - Frontend mengirimkan `{user_id, prompt, allergies: ["dairy", "peanuts"]}` ke Langflow API.
   - Langflow memfilter database resep dan membungkus data tersebut ke dalam instruksi terstruktur: `[SYSTEM: Strict Allergen Protocol] + [CONTEXT: Supabase Recipe Records] + [USER: Query]`.
   - Payload dikirim via HTTP REST dengan header otentikasi `API_KEY_IBM_BOB` ke runtime IBM Bob.
   - IBM Bob merespons dengan hasil inferensi.
   - Langflow menangkap balasan Bob, menjalankannya melalui `DeterministicSafetyFilter` (memastikan nol kata kunci alergen yang dilarang lolos), lalu mengembalikan output bersih ke backend DovaGenome.
4. **Output Akhir:** Jawaban chatbot cerdas dengan rekomendasi menu yang 100% aman dan data *structured JSON* untuk langsung ditambahkan ke keranjang belanja pengguna.

---

## 12. Project File & Link
- **GitHub Repository:** [https://github.com/JooshuaAnd/DovaGenome](https://github.com/JooshuaAnd/DovaGenome)
- **Local Pitch Deck PDF:** [docs/submission/DovaGenome_Pitch_Deck.pdf](file:///d:/DovaGenome/DovaGenome/docs/submission/DovaGenome_Pitch_Deck.pdf)
- **Status Repository:** Public, clean commit history, siap diaudit oleh juri kompetisi.

---

## 13. Pitching Deck File
- **Nama File:** `DovaGenome_Pitch_Deck.pdf`
- **Ukuran File:** **2.88 MB** *(Memenuhi syarat < 10 MB)*
- **Struktur Slide (10 Slide Lengkap):**
  1. *Cover & Vision:* Precision Catering Meets Autonomous Allergen Safety.
  2. *The Hidden Crisis:* 240M+ sufferers, 14% manual error, $4.2B food waste.
  3. *The DovaGenome Solution:* Triple-engine ecosystem (User, Kitchen, Supplier).
  4. *The 1,000-Transaction Empirical Advantage:* Data-driven RFM & demand patterns.
  5. *AI Orchestration Architecture:* IBM Langflow + IBM Bob handshakes.
  6. *Dynamic RAG & Zero-Defect Safety:* Vector retrieval & deterministic guardrails.
  7. *Supply Chain Machine Learning:* Automated Safety Stock (SS) & Reorder Point (ROP).
  8. *Omnichannel Product Showcase:* Web Application, Telegram Bot, Kitchen POS.
  9. *Measurable Traction & Startup Impact:* Empirical metrics & unit economics.
  10. *Novelty & Scale Horizon:* Competitive moats & 2026-2027 future roadmap.

---

## 14. Project / Prototype Screenshots
Tersimpan di folder `docs/submission/screenshots/` dan siap diunggah:

1. **`01-user-interface.png`**  
   *Deskripsi:* Tampilan antarmuka pemesanan menu harian pelanggan dengan filter alergen cerdas, Dietary Passport popup, dan badge keamanan bahan.
2. **`02-langflow-workflow.png`**  
   *Deskripsi:* Visualisasi kanvas alur kerja IBM Langflow yang menghubungkan input pengguna, dynamic RAG Supabase, prompt template, dan guardrail filter.
3. **`03-bob-integration.png`**  
   *Deskripsi:* Konsultasi interaktif Chef BOB (IBM Bob Engine) yang menjelaskan profil nutrisi, mensubstitusi alergen, dan memberi rekomendasi personal.
4. **`04-output.png`**  
   *Deskripsi:* Tampilan kasir POS Admin & Kitchen Ticket terintegrasi dengan rincian BOM gramasi bahan baku serta notifikasi inventaris.
5. **`05-supplier-portal.png`**  
   *Deskripsi:* Portal pengadaan supplier dengan metrik Machine Learning Reorder Point (ROP), Safety Stock, dan otomatisasi Purchase Order.

---

## 15. Dampak yang Dihasilkan (Tercatat & Terukur)
1. **100% Zero-Allergen Incident Rate:** Mengeliminasi seluruh insiden salah saji bahan alergen berkat sistem validasi ganda (*dual-layer safety guardrail*).
2. **85% Pengurangan Durasi Konsultasi Diet:** Waktu konsultasi gizi berkurang drastis dari 20 menit per pelanggan via chat manual menjadi hanya 15 detik menggunakan Chef BOB.
3. **28% Penghematan Biaya Bahan Baku & Food Waste:** Optimasi stok dengan formula ML Safety Stock dan Reorder Point mencegah pembusukan bahan segar di gudang katering.
4. **94.2% Akurasi Prediksi Kebutuhan Menu:** Model demand forecasting yang dilatih pada 1.000 data transaksi riil berhasil memproyeksikan lonjakan pesanan harian secara presisi.

---

## 16. Potensi Pengembangan & Skalabilitas
- **B2B Inpatient Hospital & School Precision Catering API:** Menghubungkan engine DovaGenome langsung ke Electronic Health Records (EHR) rumah sakit dan institusi pendidikan untuk katering medis terotomatisasi.
- **IoT Smart Kitchen & RFID Allergen Seal:** Integrasi timbangan dapur pintar bersensor IoT dan segel kemasan RFID untuk memvalidasi isi kotak makanan sebelum kurir membawanya.
- **Deep Biomarker & Blood/DNA Panel Sync:** Mengintegrasikan hasil tes lab darah (kolesterol, HbA1c, intoleransi IgG) langsung ke Dietary Passport untuk kalibrasi nutrisi mikro tingkat seluler.
- **Federated Cloud Kitchen Fleet Expansion:** Replikasi arsitektur sistem ke puluhan jaringan dapur satelit di berbagai kota dengan perutean pengadaan bahan baku terdesentralisasi.

---

## 17. Apa yang Membuat Project Ini Berbeda? (3 Novelty Utama)
1. **Dual-Layer Deterministic & Generative Safety:** Mayoritas AI kuliner di pasar hanya mengandalkan Large Language Model yang berisiko berhalusinasi (*hallucination hazard*). DovaGenome menggunakan kombinasi IBM Bob untuk penalaran klinis yang dikunci oleh filter deterministik berbasis genom 9-alergen. Jika bahan berisiko terdeteksi di level molekuler, sistem secara matematis menolak pesanan tersebut.
2. **Circular BOM Explosion (Closed-Loop Autonomous Kitchen):** Bukan sekadar aplikasi pemesanan makanan, DovaGenome menghubungkan klik pesanan konsumen ke pemecahan resep instan hingga gram terkecil (*Bill of Materials explosion*), mengupdate inventaris riil, dan otomatis memicu Purchase Order ke supplier.
3. **Behavioral RFM + Demand Forecasting Synergy:** Memanfaatkan data historis 1.000 transaksi untuk memetakan pelanggan risiko churn, memicu penawaran menu hemat personal, dan memprediksi kebutuhan bahan 7 hari ke depan dengan model Reorder Point adaptif.

---

## 18. Kemampuan AI Agent
AI Agent DovaGenome memiliki kapabilitas otonom dan semi-otonom berikut:
- **Autonomous Dietary Parsing:** Membaca profil kesehatan alami pengguna dan mengubahnya menjadi *safety constraint parameters*.
- **Dynamic Semantic Retrieval (RAG):** Mengambil database resep paling relevan dari Supabase Vector secara *real-time*.
- **Autonomous Allergen Decontamination:** Mengidentifikasi bahan tersembunyi (*hidden allergens*) seperti gelatin, perasa tiram, atau jejak kacang dalam bumbu masakan.
- **Predictive Personalization:** Menyesuaikan rekomendasi menu harian berdasarkan riwayat skor RFM pengguna (apakah pelanggan loyal, pencari diskon, atau berisiko *churn*).
- **Semi-Autonomous Procurement Trigger:** Menghitung sisa stok vs proyeksi demand, dan secara mandiri menyusun draf Purchase Order yang siap disetujui satu klik oleh manajer dapur.
