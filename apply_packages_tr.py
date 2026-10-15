# -*- coding: utf-8 -*-
"""
apply_packages_tr.py
ZCode eklenti, yetenek, komut ve pazar yeri dosyalarını
kusursuz, profesyonel Türkçe ile günceller (UTF-8 No BOM).
"""

import os
import json
import re

USER_ZCODE = os.path.expanduser(r"~\.zcode")
PROGRAM_PACKAGES = r"C:\Program Files\ZCode\resources\glm\packages"

CLAUDE_PLUGINS_TR = {}
try:
    _claude_json = os.path.join(os.path.dirname(os.path.abspath(__file__)), "claude_plugins_tr.json")
    if os.path.exists(_claude_json):
        with open(_claude_json, "r", encoding="utf-8") as _f:
            CLAUDE_PLUGINS_TR = json.load(_f)
except Exception as _e:
    pass

PLUGIN_TRANSLATIONS = {
    # Resmi araçlar ve sistem eklentileri
    "android-emulator": {
        "displayName": "Android Emülatörü",
        "description": "Android emülatörlerini yönetme, başlatma ve cihaz kontrolü için geliştirici araçları."
    },
    "browser-use": {
        "displayName": "Browser Use",
        "description": "Masaüstü için yerleşik tarayıcı otomasyonu çalışma ortamı ve rehberlik."
    },
    "document-skills": {
        "displayName": "Belge Becerileri",
        "description": "Yerleşik DOCX ve PDF belge oluşturma becerileri.",
        "examplePrompts": [
            "Notlarımdan biçimlendirilmiş bir Word belgesi oluştur",
            "Bu PDF'deki tabloları bir elektronik tabloya aktar",
            "Bu CSV dosyasından grafikler içeren bir Excel çalışma kitabı oluştur"
        ]
    },
    "documents": {
        "displayName": "Documents",
        "description": "Resmi ZCode eklentisi olarak yayınlanan DOCX belge üretim becerileri."
    },
    "pdf": {
        "displayName": "PDF",
        "description": "Resmi ZCode eklentisi olarak yayınlanan PDF belge üretim becerileri."
    },
    "presentations": {
        "displayName": "Presentations",
        "description": "Resmi ZCode eklentisi olarak yayınlanan PPTX sunum üretim becerileri."
    },
    "spreadsheets": {
        "displayName": "Spreadsheets",
        "description": "Resmi ZCode eklentisi olarak yayınlanan XLSX hesap tablosu üretim becerileri."
    },
    "image-search": {
        "displayName": "Image Search",
        "description": "İllüstrasyonlar ve referans görselleri bulmak için resmi ZCode görsel arama MCP sunucusu."
    },
    "node-repl-host": {
        "displayName": "node_repl Barındırıcısı",
        "description": "Resmi ZCode yetenekleri için paylaşılan node_repl çalışma ortamı barındırıcısı."
    },
    "hyper3d-rodin": {
        "displayName": "Hyper3D Rodin",
        "description": "Hyper3D Rodin ile metin istemlerinden veya referans görsellerden 3B modeller üretin."
    },
    "jupyter-notebook": {
        "displayName": "Jupyter Notebook",
        "description": "Jupyter not defterleriyle yan panelde çalışın: çalışan bir çekirdeğe bağlanın, hücreleri çalıştırın ve çıktıları inceleyin."
    },
    "zcode-context": {
        "displayName": "ZCode Context",
        "description": "Salt okunur oturum kullanımı, model girdi bileşimi, istek farkları ve bağlam analitiği."
    },
    "zcode-mcp-app-dev": {
        "displayName": "ZCode MCP App Dev",
        "description": "Resmi SDKlar ve yerel geliştirici ortamı ile ZCode için MCP Uygulamaları geliştirin."
    },
    "blender": {
        "displayName": "Blender",
        "description": "Etkileşimli 3B panel ve MCP araçlarıyla Blender sahnelerini düzenleyin."
    },
    "cadcraft": {
        "displayName": "CADCraft",
        "description": "Çalışma alanı dosyaları ve DXF dışa aktarma desteğiyle ZCode panelinde CADCraft CAD çizim ve modelleme."
    },
    "deckcraft": {
        "displayName": "DeckCraft",
        "description": "Çalışma alanı dosyaları ve slayt dışa aktarma desteğiyle ZCode panelinde DeckCraft interaktif sunumlar."
    },
    "designcraft": {
        "displayName": "DesignCraft",
        "description": "Çalışma alanı dosyaları ve tuval düzenleme desteğiyle ZCode panelinde DesignCraft sayfa ve grafik tasarımı."
    },
    "excalidraw": {
        "displayName": "Excalidraw",
        "description": "Excalidraw ve MCP araçlarıyla el çizimi tarzında diyagramlar ve şemalar oluşturun."
    },
    "gridcraft": {
        "displayName": "GridCraft",
        "description": "Çalışma alanı dosyaları ve tablo dışa aktarma desteğiyle ZCode panelinde GridCraft elektronik tablo düzenleme."
    },
    "openpencil": {
        "displayName": "OpenPencil",
        "description": "OpenPencil ve MCP araçlarıyla tasarım ve vektör dosyalarını düzenleyin."
    },
    "pdfcraft": {
        "displayName": "PdfCraft",
        "description": "Çalışma alanı dosyaları ve not ekleme desteğiyle ZCode panelinde PdfCraft PDF düzenleme ve inceleme."
    },
    "photocraft": {
        "displayName": "PhotoCraft",
        "description": "Çalışma alanı dosyaları ve raster filtre desteğiyle ZCode panelinde PhotoCraft görsel düzenleme."
    },
    "soundcraft": {
        "displayName": "SoundCraft",
        "description": "Çalışma alanı dosyaları ve dalga formu desteğiyle ZCode panelinde SoundCraft ses düzenleme."
    },
    "tripo-3d": {
        "displayName": "Tripo 3D",
        "description": "Bir metin isteminden veya referans görselden kaplamalı, animasyona hazır 3B modeller üretin."
    },
    "typst-workbench": {
        "displayName": "Typst Workbench",
        "description": "Etkileşimli Typst derleyicisi ile Typst belgelerini yan panelde canlı önizleyin ve düzenleyin."
    },
    "vectorcraft": {
        "displayName": "VectorCraft",
        "description": "Çalışma alanı dosyaları ve SVG dışa aktarma desteğiyle ZCode panelinde VectorCraft vektörel illüstrasyon."
    },
    "visualize": {
        "displayName": "Visualize",
        "description": "ZCode içinde HTML tuvali ile etkileşimli açıklamalar, grafikler ve tasarım önizlemeleri oluşturun."
    },
    "wordcraft": {
        "displayName": "WordCraft",
        "description": "Çalışma alanı dosyaları ve zengin metin düzenleme desteğiyle ZCode panelinde WordCraft belge işleme."
    },
    "zotero": {
        "displayName": "Zotero",
        "description": "Yan panelde Zotero kütüphanenizle çalışın: makaleleri arayın, okuyun, alıntıları dışa aktarın ve koleksiyonları yönetin."
    },
    "ios-simulator": {
        "displayName": "iOS Simülatörü",
        "description": "iOS simülatörlerini yönetme, test etme ve arayüz denetimi araçları."
    },
    "restore-legacy-sessions": {
        "displayName": "Eski Oturumları Geri Yükle",
        "description": "Önceki sürümlerden kalan eski oturumları ve sohbet geçmişlerini geri yükleyin."
    },
    "skill-creator": {
        "displayName": "Beceri Oluşturucu",
        "description": "Yeni ajan becerileri ve iş akışları oluşturmak için rehberli araç seti."
    },
    "plugin-creator": {
        "displayName": "Plugin Creator",
        "description": "Yerel bir geliştirici pazar yeri, kurulum, denemeler ve güncellemeler aracılığıyla ZCode eklentileri geliştirin ve doğrulayın."
    },
    "zcode-guide": {
        "displayName": "ZCode Rehberi",
        "description": "ZCode özellikleri, komutları ve yapılandırmaları için kapsamlı kullanım kılavuzu.",
        "examplePrompts": [
            "ZCode'da MCP sunucularını nasıl yapılandırırım?",
            "Mevcut ZCode yapılandırmamı tanıla"
        ]
    },
    "computer-use": {
        "displayName": "Bilgisayar Kontrolü",
        "description": "Bilgisayar Kontrolü: Masaüstü uygulamalarını fare, klavye ve sistem eylemleriyle otomatikleştirin."
    },
    "zcode-cua": {
        "displayName": "Bilgisayar Kontrolü",
        "description": "Bilgisayar Kontrolü: Masaüstü uygulamalarını fare, klavye ve sistem eylemleriyle otomatikleştirin."
    },
    "video-agent-kit": {
        "displayName": "Video Ajan Kiti",
        "description": "Otomatik video düzenleme araç seti: Bulut ses transkripsiyonu ve sentezi, kare analizi, zaman çizelgesi ve önizleme."
    },
    "video2code": {
        "displayName": "Video2Code",
        "description": "ZCode yerleşik Browser Use WebView ile WebM kaydı ve ffmpeg ile MP4 dönüştürme/yeniden oluşturma."
    },
    "mimosa": {
        "displayName": "Kod Güvenlik Koruması",
        "description": "ZCode için yazma öncesi kancalar, tur sonu incelemesi, Git kapıları ve güvenlik taraması becerisiyle yerel öncelikli güvenlik koruması."
    },
    "cloudbase-skills": {
        "displayName": "CloudBase Becerileri",
        "description": "Web, WeChat Mini Programı, veritabanı, bulut fonksiyonları ve yapay zeka projeleri için CloudBase geliştirme becerileri ve MCP entegrasyonu."
    },
    "github": {
        "displayName": "GitHub CLI",
        "description": "Commit, pull request, issue, release, Actions ve repolar için GitHub CLI iş akışları."
    },
    "gitlab": {
        "displayName": "GitLab CLI",
        "description": "Merge request, issue, CI/CD ve repolar için GitLab resmi ajan becerilerine dayalı GitLab CLI iş akışları."
    },
    "alibaba-cloud-cli": {
        "displayName": "Alibaba Cloud CLI",
        "description": "Kimlik bilgisi kurulumu, profil kontrolleri ve güvenli bulut kaynak işlemleri için Alibaba Cloud CLI iş akışları."
    },
    "lark-cli": {
        "displayName": "Lark CLI",
        "description": "Belgeler, tablolar, Base, takvim ve mesajlaşma için rehberli kurulum ve OAuth girişli Lark CLI iş akışları."
    },
    "tencent-meeting-cli": {
        "displayName": "Tencent Meeting CLI",
        "description": "OAuth2 kurulumu, toplantı yönetimi, kayıtlar ve katılımcı raporlarıyla Tencent Meeting CLI iş akışları."
    },
    "dingtalk-cli": {
        "displayName": "DingTalk CLI",
        "description": "OAuth/cihaz yetkilendirmesi, profil kontrolleri ve yeteneklerle DingTalk Çalışma Alanı CLI iş akışları."
    },
    "wecom-cli": {
        "displayName": "WeCom CLI",
        "description": "Mesajlar, belgeler, tablolar, takvim, toplantılar ve kişiler için QR doğrulamalı WeCom CLI iş akışları."
    },
    "obsidian": {
        "displayName": "Obsidian",
        "description": "Obsidian Markdown notları, Bases veritabanı görünümleri, Canvas panoları, CLI otomasyonu ve görselleştirme becerileri."
    },
    "accounting-and-reporting": {
        "displayName": "Muhasebe ve Raporlama",
        "description": "Şirket defterinden muhasebe kapanışı ve yasal raporlama: ay sonu kontrolleri ve mutabakat."
    },
    "assess-credit": {
        "displayName": "Sabit Getiri ve Kredi Araştırması",
        "description": "Sabit getirili menkul kıymetler ve kredi araştırması: tahvil profilleri, ihraççı değerlendirmesi ve getiri eğrisi analizi."
    },
    "find-clients": {
        "displayName": "Kurumsal Müşteri Kazanımı",
        "description": "Kurumsal bankacılık müşteri kazanımı: bölgeye ve sektöre göre potansiyel müşteri taraması ve fırsat analizi."
    },
    "model-deals": {
        "displayName": "İşlem Modelleme ve Yapılandırma",
        "description": "İşlem yapılandırma ve modelleme: M&A, IPO ve sermaye artırımı seyreltme analizi."
    },
    "pick-funds": {
        "displayName": "Fon ve Portföy Araştırması",
        "description": "Fon ve fon yöneticisi araştırması: çok kriterli fon taraması, portföy ve stil analizi."
    },
    "read-macro": {
        "displayName": "Makro Strateji Analizi",
        "description": "Yukarıdan aşağıya makro strateji: büyüme, enflasyon, likidite ve çapraz varlık dağılım görünümleri."
    },
    "run-fpa": {
        "displayName": "Finansal Planlama ve Analiz (FP&A)",
        "description": "Kurumsal finansman ve FP&A: yönetim raporlaması, nakit akışı tahminleri ve bütçe-gerçekleşen varyans analizi."
    },
    "vet-companies": {
        "displayName": "Şirket Durum Tespiti (Due Diligence)",
        "description": "Karşı taraf ve şirket durum tespiti: yapılandırılmış DD raporları, tedarik zinciri haritalama ve risk taraması."
    },
    "watch-positions": {
        "displayName": "Pozisyon ve Portföy Takibi",
        "description": "İzleme listesi ve portföy takibi: kapanış sonrası özetler, pozisyon olay uyarıları ve gün içi hareket analizi."
    },
    "write-research": {
        "displayName": "Yatırım ve Hisse Araştırması",
        "description": "Uçtan uca yatırım araştırma raporları, sektör analizi, kazanç güncellemeleri ve değerleme modelleri."
    },
    "hexin": {
        "displayName": "Tonghuashun iFinD",
        "description": "RoyalFlush iFinD hisse senedi, küresel hisseler, endeks, fon ve tahvil verileri için MCP hizmetleri."
    },
    "wind": {
        "displayName": "Wind Finansal Veri",
        "description": "Wind hisse senedi, küresel hisseler, endeks, fon, tahvil, ekonomik ve doküman verileri için MCP hizmetleri."
    },
    "tianyancha": {
        "displayName": "Tianyancha Şirket Bilgileri",
        "description": "Tianyancha şirket bilgileri sorguları için MCP hizmeti."
    },
    "finance-search": {
        "displayName": "Finansal Arama",
        "description": "SEC EDGAR dosyalama araması ve finansal web/haber aramaları için MCP hizmetleri."
    }
}

