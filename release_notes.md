# 🇹🇷 ZCode Desktop Türkçe Dil Paketi v1.2.0 (v3.17.1+ Otonom Sürüm)

ZCode Desktop için geliştirilmiş en kapsamlı, bağımsız ve güncel Türkçe yerelleştirme sürümüdür. ZCode **v3.17.1** ile tam uyumludur.

---

### 🚀 Neler Yeni ve Öne Çıkanlar (v1.2.0)

1. **Model ve Sağlayıcı Hata Mesajları Enjeksiyonu (`ZBt` Kancası):**
   - Sohbet bildirim çubuğunda sağlayıcıdan (Zhipu/GLM, Claude, OpenAI) gelen dinamik hata mesajları yakalanarak kökten Türkçeleştirildi:
     - *"Model output was blocked by the provider's content safety filter."* ➔ *"Model çıktısı, sağlayıcının içerik güvenliği filtresi tarafından engellendi."*
     - *"Prompt was blocked by the provider's content safety filter."* ➔ *"İstem (prompt), sağlayıcının içerik güvenliği filtresi tarafından engellendi."*
     - Kota aşımı, istek sınırı (rate limit), maksimum bağlam (token) sınırı ve ağ zaman aşımı mesajları otomatik Türkçeleştirildi.

2. **ZCode Sites Komutları ve Parametre İpuçları:**
   - `/site-badge`, `/site-deploy`, `/site-logs`, `/site-offline`, `/site-online`, `/site-status`, `/site-usage` komut açıklamaları ve parametre ipuçları tamamen Türkçe olarak arayüze entegre edildi.

3. **Otomasyon Şablonları & Takvim/Haftalık Formatlar:**
   - "Sabah Geliştirici Özeti", "Risk Taraması", "Sürüm Özeti", "Belge Senkronizasyon Kontrolü" şablon açıklamaları Türkçeleştirildi.
   - Haftalık ve günlük zamanlanmış görev bildirimlerindeki takvim formatı düzenlendi ("Her hafta Cuma saat 16:00" gibi temiz formatlama).

4. **Kupon, Bilet ve Kampanya Animasyonları:**
   - Bilet üzerindeki `Valid until` metni `Geçerlilik tarihi:`, `Replay` butonu `Animasyonu Tekrar Oynat` olarak uyarlandı.

5. **510+ Resmi ve Topluluk Eklentisi Açıklaması:**
   - Resmi ZCode eklentilerinin yanı sıra Topluluk Mağazasındaki (Excalidraw, PhotoCraft, VectorCraft, PdfCraft, DesignCraft, WordCraft, GridCraft, CADCraft vb.) tüm eklentilerin başlık ve açıklamaları Türkçeleştirildi.

6. **7.400+ Arayüz Anahtarı:**
   - ZCode'un v3.17.1 ile gelen tüm yeni çekirdek metinleri, ayarları ve diyalogları eksiksiz yerelleştirildi.

---

### 📦 Kurulum (Tek Tıkla)

1. Aşağıdaki **`ZCode_Tek_Tik_Yama.exe`** dosyasını indirin.
2. ZCode uygulamasını tamamen kapatın.
3. İndirdiğiniz `.exe` dosyasını çalıştırın.
4. Saniyeler içinde yama uygulanır ve ZCode %100 Türkçe olarak açılır!

> **Geri Alma (Uninstall):** Yama programı orijinal `app.asar` yedeğinizi otomatik saklar; dilediğinizde tek tıkla fabrika ayarlarına geri dönebilirsiniz.

---
**Geliştirici:** Faruk Öztürk ([@foztrk](https://github.com/foztrk))
