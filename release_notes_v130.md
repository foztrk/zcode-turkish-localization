# 🚀 ZCode Türkçe Dil Paketi v1.3.0 - Resmi ZCode v3.18.0 Desteği

Bu sürüm, **ZCode Desktop v3.18.0** resmi güncellemesi ile tam uyumluluk sağlamaktadır. Toplam **8.355 arayüz anahtarı** ve tüm yerleşik eklentiler eksiksiz olarak Türkçeleştirilmiştir.

---

## 🌟 Öne Çıkan Yenilikler ve İyileştirmeler (v3.18.0 Parity)

1. **8.355 Anahtara Genişletilmiş Çeviri Desteği (559 Yeni Anahtar):**
   - **Git Worktree Yönetimi:** Yeni paralel çalışma alanları (`git.managedWorktree.*`) arayüzü, diyalogları ve hata uyarıları Türkçeleştirildi.
   - **Yerleşik Tarayıcı Tasarım Paneli (`browser.design.*`):** Sayfa içi bileşenleri inceleme, stil düzenleme (tipografi, hizalama, dolgu, renkler) ve dışa aktarma arayüzü tam Türkçe yapıldı.
   - **Uzantı Oturum İzinleri (`extensions.*`):** Eklenti uzantı kodlarının arka planda çalışması, oturum okuma/yazma izinleri ve denetim günlüğü diyalogları yerelleştirildi.
   - **Sesli Giriş ve Ses Tanıma (`voiceInput.*`):** Ses tanıma durumu, mikrofon izinleri ve platform hata mesajları (Windows/macOS/Linux) Türkçeleştirildi.
   - **Arşiv Yönetimi (`archives.*`):** Oturumları kalıcı silme ve bağımlılık kontrol mekanizması tam Türkçeleştirildi.
   - **Kodlama Planı & Token Sıfırlama (`codingPlan.*`):** Kota yenileme, 5 saatlik ve haftalık kullanım sıfırlama arayüzleri yerelleştirildi.

2. **İçerik Güvenliği Filtresi ve Model Hata Mesajları:**
   - Model sağlayıcılarının içerik güvenliği filtresi engelleme mesajları (`Model output was blocked by the provider's content safety filter`) hem JS yürütme katmanında hem de DOM gözlemcisinde Türkçe olarak yamalandı.

3. **Yeni Çoklu Dil Altyapısı Entegrasyonu:**
   - ZCode'un v3.18.0 ile getirdiği genişletilmiş dil haritası yapısına (`ja-JP`, `ru-RU`, `ko-KR`) tam uyum sağlandı.
   - Değişen dinamik modül hash'leri (`IntlProvider-C0vyPcb8.js`, `styles-BhvI6_DD.js`, `chunk-GMTOLIE6.js`) ve güncellenen fonksiyon kancaları (`DYt`, `n8`, `Kk`, `qk`, `Jk`) eksiksiz bağlandı.

4. **Yenilenen Tek Tık Yama (`ZCode_Tek_Tik_Yama.exe`):**
   - 8.355 anahtarlık gömülü sözlük ve tüm eklenti verileriyle bağımsız taşınabilir tek tık yama (.exe) yeniden derlendi.

---

## 📥 Kurulum

1. ZCode'u kapatın.
2. Aşağıdaki varlıklardan **`ZCode_Tek_Tik_Yama.exe`** dosyasını indirin ve yönetici olarak çalıştırın.
3. Birkaç saniye içinde yama otomatik uygulanacak ve ZCode Türkçe olarak başlayacaktır.
