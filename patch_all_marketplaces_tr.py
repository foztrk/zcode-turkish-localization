# -*- coding: utf-8 -*-
"""
patch_all_marketplaces_tr.py
ZCode ve Claude eklenti mağazalarındaki tüm resmi marketplace.json ve cdn-marketplace.json
dosyalarını %100 eksiksiz Türkçe yapar.
"""

import os
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

# 68 Resmi ZCode Eklentisi Türkçe Çeviri Veritabanı
ZCODE_OFFICIAL_PLUGINS_TR = {
    "accounting-and-reporting": {
        "title": "Muhasebe ve Raporlama",
        "displayName": "Muhasebe ve Raporlama",
        "description": "Şirketin kendi defterlerinden muhasebe kapanışı ve yasal raporlama: yevmiye kayıtları, mizanlar, mutabakat ve mali tablo açıklamaları."
    },
    "assess-credit": {
        "title": "Sabit Getiri ve Kredi Araştırması",
        "displayName": "Sabit Getiri ve Kredi Araştırması",
        "description": "Sabit getirili menkul kıymetler ve kredi araştırması: değerleme ve süre/dışbükeylik ile tahvil profilleri, kredi marjı karşılaştırmaları ve borçlanma tavanı tahminleri."
    },
    "find-clients": {
        "title": "Kurumsal Müşteri Kazanımı",
        "displayName": "Kurumsal Müşteri Kazanımı",
        "description": "Kurumsal bankacılık müşteri kazanımı: bölgeye, sektöre ve gelire göre potansiyel müşteri taraması, çapraz satış haritalaması, ilişki istihbaratı ve tanıtım özetleri."
    },
    "model-deals": {
        "title": "İşlem Yapılandırma ve Modelleme",
        "displayName": "İşlem Yapılandırma ve Modelleme",
        "description": "İşlem yapılandırma ve modelleme: hisse sulanma analizi, fon kaynakları ve kullanım tabloları, LBO getirileri, duyarlılık matrisleri ve birleşme analizleri."
    },
    "pick-funds": {
        "title": "Fon ve Yönetici Araştırması",
        "displayName": "Fon ve Yönetici Araştırması",
        "description": "Fon ve portföy yöneticisi araştırması: çok kriterli fon taraması, fon ve yönetici profil özetleri, emsallere göre getiri analizi ve yatırım komitesi raporları."
    },
    "read-macro": {
        "title": "Makro ve Strateji",
        "displayName": "Makro ve Strateji",
        "description": "Yukarıdan aşağıya makro ve strateji çalışmaları: büyüme/enflasyon/politika makro gösterge panelleri, varlıklar arası ısı haritaları ve varlık dağılım önerileri."
    },
    "run-fpa": {
        "title": "Kurumsal Finans ve FP&A",
        "displayName": "Kurumsal Finans ve FP&A",
        "description": "Kurumsal finansman ve FP&A: yönetim raporlaması, varyans analizi, hareketli tahminler, operasyonel gider sürücü modellemesi ve Yönetim Kurulu sunumları."
    },
    "vet-companies": {
        "title": "Şirket İncelemesi ve Due Diligence",
        "displayName": "Şirket İncelemesi ve Due Diligence",
        "description": "Karşı taraf ve şirket detaylı incelemesi (DD): yapılandırılmış DD raporları, ortaklık grafiği takibi, uyumluluk uyarıları ve tedarikçi risk puanlaması."
    },
    "watch-positions": {
        "title": "Pozisyon İzleme",
        "displayName": "Pozisyon İzleme",
        "description": "İzleme listesi ve portföy takibi: seans sonrası özetler, pozisyon olayları ve bildirim uyarıları, hedef fiyat ve derecelendirme değişiklik takibi."
    },
    "write-research": {
        "title": "Hisse Senedi Araştırması",
        "displayName": "Hisse Senedi Araştırması",
        "description": "Uçtan uca yatırım araştırması raporları, sektör analizleri, kazanç güncellemeleri, değerleme modelleri (İNA/DCF, çarpanlar) ve teze dayalı analiz notları."
    },
    "blender": {
        "title": "Blender",
        "displayName": "Blender",
        "description": "Resmi Blender CLI ile 3B modelleme yapın, ağları (mesh) düzenleyin, malzemeleri ayarlayın, Cycles/EEVEE sahnelerini işleyin ve Python ile otomatikleştirin."
    },
    "godot": {
        "title": "Godot Engine",
        "displayName": "Godot Engine",
        "description": "Resmi Godot CLI ile oyun geliştirin ve her yinelemeyi doğrudan sohbet içinde görüntüleyin: 2D ve 3D sahneler oluşturun, GDScript yazın."
    },
    "hyper3d-rodin": {
        "title": "Hyper3D Rodin",
        "displayName": "Hyper3D Rodin",
        "description": "Metin veya referans görselleri 3B modellere dönüştürün, modelleri animasyon veya fizik için alt nesnelere ayırın, PBR dokular ekleyin."
    },
    "tripo-3d": {
        "title": "Tripo 3D",
        "displayName": "Tripo 3D",
        "description": "Metin veya görsellerden dokulu 3B modeller oluşturun, kemik sistemi (rigging) ve animasyon ekleyin, GLB/FBX formatında dışa aktarın."
    },
    "unity": {
        "title": "Unity",
        "displayName": "Unity",
        "description": "Unity'de oyun sahneleri oluşturun, nesneleri ve varlıkları düzenleyin, C# betikleri yazın, oyun modunu test edin ve projeleri derleyin."
    },
    "unreal-engine": {
        "title": "Unreal Engine",
        "displayName": "Unreal Engine",
        "description": "Unreal Engine seviyelerini derleyin ve düzenleyin, sahne aktörlerini ayarlayın ve Unreal Engine CLI yeteneklerini kullanarak varlıklar oluşturun."
    },
    "node-repl-host": {
        "title": "Node REPL Barındırıcısı",
        "displayName": "Node REPL Barındırıcısı",
        "description": "ZCode resmi yetenekleri için paylaşılan node_repl çalışma zamanı barındırıcısı. Doğrudan kullanılmaz."
    },
    "cloudbase-skills": {
        "title": "CloudBase",
        "displayName": "CloudBase",
        "description": "CloudBase geliştirme yetenekleri ve sunucusuz bulut entegrasyonu."
    },
    "mimosa": {
        "title": "Kod Güvenlik Koruması",
        "displayName": "Kod Güvenlik Koruması (Mimosa)",
        "description": "ZCode için yerel güvenlik kalkanı: yazma öncesi kancalar, onay denetimleri ve güvenlik kuralları."
    },
    "github": {
        "title": "GitHub",
        "displayName": "GitHub",
        "description": "GitHub CLI ile commit, PR, issue, sürüm yönetimi ve GitHub Actions iş akışları."
    },
    "video-agent-kit": {
        "title": "Video Agent Kit",
        "displayName": "Video Agent Kit",
        "description": "Otomatik video kurgu araç seti: bulut ses deşifresi ve sentezi, video kare anlama, zaman çizelgesi, önizleme işleme ve TTS."
    },
    "video2code": {
        "title": "Video to Code",
        "displayName": "Video to Code",
        "description": "Yerleşik Browser Use ile WebM kaydeder ve ffmpeg ile MP4/kod prototipine dönüştürür."
    },
    "autoresearch": {
        "title": "AutoResearch",
        "displayName": "AutoResearch",
        "description": "ZCode için otonom deney döngüsü: hedef belirleyin, mekanik yöntem seçin ve sonuçları optimize edin."
    },
    "gitlab": {
        "title": "GitLab",
        "displayName": "GitLab",
        "description": "GitLab CLI ile birleştirme istekleri, CI/CD hatları ve sorun takip iş akışları."
    },
    "alibaba-cloud-cli": {
        "title": "Alibaba Cloud CLI",
        "displayName": "Alibaba Cloud CLI",
        "description": "Alibaba Cloud CLI kimlik doğrulama, profil denetimi ve bulut kaynak yönetimi iş akışları."
    },
    "lark-cli": {
        "title": "Lark CLI",
        "displayName": "Lark CLI",
        "description": "Lark/Feishu belgeler, tablolar, takvim, mesajlaşma ve onay süreçleri için CLI entegrasyonu."
    },
    "tencent-meeting-cli": {
        "title": "Tencent Meeting CLI",
        "displayName": "Tencent Meeting CLI",
        "description": "Tencent Meeting toplantı oluşturma, yönetme ve oda kontrolü için OAuth2 CLI entegrasyonu."
    },
    "dingtalk-cli": {
        "title": "DingTalk CLI",
        "displayName": "DingTalk CLI",
        "description": "DingTalk çalışma alanı, yetkilendirme ve kurumsal mesajlaşma CLI entegrasyonu."
    },
    "wecom-cli": {
        "title": "WeCom CLI",
        "displayName": "WeCom CLI",
        "description": "WeCom mesajlar, belgeler, e-posta, takvim ve toplantılar için kurumsal entegrasyon."
    },
    "hexin": {
        "title": "Tonghuashun (iFinD)",
        "displayName": "Tonghuashun iFinD",
        "description": "RoyalFlush iFinD hisse senedi, endeks, fon ve finansal veri analizi için MCP servisleri."
    },
    "wind": {
        "title": "Wind Financial",
        "displayName": "Wind Finans",
        "description": "Wind hisse senedi, tahvil, fon, endeks ve makroekonomik veriler için MCP servisleri."
    },
    "tianyancha": {
        "title": "Tianyancha",
        "displayName": "Tianyancha",
        "description": "Şirket bilgileri, ortaklık yapısı ve kurumsal risk sorguları için Tianyancha MCP servisi."
    },
    "finance-search": {
        "title": "Finansal Arama",
        "displayName": "Finansal Arama",
        "description": "SEC EDGAR başvuruları, finansal web siteleri ve haber aramaları için birleşik finansal arama MCP servisleri."
    },
    "obsidian": {
        "title": "Obsidian",
        "displayName": "Obsidian",
        "description": "Obsidian not defteri becerileri: Obsidian biçimlendirmesi, bağlantılar, etiketler ve not yönetimi."
    },
    "zcode-mcp-app-dev": {
        "title": "MCP Uygulama Geliştirme",
        "displayName": "MCP Uygulama Geliştirme",
        "description": "Resmi SDK'larla ZCode için MCP Uygulamaları ve uzantıları geliştirin."
    },
    "excalidraw": {
        "title": "Excalidraw",
        "displayName": "Excalidraw",
        "description": "Ajanın diyagram ve çizim oluşturmasını sağlayın; kenar çubuğunda Excalidraw ile düzenleyin ve dışa aktarın."
    },
    "photocraft": {
        "title": "PhotoCraft",
        "displayName": "PhotoCraft",
        "description": "ZCode panelinde görsel düzenleme; çalışma alanı dosyalarını açma, katmanlar ve fotoğraf işleme."
    },
    "vectorcraft": {
        "title": "VectorCraft",
        "displayName": "VectorCraft",
        "description": "ZCode panelinde SVG ve vektörel illüstrasyon düzenleme."
    },
    "pdfcraft": {
        "title": "PdfCraft",
        "displayName": "PdfCraft",
        "description": "ZCode panelinde PDF düzenleme, sayfa yönetimi ve açıklama ekleme."
    },
    "designcraft": {
        "title": "DesignCraft",
        "displayName": "DesignCraft",
        "description": "ZCode panelinde sayfa mizanpajı ve grafik tasarım."
    },
    "wordcraft": {
        "title": "WordCraft",
        "displayName": "WordCraft",
        "description": "ZCode panelinde DOCX kelime işlemci; belgeleri açma, biçimlendirme ve düzenleme."
    },
    "gridcraft": {
        "title": "GridCraft",
        "displayName": "GridCraft",
        "description": "ZCode panelinde XLSX elektronik tablo düzenleme ve veri işleme."
    },
    "deckcraft": {
        "title": "DeckCraft",
        "displayName": "DeckCraft",
        "description": "ZCode panelinde PPTX sunum hazırlama ve slayt tasarımı."
    },
    "cadcraft": {
        "title": "CADCraft",
        "displayName": "CADCraft",
        "description": "ZCode panelinde 2B/3B CAD çizimi ve teknik tasarım."
    },
    "soundcraft": {
        "title": "SoundCraft",
        "displayName": "SoundCraft",
        "description": "ZCode panelinde ses düzenleme, kırpma ve filtreleme."
    },
    "kicad": {
        "title": "KiCad",
        "displayName": "KiCad",
        "description": "KiCad 10 ile sohbet içinden 2 katmanlı devre kartı (PCB) tasarımı."
    },
    "jupyter-notebook": {
        "title": "Jupyter Notebook",
        "displayName": "Jupyter Notebook",
        "description": "Kenar çubuğunda etkileşimli Jupyter Notebook açın; veri analizi ve Python kodlarını birlikte çalıştırın."
    },
    "typst-workbench": {
        "title": "Typst Workbench",
        "displayName": "Typst Workbench",
        "description": "Typst belgelerini gerçek zamanlı önizleyin, hataları görün ve anında PDF olarak dışa aktarın."
    },
    "zotero": {
        "title": "Zotero",
        "displayName": "Zotero",
        "description": "Zotero kitaplığınızı kullanın: akademik makaleleri arayın ve okuyun, alıntılar ve .bib dosyaları oluşturun."
    },
    "anet": {
        "title": "AgentNetwork (anet)",
        "displayName": "AgentNetwork (anet)",
        "description": "A2A protokolüyle yerel ağ geçidi üzerinden diğer yapay zeka ajanlarına görevler atayın."
    },
    "ruic-card": {
        "title": "Holografik Kart Üretici",
        "displayName": "Holografik Kart Üretici",
        "description": "Holografik koleksiyon kartı oluşturucu: katmanlı görsel + Blender + Three.js ile 3B interaktif kartlar."
    },
    "libtv-cli": {
        "title": "LibTV CLI",
        "displayName": "LibTV CLI",
        "description": "Resmi LibTV CLI yeteneği: video oluşturma tuvali ve iş akışları."
    },
    "jev-decisions": {
        "title": "Jev Decisions",
        "displayName": "Jev Decisions",
        "description": "Topluluk jev-mcp sunucusu aracılığıyla ZCode ajanları için kalibre edilmiş karar araçları."
    },
    "visualize": {
        "title": "Görselleştirme",
        "displayName": "Görselleştirme (Visualize)",
        "description": "ZCode sohbetinde etkileşimli açıklamalar, grafikler ve tasarım önizlemeleri oluşturun."
    },
    "android-emulator": {
        "title": "Android Emülatörü",
        "displayName": "Android Emülatörü",
        "description": "Android geliştirme iş akışları ve emülatör otomasyonu."
    },
    "browser-use": {
        "title": "Browser Use",
        "displayName": "Browser Use",
        "description": "Yerleşik tarayıcı otomasyonu çalışma zamanı."
    },
    "documents": {
        "title": "Belgeler",
        "displayName": "Belgeler (Documents)",
        "description": "DOCX belge üretim yetenekleri ve Word görüntüleyici."
    },
    "pdf": {
        "title": "PDF",
        "displayName": "PDF",
        "description": "PDF üretim yetenekleri ve PDF görüntüleyici."
    },
    "presentations": {
        "title": "Sunumlar",
        "displayName": "Sunumlar (Presentations)",
        "description": "PPTX sunum üretim yetenekleri ve PowerPoint görüntüleyici."
    },
    "spreadsheets": {
        "title": "Elektronik Tablolar",
        "displayName": "Elektronik Tablolar (Spreadsheets)",
        "description": "XLSX elektronik tablo yetenekleri ve Excel görüntüleyici."
    },
    "image-search": {
        "title": "Görsel Arama",
        "displayName": "Görsel Arama",
        "description": "İllüstrasyonlar ve referans görseller bulmak için resmi ZCode görsel arama MCP sunucusu."
    },
    "ios-simulator": {
        "title": "iOS Simülatörü",
        "displayName": "iOS Simülatörü",
        "description": "iOS geliştirme iş akışları ve simülatör otomasyonu."
    },
    "restore-legacy-sessions": {
        "title": "Eski Oturumları Geri Yükle",
        "displayName": "Eski Oturumları Geri Yükle",
        "description": "Eski ZCode oturumlarını yeni sisteme aktarın ve geri yükleyin."
    },
    "plugin-creator": {
        "title": "Eklenti Oluşturucu",
        "displayName": "Eklenti Oluşturucu",
        "description": "Yerel geliştirici pazaryeri üzerinden ZCode eklentileri geliştirin."
    },
    "skill-creator": {
        "title": "Beceri Oluşturucu",
        "displayName": "Beceri Oluşturucu",
        "description": "Yerel ZCode yetenekleri oluşturun, düzenleyin ve test edin."
    },
    "zcode-guide": {
        "title": "ZCode Rehberi",
        "displayName": "ZCode Rehberi",
        "description": "ZCode kullanım ve otomatik sorun giderme rehberi."
    },
    "computer-use": {
        "title": "Bilgisayar Kontrolü",
        "displayName": "Bilgisayar Kontrolü",
        "description": "Fare, klavye ve UI öğeleriyle masaüstü uygulamalarını otomatikleştirin."
    },
    "zcode-site": {
        "title": "ZCode Siteleri",
        "displayName": "ZCode Siteleri",
        "description": "Web projelerinizi tek komutla canlıya yayınlayın ve ZCode Sites üzerinden önizleme bağlantısı alın."
    }
}