SKILL_TRANSLATIONS = {
    "android-dev": "android-emulator MCP araçlarıyla Android emülatör uygulamalarını derleyin, çalıştırın, denetleyin ve kolayca otomatikleştirin.",
    "control-browser": "Yalnızca ana ajan tarayıcı kullanımı: ZCode içinde web sayfalarını ve yerel HTTP hedeflerini açın, gezinin, inceleyin, tıklayın, form doldurun, ekran görüntüsü alın ve doğrulayın.",
    "web-gui-tester": "Oturumdaki tarayıcı otomasyon araçlarını kullanarak web arayüzlerini etkileşimli olarak test edin, kullanıcı eylemlerini simüle edin, ekran görüntüleriyle doğrulayın ve test raporu oluşturun.",
    "docx": "Revizyonlar, yorumlar, biçimlendirme koruma ve metin çıkarma desteğiyle kapsamlı DOCX belgesi oluşturma, düzenleme ve analiz yetenekleri. Şablon tabanlı üretim ve format dönüştürmeyi destekler.",
    "pdf": "4 özel iş akışına sahip profesyonel PDF işleme araç seti: Typst/ReportLab ile yayın kalitesinde PDF üretimi, HTML/CSS tuvali ile görsel belge biçimlendirme, LaTeX ile akademik makaleler ve PyMuPDF/pdfplumber ile programatik düzenleme. Akıllı yönlendirme, format doğrulama ve otomatik kalite kontrolleri içerir.",
    "pptx": "PowerPoint (.pptx) sunum oluşturma, biçimlendirme ve düzenleme yetenekleri. Sıfırdan veya taslaklardan sunum hazırlama, mevcut slaytları düzenleme ve metin/not çıkarma işlemlerini kapsar.",
    "xlsx": "Veri analizi, formüller ve grafiklerle Excel (.xlsx, .xlsm, .csv) için gelişmiş elektronik tablo işleme yetenekleri. Sıfırdan çalışma kitapları oluşturma, mevcut tabloları düzenleme, veri analizi ve formül hesaplamalarını kapsar.",
    "ios-dev": "ios-simulator MCP araçlarıyla iOS simülatör uygulamalarını derleyin, çalıştırın, denetleyin ve kolayca otomatikleştirin.",
    "restore-legacy-sessions": "ZCode'un ~/.zcode/v2/sessions altındaki eski ACP dönemi ZCode oturumlarını yeni ZCode görev/oturum depolarına aktarması, incelemesi veya planlaması gerektiğinde kullanın. Eski sohbet geçmişini taşıma veya önceki oturumları geri yükleme sorularında tetiklenir.",
    "skill-creator": "Yeni beceriler oluşturun, mevcut becerileri düzenleyin ve ifadeleri iyileştirin. Sıfırdan SKILL.md yazarken, mevcut becerileri geliştirirken, tekrarlanan iş akışlarını yeniden kullanılabilir becerilere dönüştürürken veya beceri tetikleyicilerini giderirken kullanın.",
    "plugin-creator": "ZCode eklenti kaynak kodunu ve yerel bir test mağazasını oluşturun veya güncelleyin; ardından kullanıcıya mağazayı ekleme, eklentiyi yükleme veya güncelleme ve uygulamada deneme konusunda rehberlik edin.",
    "computer-use": "Erişilebilirlik odaklı semantik eylemler ve görsel doğrulama ile masaüstü kontrolü.",
    "zcode-computer-use": "Erişilebilirlik odaklı semantik eylemler ve görsel doğrulama ile masaüstü kontrolü.",
    "diagnosing-commands": "ZCode istemcisindeki özel eğik çizgi komutu (/komut) yapılandırma sorunlarını teşhis etmek ve düzeltmek için kullanın. Bir komut eksik olduğunda, bir beceri/ajan tarafından geçersiz kılındığında, ayrıştırılamadığında, kapsamlarda yinelenen adlara sahip olduğunda veya çalıştırılamadığında geçerlidir.",
    "diagnosing-hooks": "ZCode istemcisindeki kanca (hook) yapılandırma sorunlarını teşhis etmek ve düzeltmek için kullanın. Bir kanca tetiklenmediğinde, bir olay adı yanlış olduğunda, bir eşleştirici eşleşmediğinde, bir komut dosyası başarısız olduğunda veya kanca sıralaması/izinleri beklenmeyen davranışlara yol açtığında geçerlidir.",
    "diagnosing-mcp": "ZCode istemcisindeki MCP (Model Bağlam Protokolü) sunucu yapılandırma sorunlarını teşhis etmek ve düzeltmek için kullanın. Bir MCP sunucusu bağlanmadığında, araçları eksik olduğunda, işlemi hata ile sonlandığında, aktarım protokolü (stdio veya SSE) yanlış yapılandırıldığında veya ortam değişkenleri hatalı olduğunda geçerlidir.",
    "diagnosing-plugins": "ZCode istemcisindeki eklenti ve mağaza sorunlarını teşhis etmek ve düzeltmek için kullanın. Bir eklenti listelenmediğinde, mağaza ekleme veya eklenti yükleme başarısız olduğunda, bir eklenti komutu/becerisi/ajanı eksik olduğunda veya bir eklenti yapılandırması bozulduğunda geçerlidir.",
    "diagnosing-skills": "ZCode istemcisindeki beceri yapılandırma sorunlarını teşhis etmek ve düzeltmek için kullanın. Bir beceri keşfedilmediğinde, yüklü olduğu halde otomatik tetiklenmediğinde, dosyaları eksik olduğunda, frontmatter ayrıştırma hataları verdiğinde veya kapsamlarda yinelenen adlara sahip olduğunda geçerlidir.",
    "zcode-configuration-guide": "ZCode istemcisinde uzantı kaynaklarını (MCP sunucuları, eğik çizgi komutları, beceriler, kancalar ve eklentiler) veya AGENTS.md gibi talimat dosyalarını yapılandırırken kullanın. Bir kullanıcı bu uzantı mekanizmalarının nasıl ekleneceğini, düzenleneceğini veya yapılandırılacağını sorduğunda geçerlidir.",
    "microsoft-foundry": "Microsoft Foundry ajanlarını, modellerini ve kaynaklarını uçtan uca derleyin, dağıtın, değerlendirin, optimize edin, ince ayar yapın ve yönetin.",
    "finetuning": "SFT, DPO veya RFT kullanarak Microsoft Foundry üzerinde modelleri ince ayarlar (fine-tune). Veri kümesi hazırlama, eğitim işi gönderme, değerlendirme ve dağıtımı kapsar.",
    "deploy-model": "Akıllı amaç tabanlı yönlendirme ile birleşik Azure OpenAI model dağıtım yeteneği. Hem hızlı ön ayarlı hem de tam özelleştirilmiş dağıtımları yönetir.",
    "capacity": "Bölgeler ve abonelikler genelinde kullanılabilir Azure OpenAI model kapasitesini keşfeder. Kota sınırlarını analiz eder ve en uygun dağıtım konumlarını önerir.",
    "customize": "Tam özelleştirme kontrolüyle Azure OpenAI modelleri için etkileşimli rehberli dağıtım akışı. Model sürümü, SKU, kapasite ve içerik filtreleme ilkesi seçimini sağlar.",
    "preset": "Kullanılabilir tüm bölgelerdeki kapasiteyi analiz ederek Azure OpenAI modellerini en uygun bölgelere akıllıca dağıtır. Kapasite mevcut olduğunda geçerli bölgeyi tercih eder.",
    "chrome-cdp": "Chrome oturumu ile etkileşim kurun, sayfaları denetleyin ve test edin.",
    "codebase-memory": "Yapısal kod sorguları, mimari keşif ve çağrı zinciri analizi için kod tabanı bilgi grafiğini kullanın.",
    "desktop-eye": "Canlı masaüstü ekran görüntüsü alarak arayüz bağlamını anlık olarak doğrulayın."
}

