# 🇹🇷 ZCode Desktop Türkçe Dil Paketi & Yerelleştirme Altyapısı
### (Community Turkish Localization & Engineering Infrastructure for ZCode Desktop)

<div align="center">

[![GitHub License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Tested On](https://img.shields.io/badge/ZCode%20Version-v3.18.2%2B-green.svg)](https://zcode.z.ai)
[![Keys Translated](https://img.shields.io/badge/Translated%20Keys-8%2C365-orange.svg)](tr_dictionary_zcode.json)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Cross--Platform-lightgrey.svg)](#-kurulum-installation)
[![Maintenance Commitment](https://img.shields.io/badge/Maintenance-Day--0%20SLA-blue.svg)](#-note-regarding-official-upstream-zai-org)
[![GitHub stars](https://img.shields.io/github/stars/foztrk/zcode-turkish-localization?style=social)](https://github.com/foztrk/zcode-turkish-localization)

[📥 **Tek Tıkla İndir (.exe)**](https://github.com/foztrk/zcode-turkish-localization/releases/latest) • 
[⭐ **Yıldız Ver (Star)**](https://github.com/foztrk/zcode-turkish-localization) • 
[💬 **Geri Bildirim / Hata Bildir**](https://github.com/foztrk/zcode-turkish-localization/issues) • 
[🏛️ **Resmi Upstream PR Dalı**](https://github.com/foztrk/ZCode/tree/feat/add-turkish-language-support)

</div>

---

> [!TIP]
> 🌟 **Projeyi beğendiyseniz sağ üst köşeden bir ⭐ Yıldız (Star) bırakarak bize destek olabilirsiniz!**  
> GitHub yıldızlarınız, bağımsız topluluk projesinin görünürlüğünü artırmak için en büyük katkıdır.

ZCode Desktop yapay zeka destekli IDE ve kodlama asistanı için geliştirilmiş **en kapsamlı, %100 eksiksiz ve bağımsız Türkçe yerelleştirme projesidir**.

Bu proje; arayüz metinlerinden model/sağlayıcı hata bildirimlerine, eklenti mağazasından (topluluk ve resmi eklentiler), uzak bağlantılardan (Docker, SSH, WSL), ZCode Sites komutlarından ve otomasyon görev şablonlarına kadar ZCode'un tüm katmanlarını Türkçeleştirir. Ayrıca sol alttaki profil menüsüne ve Genel Ayarlar sayfasına kalıcı **"Türkçe"** dil seçeneğini doğrudan entegre eder.

---

## 📢 Note Regarding Official Upstream (@zai-org)

> **To the Community & ZCode Team at [@zai-org](https://github.com/zai-org) / Zhipu AI:**

As of November 2026, official issue [#1047](https://github.com/zai-org/feedback/issues/1047) was tracked and merged into primary issue [#708](https://github.com/zai-org/feedback/issues/708). Consequently, **this project serves as the definitive, fully autonomous, and officially maintained community localization engine for all Turkish-speaking ZCode developers.**

Our reverse-engineered AST and ASAR injection engine guarantees zero downtime and instant day-0 Turkish support with every new ZCode release.

---

## 🌟 Neler İçerir? (Özellikler)

1. **Model ve Sağlayıcı Hata Mesajları Enjeksiyonu (`ZBt` / `bVt` Kancası):**
   - Sohbet panelinde model sağlayıcısından gelen İngilizce hata mesajları (`"Model output was blocked by the provider's content safety filter."`, rate limit, quota, context limit vb.) anında yakalanıp Türkçeleştirilir.
2. **Tam Kapsamlı Arayüz (8.365 Anahtar):**
   - React-Intl dil sağlayıcısı (`IntlProvider`) üzerinden **8.365 anahtarın tamamı** Türkçe yazılım ve geliştirici terminolojisine uygun olarak yerelleştirildi.
   - **v3.18.2 Uyumluluğu:** 10 yeni i18n anahtarı (Yazı tipi gri tonlama düzgünleştirme ayarı, sesli giriş mikrofon yetkilendirme diyalogları ve sistem bildirimleri) eksiksiz Türkçeleştirildi.
   - v3.18.2 ile değişen dinamik modül hash'leri (`IntlProvider-FwXbxV-p.js`, `styles-a4AckxCl.js`, `chunk-N4BDK3A6.js`) ve güncellenen fonksiyon kancaları (`MYt`, `r8`, `wit`, `qk`, `Jk`, `Yk`) tam entegre edildi.
   - **v3.18.0 Uyumluluğu:** 559 yeni i18n anahtarı (Git Worktree yönetimi, Yerleşik Tasarım Tarayıcısı, Uzantı Oturum İzinleri, Sesli Giriş ve Hata Güvenlik Filtreleri) eksiksiz Türkçeleştirildi.
   - v3.17.2 ile eklenen yeni MCP hata çözüm önerileri (`settings.mcp.failureAdvice.*`) ve hata ayrıntıları eksiksiz çevrildi.
   - Sol alttaki profil menüsünde ve Genel Ayarlar sayfasında yerleşik **"Türkçe"** dil seçeneği.
   - Electron yerel masaüstü menüleri (Dosya, Düzen, Görünüm, Pencere, Yardım).
   - Güncelleyici diyalogları, kupon/bilet geçerlilik metinleri ve Türkçe yerel tarih/sayı biçimlendirmeleri.
3. **Resmi ve Topluluk Eklenti Mağazası (510+ Paket):**
   - Resmi ZCode eklentilerinin (PDF, Sunum, Tablo, Belge, Görselleştirme, Android/iOS Simülatör, Browser Use) başlık ve açıklamaları.
   - Topluluk Mağazasındaki tüm eklentilerin (Excalidraw, PhotoCraft, VectorCraft, PdfCraft, DesignCraft, WordCraft, GridCraft, CADCraft vb.) Türkçe açıklamaları.
4. **ZCode Sites Komutları & Otomasyon Görev Şablonları:**
   - `/site-badge`, `/site-deploy`, `/site-logs`, `/site-offline`, `/site-online`, `/site-status`, `/site-usage` komut açıklamaları ve argüman ipuçları.
   - "Sabah Geliştirici Özeti", "Risk Taraması", "Sürüm Özeti", "Belge Senkronizasyon Kontrolü" otomasyon şablonları ve düzgün haftalık takvim formatı.
5. **Kalıcı ve Güvenli:**
   - Orijinal `app.asar` fabrika yedeğini saklar; istendiğinde tek tıkla orijinal fabrika ayarlarına geri döndürür.

---

## 🚀 Kurulum (Installation)

### Yöntem 1: Tek Tıkla Kurulum (Önerilen)
1. [Releases](https://github.com/foztrk/zcode-turkish-localization/releases/latest) sayfasından **`ZCode_Tek_Tik_Yama.exe`** dosyasını indirin.
2. ZCode uygulamasını tamamen kapatın.
3. İndirdiğiniz `.exe` dosyasını çalıştırın.
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