# Marketplace JSON dosyalarını yamala
def patch_marketplace_file(filepath):
    if not os.path.exists(filepath):
        print(f"[YOK] {filepath}")
        return 0

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    updated = 0
    plugins = data.get("plugins", [])
    for pl in plugins:
        pname = pl.get("name")
        if pname in ZCODE_OFFICIAL_PLUGINS_TR:
            info = ZCODE_OFFICIAL_PLUGINS_TR[pname]
            pl["title"] = info["title"]
            pl["displayName"] = info["displayName"]
            pl["description"] = info["description"]
            
            # i18n objesi varsa tr ekle
            if "description_i18n" not in pl or not isinstance(pl["description_i18n"], dict):
                pl["description_i18n"] = {}
            pl["description_i18n"]["tr"] = info["description"]
            pl["description_i18n"]["en"] = pl["description_i18n"].get("en", info["description"])

            if "title_i18n" not in pl or not isinstance(pl["title_i18n"], dict):
                pl["title_i18n"] = {}
            pl["title_i18n"]["tr"] = info["title"]

            # Kategori düzeltmesi
            if pl.get("category") == "游戏/3D":
                pl["category"] = "game3d"

            updated += 1

    with open(filepath, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[TAMAMLANDI] {filepath} -> {updated}/{len(plugins)} eklenti güncellendi.")
    return updated

def main():
    targets = [
        os.path.expanduser("~/.zcode/cli/plugins/marketplaces/zcode-plugins-official/marketplace.json"),
        os.path.expanduser("~/.zcode/cli/plugins/marketplaces/zcode-plugins-official/cdn-marketplace.json"),
        os.path.expanduser("~/.zcode/cli/plugins/marketplaces/claude-plugins-official/marketplace.json"),
        os.path.expanduser("~/.zcode/cli/plugins/marketplaces/claude-plugins-official/.claude-plugin/marketplace.json"),
    ]

    for t in targets:
        patch_marketplace_file(t)

if __name__ == "__main__":
    main()