COMMAND_TRANSLATIONS = {
    "android-dev.md": {
        "description": "Android emülatör geliştirme döngüsünü başlatın.",
        "argument-hint": "\"[hedef veya sorun açıklaması]\""
    },
    "ios-dev.md": {
        "description": "iOS simülatör geliştirme döngüsünü başlatın.",
        "argument-hint": "\"[hedef veya sorun açıklaması]\""
    },
    "restore-legacy-sessions.md": {
        "description": "Eski bir ZCode oturumunu seçin ve geri yükleyin.",
        "argument-hint": "\"[ajan/çalışma alanı/oturum filtreleri]\""
    }
}


def patch_json_file(filepath):
    try:
        with open(filepath, "r", encoding="utf-8-sig") as f:
            data = json.load(f)

        changed = False

        name = data.get("name")
        if name:
            clean_name = name.replace("-plugin", "")
            tr_info = PLUGIN_TRANSLATIONS.get(clean_name) or PLUGIN_TRANSLATIONS.get(name)
            if tr_info:
                if "description" in tr_info and data.get("description") != tr_info["description"]:
                    data["description"] = tr_info["description"]
                    changed = True
                if "displayName" in tr_info and "displayName" in data and data.get("displayName") != tr_info["displayName"]:
                    data["displayName"] = tr_info["displayName"]
                    changed = True

        if "manifest" in data and "plugins" in data["manifest"]:
            for pl in data["manifest"]["plugins"]:
                pname = pl.get("name")
                tr_info = PLUGIN_TRANSLATIONS.get(pname)
                if tr_info:
                    if "description" in tr_info and pl.get("description") != tr_info["description"]:
                        pl["description"] = tr_info["description"]
                        if "description_i18n" not in pl:
                            pl["description_i18n"] = {}
                        pl["description_i18n"]["tr"] = tr_info["description"]
                        changed = True
                    if "displayName" in tr_info and pl.get("displayName") != tr_info["displayName"]:
                        pl["displayName"] = tr_info["displayName"]
                        changed = True
                    if "examplePrompts" in tr_info:
                        pl["examplePrompts"] = tr_info["examplePrompts"]
                        if "examplePrompts_i18n" not in pl:
                            pl["examplePrompts_i18n"] = {}
                        pl["examplePrompts_i18n"]["tr"] = tr_info["examplePrompts"]
                        changed = True

        if "plugins" in data and isinstance(data["plugins"], list):
            for pl in data["plugins"]:
                pname = pl.get("name")
                tr_info = PLUGIN_TRANSLATIONS.get(pname)
                if tr_info:
                    if "description" in tr_info and pl.get("description") != tr_info["description"]:
                        pl["description"] = tr_info["description"]
                        if "description_i18n" not in pl:
                            pl["description_i18n"] = {}
                        pl["description_i18n"]["tr"] = tr_info["description"]
                        changed = True
                    if "displayName" in tr_info and pl.get("displayName") != tr_info["displayName"]:
                        pl["displayName"] = tr_info["displayName"]
                        changed = True
                    if "examplePrompts" in tr_info:
                        pl["examplePrompts"] = tr_info["examplePrompts"]
                        if "examplePrompts_i18n" not in pl or not isinstance(pl["examplePrompts_i18n"], dict):
                            pl["examplePrompts_i18n"] = {}
                        pl["examplePrompts_i18n"]["tr"] = tr_info["examplePrompts"]
                        changed = True
                elif CLAUDE_PLUGINS_TR and pname in CLAUDE_PLUGINS_TR:
                    c_desc = CLAUDE_PLUGINS_TR[pname]
                    if pl.get("description") != c_desc:
                        pl["description"] = c_desc
                        if "description_i18n" not in pl or not isinstance(pl["description_i18n"], dict):
                            pl["description_i18n"] = {}
                        pl["description_i18n"]["tr"] = c_desc
                        changed = True

        if changed:
            with open(filepath, "w", encoding="utf-8", newline="\n") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"[OK JSON] {filepath}")
    except Exception as e:
        print(f"[ERR JSON] {filepath}: {e}")


