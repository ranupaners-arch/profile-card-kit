# profile-card-kit

Buat README profil GitHub dari satu berkas konfigurasi: kartu bergaya neofetch dengan statistik GitHub langsung, tombol tautan pixel-art, dan grafik kontribusi Pac-Man dengan penghitung berjalan. Semuanya SVG, diperbarui tiap hari lewat GitHub Actions, dan mengikuti tema terang atau gelap pengunjung.

*English: [README.md](README.md)*

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./docs/preview/dark.svg">
  <img alt="Pratinjau kartu neofetch" src="./docs/preview/light.svg">
</picture>

*Angka di atas hanya contoh.*

## Isi

- [Mulai cepat](#mulai-cepat)
- [Membuat potret ASCII](#membuat-potret-ascii)
- [Konfigurasi](#konfigurasi)
- [Jalankan lokal](#jalankan-lokal)
- [Pemecahan masalah](#pemecahan-masalah)
- [Privasi dan kode pihak ketiga](#privasi-dan-kode-pihak-ketiga)

## Mulai cepat

Kamu hanya perlu akun GitHub. Tidak ada yang perlu dipasang: GitHub Actions yang bekerja. Untuk menjalankannya di komputermu, perlu Python 3.10 atau lebih baru (lihat [Jalankan lokal](#jalankan-lokal)).

**1. Buat repositori profil.**
Klik **Use this template** di repo ini (atau salin filenya), lalu beri nama repositori barunya **persis sama dengan username GitHub-mu**, misalnya `octocat/octocat`. GitHub menampilkan `README.md` repo itu di halaman profilmu. Repo harus publik.

**2. Edit `profile.yaml`.**
Isi `github_username`, `name`, serta baris `info`, `contact`, dan `links`. Setiap bidang dijelaskan di dalam berkasnya, dan [`examples/ranupane/profile.yaml`](examples/ranupane/profile.yaml) adalah contoh lengkap. Selama `github_username` masih `octocat`, workflow melewati dirinya sendiri, jadi salinan baru tidak pernah menerbitkan data contoh.

**3. (Opsional) Tambahkan potret ASCII.**
Tanpa potret, kartu menampilkan siluet netral. Lihat [Membuat potret ASCII](#membuat-potret-ascii).

**4. Izinkan workflow melakukan push.**
Repositori **Settings → Actions → General → Workflow permissions** → pilih **Read and write permissions** → Save.

**5. (Opsional) Hitung repositori privat.**
Angka publik langsung jalan. Untuk menyertakan repositori privat, buat [personal access token klasik](https://github.com/settings/tokens/new) dengan scope `repo` dan `read:user`, lalu simpan sebagai secret repositori bernama `ACCESS_TOKEN` (**Settings → Secrets and variables → Actions → New repository secret**). Tanpa itu, statistik hanya menghitung repositori publik.

**6. Jalankan workflow sekali.**
Buka tab **Actions**, jalankan **Update profile card**, lalu **Pacman contribution graph**, dengan **Run workflow**. Setelah itu keduanya jalan sendiri tiap hari. Hasilnya ada di `output/`, lengkap dengan snippet siap pakai di `output/snippet.md`.

**7. Tempel snippet ke README.**
Ganti isi `README.md` dengan isi `output/snippet.md`. Snippet itu menampilkan kartu, tombol tautan, dan grafik Pac-Man. Commit, lalu buka halaman profilmu. Gambar Pac-Man tetap rusak sampai workflow-nya jalan sekali.

## Membuat potret ASCII

Kolom kiri kartu berisi potret ASCII maksimal **50 kolom × 37 baris**. Ada empat cara, dari yang paling mudah.

**A. Tidak melakukan apa-apa.** Siluet netral dipakai.

**B. Ubah foto otomatis.** Paling bagus untuk foto dengan latar polos dan rata (tembok, kain, kertas studio) dengan wajah di bagian atas gambar.

```sh
pip install -r requirements-ascii.txt       # OpenCV + NumPy, hanya untuk langkah ini
python -m profilecard ascii foto.jpg --auto > ascii.txt
```

`--auto` membaca warna latar dari tepi foto, membuangnya, lalu memotong ke kepala dan bahumu. Perintah ini mencetak hasilnya, jadi sekaligus menjadi pratinjau: jalankan, lihat di terminal, ubah opsi, jalankan lagi.

**C. Setel manual.** Kalau hasil otomatis kurang pas:

| Opsi | Pakai kalau |
|---|---|
| `--crop x0,y0,x1,y1` | Bingkainya salah. Kotak piksel pada foto yang disesuaikan ke kanvas 400×400; lebar kotak sekitar 0,7 kali tingginya. |
| `--mask-hue 95,135` | Latar berwarna satu warna kuat. Rentang hue OpenCV 0–179 (biru sekitar 95–135, hijau sekitar 40–80). Hanya membuang warna itu. |
| `--invert` | Cahaya dari belakang, atau subjek terang di latar gelap. |
| `--auto --crop ...` | Tetap pakai pembuangan latar otomatis, tapi tentukan sendiri bingkainya. |

Tips fotonya: bentuk apa pun boleh (foto disesuaikan, tidak pernah digepengkan), tapi pilih latar polos dan cahaya bagus di wajah. Kacamata dan jenggot terbaca baik; detail rambut halus tidak, karena gambarnya hanya 50×37 karakter. Dengan `requirements-ascii.txt` (OpenCV 4), `--auto` juga mendeteksi wajahmu untuk menentukan bingkai; dengan OpenCV 5 ia memperkirakan kepala dari siluet, sedikit kurang presisi. Latar dinilai dari rona warna, bukan terangnya, jadi dinding yang memudar jadi bayangan terbuang bersih sementara kulit, pakaian, dan rambut gelap tetap. Latar yang ramai atau beraneka warna adalah kasus tersulit: potong lebih ketat dengan `--crop`, atau rapikan hasilnya dengan tangan (cara D).

**D. Edit manual.** `ascii.txt` adalah teks biasa. Buka di editor mana pun untuk merapikan karakter nyasar, atau tulis seni ASCII atau logo sendiri. Jaga tiap baris maksimal 52 karakter; berkas yang lebih lebar ditolak dengan pesan yang jelas. Lebih dari 37 baris boleh: kartu akan memanjang.

Lalu beri tahu config lokasinya dan commit:

```yaml
ascii: ascii.txt
```

Workflow tidak menjalankan OpenCV. Ia hanya membaca `ascii.txt` yang sudah jadi, jadi fotonya tidak perlu ada di repositori. Simpan foto di luar repo kalau kamu mau.

## Konfigurasi

Semuanya ada di [`profile.yaml`](profile.yaml).

| Bidang | Fungsi |
|---|---|
| `github_username` | Statistik milik siapa. Kosongkan di Actions untuk memakai pemilik repositori. |
| `name` | Judul kartu (huruf besar). Default: username. |
| `birthday` | Mengisi baris `{uptime}` ("22 years, 4 months, 16 days"). Hapus untuk menyembunyikan baris itu. |
| `ascii` | Lokasi potretmu. Hilangkan untuk siluet. |
| `info` | Baris di bawah judul: `- Label: nilai`. Titik pada label mewarnai kedua bagian (`Languages.Real`). `""` adalah baris kosong. |
| `contact` | Blok kedua berjudul "Contact", format sama. Hapus untuk menyembunyikan. |
| `links` | 1 sampai 5 tombol pixel-art. `type`: `website`, `x`, atau `email`; `label` opsional. |
| `output_dir` | Lokasi hasil. Default `output`. |
| `pacman` | `true` (default) atau `false`. Dengan `false`, snippet tidak memuat grafik Pac-Man dan workflow pacman tidak melakukan apa-apa, jadi tidak ada action pihak ketiga yang berjalan. Lihat [Privasi](#privasi-dan-kode-pihak-ketiga). |
| `pacman_label` | Teks sebelum penghitung Pac-Man. Default `Contributions`. |
| `colors` | Ganti warna per tema. Kunci: `bg fg key value add dele cc` (dan `flash` untuk penghitung Pac-Man). |

Ubah jam pembaruan lewat baris `cron` di `.github/workflows/build.yaml` dan `pacman.yaml` (waktu UTC).

### Token

| Variabel | Fungsi |
|---|---|
| `GITHUB_TOKEN` | Disediakan Actions. Cukup untuk semua angka publik. |
| `ACCESS_TOKEN` | Secret opsional. Menambahkan repositori privat ke hitungan. |

Token hanya dibaca dari environment dan tidak pernah ditulis ke berkas. Cache jumlah baris di `cache/` memakai hash nama repositori, jadi nama repositori privat tidak bocor.

## Jalankan lokal

```sh
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

python -m profilecard build                       # render kartu, tombol, snippet (tanpa jaringan)
GITHUB_TOKEN=... python -m profilecard update     # ditambah statistik GitHub
python -m unittest discover tests                 # tes offline
```

| Perintah | Fungsi |
|---|---|
| `build` | Membuat `output/neofetch`, `output/links`, dan `output/snippet.md`. Statistik yang ada dipertahankan. |
| `stats` | Mengisi angka GitHub di kartu dari API. |
| `update` | `build`, lalu `stats`. |
| `pacman` | Menambah penghitung kontribusi ke `output/pacman/{dark,light}.svg`. |
| `ascii GAMBAR` | Mengubah potret menjadi ASCII art (lihat di atas). |
| `ci-info` | Mencetak `username=` dan `pacman=` untuk dibaca workflow. |

Taruh `-c lokasi/profile.yaml` sebelum perintah untuk memakai konfigurasi lain. Untuk uji lokal cepat: `GITHUB_TOKEN=$(gh auth token) python -m profilecard update`.

## Pemecahan masalah

| Gejala | Solusi |
|---|---|
| Workflow gagal di langkah **Commit** dengan `403` | Langkah 4: beri workflow **Read and write permissions**. |
| Workflow jalan tapi tidak melakukan apa-apa | `github_username` masih `octocat`. Ganti. |
| Statistik `0` atau repo privat tidak terhitung | Tambahkan secret `ACCESS_TOKEN` (langkah 5), lalu jalankan workflow lagi. |
| Gambar Pac-Man rusak | Jalankan **Pacman contribution graph** sekali, atau set `pacman: false` lalu pakai snippet lagi. |
| `error: GitHub rejected the token (401)` | `ACCESS_TOKEN` kedaluwarsa atau salah. Buat ulang, atau hapus secret agar kembali ke angka publik. |
| `error: ... failed after 3 attempts` | GitHub atau jaringan sedang bermasalah, atau repositori terlalu besar untuk dihitung. Jalankan ulang workflow. |
| `Pets: no` tampil `no` | Memang begitu: nilai disimpan persis seperti yang kamu tulis. |
| Kartu tidak berubah setelah dijalankan | GitHub menyimpan cache gambar beberapa menit. Refresh keras, atau tunggu. |
| `config error: ... columns wide` | `ascii.txt` lebih lebar dari 52 karakter. Buat ulang atau pangkas barisnya. |
| `The ascii command needs OpenCV` | `pip install -r requirements-ascii.txt`. |

## Privasi dan kode pihak ketiga

Sebagian besar proyek ini adalah Python biasa yang berjalan di repositorimu. Satu bagian bukan:

- **Animasi Pac-Man** digambar oleh [abozanona/pacman-contribution-graph](https://github.com/abozanona/pacman-contribution-graph), action buatan orang lain. Kodenya (versi 5.5.2, ditinjau saat kit ini dibuat) mengirim **username GitHub**-mu ke server penulisnya setiap kali jalan, dan **skor serta jumlah langkah** Pac-Man ke endpoint papan peringkat. Token-mu tidak dikirim ke sana. Hasil bundel `dist/` dan pustaka npm di dalamnya tidak ditinjau. Repositori itu **tidak punya berkas lisensi**, jadi ia hanya dipakai sebagai action dan tidak ada yang disalin.
- **Yang dilakukan kit ini:** action di-pin ke satu commit yang sudah ditinjau, bukan `@main`; ia berjalan di job dengan token **baca-saja** tanpa kredensial git tersimpan; job yang boleh menulis ke repositorimu tidak pernah menjalankan kode pihak ketiga; dan fitur ini opsional (`pacman: false`).
- **Yang sebaiknya kamu lakukan:** jangan berikan `ACCESS_TOKEN` ke job Pac-Man (template sudah begitu). Kalau ingin kontribusi privat masuk grafik, kamu harus memberikan tokenmu ke action itu. Itu menyerahkan kredensial, jadi lakukan hanya jika kamu menerimanya. Untuk memperbarui pin, baca kode barunya dulu, baru ganti SHA di `.github/workflows/pacman.yaml`.
- **Kartu dan tombol** tidak memerlukan semua ini. Keduanya hanya memanggil API GitHub, dengan tokenmu, dari kode di repositori ini.

## Kredit dan lisensi

Gaya tombol terinspirasi dari profil [ignaciochiappero](https://github.com/ignaciochiappero). Animasi Pac-Man dibuat oleh [abozanona/pacman-contribution-graph](https://github.com/abozanona/pacman-contribution-graph), yang dipanggil workflow sebagai action. Ia tidak punya berkas lisensi dan mengirim sebagian data ke penulisnya (lihat [Privasi](#privasi-dan-kode-pihak-ketiga)).

Lisensi proyek ini: [MIT](LICENSE).
