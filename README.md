# 🇹🇷 ZCode Desktop Türkçe Dil Paketi & Yerelleştirme Altyapısı
### (Community Turkish Localization & Engineering Infrastructure for ZCode Desktop)

<div align="center">

[![GitHub License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Tested On](https://img.shields.io/badge/ZCode%20Version-v3.16.3%2B-green.svg)](https://zcode.z.ai)
[![Keys Translated](https://img.shields.io/badge/Translated%20Keys-7%2C328-orange.svg)](tr_dictionary_zcode.json)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Cross--Platform-lightgrey.svg)](#-kurulum-installation)
[![Maintenance Commitment](https://img.shields.io/badge/Maintenance-Day--0%20SLA-blue.svg)](#-note-to-official-zcode-developers-zai-org)
[![GitHub stars](https://img.shields.io/github/stars/foztrk/zcode-turkish-localization?style=social)](https://github.com/foztrk/zcode-turkish-localization)

[📥 **Tek Tıkla İndir (.exe)**](https://github.com/foztrk/zcode-turkish-localization/releases/latest) • 
[⭐ **Yıldız Ver (Star)**](https://github.com/foztrk/zcode-turkish-localization) • 
[💬 **Geri Bildirim / Hata Bildir**](https://github.com/foztrk/zcode-turkish-localization/issues) • 
[🏛️ **Resmi Upstream PR Dalı**](https://github.com/foztrk/ZCode/tree/feat/add-turkish-language-support)

</div>

---

> [!TIP]
> 🌟 **Projeyi beğendiyseniz sağ üst köşeden bir ⭐ Yıldız (Star) bırakarak bize destek olabilirsiniz!**  
> GitHub yıldızlarınız, ZCode resmi ekibinin Türkçe dilini doğrudan çekirdeğe (native) entegre etmesini hızlandırmak ve projenin görünürlüğünü artırmak için en büyük katkıdır.

ZCode Desktop yapay zeka destekli IDE ve kodlama asistanı için geliştirilmiş **en kapsamlı, %100 eksiksiz ve bağımsız Türkçe yerelleştirme projesidir**.

Bu proje; arayüz metinlerinden eklenti mağazasına, uzak bağlantılardan (Docker, SSH, WSL), komutlardan ve yeteneklerden (skills) fiyatlandırma webview'larına kadar ZCode'un tüm katmanlarını Türkçeleştirir. Ayrıca sol alttaki profil menüsüne ve Genel Ayarlar sayfasına kalıcı **"Türkçe"** dil seçeneğini doğrudan entegre eder.

---

## 📢 Note to Official ZCode Developers (@zai-org)

> **Dear ZCode Team & Contributors at [@zai-org](https://github.com/zai-org) / Zhipu AI,**

First of all, congratulations on creating **ZCode**! It is an outstanding agentic IDE and coding assistant, and our Turkish developer community truly appreciates the hard work your team is putting into this product.

### Upstream Integration Ready (Parity with v3.16.3)
Following guidance from the Z.ai Developer Support team, we have prepared the complete native Turkish localization branch in our fork:
- 🔗 **Branch:** [foztrk/ZCode@feat/add-turkish-language-support](https://github.com/foztrk/ZCode/tree/feat/add-turkish-language-support)
- 🔗 **Direct Commit:** [7f14fea](https://github.com/foztrk/ZCode/commit/7f14fea0)
- 🔗 **Official Feedback Issue:** [zai-org/feedback#1047](https://github.com/zai-org/feedback/issues/1047#issuecomment-6291121632)

### Changes Prepared:
1. `packages/ui/src/i18n/locales/tr-TR.ts`: Complete Turkish locale dictionary with **7,328 keys** (100% key parity).
2. `packages/shared/src/protocol.ts`: Extended `Locale` union type to `"zh-CN" | "en-US" | "tr-TR"`.
3. `packages/ui/src/i18n/IntlProvider.tsx`: Registered `tr-TR` translations in `MESSAGES`.
4. `packages/ui/src/i18n/LocaleSwitcher.tsx` & `WorkspaceSidebarFooter.tsx`: Added Turkish ("Tr" / "Türkçe") to interactive language pickers.

---

## 🌟 Neler İçerir? (Özellikler)

1. **Tam Kapsamlı Arayüz (7.328 Anahtar):**
   - React-Intl dil sağlayıcısı (`IntlProvider`) üzerinden **7.328 anahtarın tamamı** Türkçe yazılım ve geliştirici terminolojisine uygun olarak yerelleştirildi.
   - v3.16.3 ile gelen yeni kimlik doğrulama, uzak bağlantı platform/dizin hata mesajları, OAuth giriş bağlantısı kopyalama ve MID araçları.
   - Uzak Bağlantılar (SSH, Docker, WSL, ZCode Server) altyapısı, Konteyner Seçimi, Özel Anahtar yönetimi ve kaynak indirme sihirbazları.
   - Sol alttaki profil menüsünde ve Genel Ayarlar sayfasında yerleşik **"Türkçe"** dil seçeneği.
   - Electron yerel masaüstü menüleri (Dosya, Düzen, Görünüm, Pencere, Yardım).
   - Güncelleyici diyalogları ve Türkçe yerel tarih/sayı biçimlendirmeleri.
2. **Resmi Eklenti Mağazası ve Claude Code Eklentileri (330+ Paket):**
   - Resmi ZCode eklentilerinin (Plugin Creator, PDF, Documents, Presentations, Spreadsheets, Finans, Güvenlik vb.) başlık ve Türkçe açıklamaları.
   - Claude Code Mağazasındaki 291 eklentinin tamamının Türkçe açıklamaları.
3. **Ajan Becerileri (Skills) ve Komutlar (Slash Commands):**
   - Yeni `visualize` (Görselleştirme) becerisi dahil tüm ajan yetenekleri ve `/komut` açıklamaları, argüman ipuçları ve kategori başlıkları.
4. **Planı Yükselt & Webview Arayüzü:**
   - Dinamik DOM gözlemcisi ile Bireysel ve Ekip planları, kredi kotaları, indirimler ve faturalandırma metinleri.
5. **Kalıcı ve Güvenli:**
   - Orijinal `app.asar.orig.v3163` fabrika yedeğini saklar; istendiğinde tek tıkla orijinal fabrika ayarlarına geri döndürür.

---

## 🚀 Kurulum (Installation)

### Yöntem 1: Tek Tıkla Kurulum (Önerilen)
1. [Releases](https://github.com/foztrk/zcode-turkish-localization/releases/latest) sayfasından **`ZCode_Tek_Tik_Yama.exe`** dosyasını indirin.
2. ZCode uygulamasını tamamen kapatın.
3. İndirdiğiniz `.exe` dosyasını çalıştırın ve ekrandaki talimatları izleyin.
4. Yama saniyeler içinde uygulanır ve ZCode Türkçe olarak kullanıma hazır hale gelir!

### Yöntem 2: Python ile Manuel Kurulum
```bash
git clone https://github.com/foztrk/zcode-turkish-localization.git
cd zcode-turkish-localization
python build_and_test_asar.py
```
Oluşan `app.asar.patched` dosyasını `C:\Program Files\ZCode\resources\app.asar` olarak kopyalayın.

---

## 👤 Geliştirici & Katkıda Bulunanlar

- **Faruk Öztürk** ([@foztrk](https://github.com/foztrk)) — Proje Yürütücüsü & Çevirmen

---

## 📄 Lisans
Bu proje [MIT Lisansı](LICENSE) altında lisanslanmıştır. ZCode, Z.ai / Zhipu AI'ın tescilli ticari markasıdır.