def patch_markdown_file(filepath):
    try:
        with open(filepath, "r", encoding="utf-8-sig") as f:
            content = f.read()

        changed = False

        if os.path.basename(filepath) == "SKILL.md":
            for skill_name, tr_desc in SKILL_TRANSLATIONS.items():
                if re.search(rf"^name:\s*{re.escape(skill_name)}\b", content, re.MULTILINE):
                    new_content, n = re.subn(
                        r"(^description:\s*)([^\n>]+)",
                        rf'\g<1>"{tr_desc}"',
                        content,
                        flags=re.MULTILINE
                    )
                    if n > 0:
                        content = new_content
                        changed = True
                    else:
                        new_content, n = re.subn(
                            r"(^description:\s*>\n(?:\s+[^\n]+\n)+)",
                            f'description: "{tr_desc}"\n',
                            content,
                            flags=re.MULTILINE
                        )
                        if n > 0:
                            content = new_content
                            changed = True

        cmd_name = os.path.basename(filepath)
        if cmd_name in COMMAND_TRANSLATIONS:
            cmd_info = COMMAND_TRANSLATIONS[cmd_name]
            tr_desc = cmd_info["description"]
            tr_hint = cmd_info.get("argument-hint")

            new_content, n = re.subn(
                r"(^description:\s*)([^\n]+)",
                rf'\g<1>"{tr_desc}"',
                content,
                flags=re.MULTILINE
            )
            if n > 0:
                content = new_content
                changed = True

            if tr_hint:
                new_content, n2 = re.subn(
                    r"(^argument-hint:\s*)([^\n]+)",
                    rf'\g<1>{tr_hint}',
                    content,
                    flags=re.MULTILINE
                )
                if n2 > 0:
                    content = new_content
                    changed = True

        if changed:
            with open(filepath, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
            print(f"[OK MD] {filepath}")
    except Exception as e:
        print(f"[ERR MD] {filepath}: {e}")


def patch_special_files():
    # 1. server.js
    server_paths = [
        r"C:\Program Files\ZCode\resources\glm\packages\browser-use-plugin\dist\mcp\server.js",
        os.path.join(USER_ZCODE, r"cli\plugins\cache\zcode-plugins-official\browser-use\0.4.2\dist\mcp\server.js")
    ]
    for sp in server_paths:
        if os.path.exists(sp):
            try:
                with open(sp, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                orig_len = len(content)
                content = content.replace("General-purpose agent for researching complex questions, searching for code, and executing multi-step tasks.", "Karmaşık soruları araştırmak, kod aramak ve çok adımlı görevleri yürütmek için genel amaçlı ajan.")
                content = content.replace("Read-only search agent for broad fan-out searches", "Geniş kapsamlı aramalar için salt okunur arama ajanı")
                if len(content) != orig_len or "Karmaşık soruları" in content:
                    with open(sp, "w", encoding="utf-8", newline="\n") as f:
                        f.write(content)
                    print(f"[OK SERVER.JS] {sp}")
            except Exception as e:
                print(f"[ERR SERVER.JS] {sp}: {e}")

    # 2. judge.md
    judge_paths = [
        r"C:\Program Files\ZCode\resources\glm\packages\document-skills-plugin\agents\judge.md",
        os.path.join(USER_ZCODE, r"cli\plugins\cache\zcode-plugins-official\document-skills\0.1.4\agents\judge.md"),
        os.path.join(USER_ZCODE, r"cli\plugins\cache\zcode-plugins-official\document-skills\0.1.5\agents\judge.md")
    ]
    for jp in judge_paths:
        if os.path.exists(jp):
            try:
                with open(jp, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                if "kabul incelemesi" not in content or "Ã" in content:
                    content = re.sub(r'description:\s*"[^"]+"', 'description: "Yalnızca pptx, docx, xlsx, pdf, poster ve grafik türündeki görsel çıktıların kabul incelemesi için tek yetkili görsel onay ajanı."', content)
                    with open(jp, "w", encoding="utf-8", newline="\n") as f:
                        f.write(content)
                    print(f"[OK JUDGE.MD] {jp}")
            except Exception as e:
                print(f"[ERR JUDGE.MD] {jp}: {e}")


def scan_and_patch(root_dir):
    if not os.path.exists(root_dir):
        return
    for root, dirs, files in os.walk(root_dir):
        for f in files:
            p = os.path.join(root, f)
            if f in ("plugin.json", "bundled-marketplace.json", "cdn-marketplace.json", "marketplace.json"):
                patch_json_file(p)
            elif f == "SKILL.md" or (f.endswith(".md") and "commands" in root):
                patch_markdown_file(p)


def main():
    print("ZCode Eklenti ve Paket Türkçe Yamalama Başlatılıyor...")
    patch_special_files()
    scan_and_patch(os.path.join(USER_ZCODE, "cli", "plugins"))
    scan_and_patch(PROGRAM_PACKAGES)
    scan_and_patch(os.path.expanduser(r"~\.agents\skills"))
    scan_and_patch(os.path.expanduser(r"~\.claude\skills"))
    print("Eklenti paketleri başarıyla güncellendi!")


if __name__ == "__main__":
    main()
