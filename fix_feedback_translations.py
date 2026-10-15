# -*- coding: utf-8 -*-
import json

updates = {
    'workspaceHeader.help.community': 'Kullanıcı Topluluğu',
    'workspaceHeader.help.productRequest': 'Özellik İsteğinde Bulunun',
    'feedback.center.submitTitle': 'Geri Bildirim Gönder',
    'feedback.tickets.empty.action': 'Geri Bildirim Gönder',
    'feedback.submit.submit': 'Geri Bildirim Gönder',
    'feedback.submit.simple.logsLabel': 'Tanılama günlüklerini yükle',
    'feedback.timeline.event.submitted': 'Geri bildirim gönderildi',
    'feedback.submission.submittedLabel': 'Geri bildirim gönderildi',
    'feedback.featureRequest.title': 'Özellik İsteğinde Bulunun',
    'feedback.featureRequest.descriptionLabel': 'Özellik Açıklaması',
    'feedback.featureRequest.solutionLabel': 'Beklenen Çözüm',
    'feedback.featureRequest.submit': 'İsteği Gönder',
    'feedback.background.pauseLogs': 'Günlükleri duraklat',
    'feedback.module.modelCallError': 'Model Çağrısı Hatası',
    'feedback.status.needInfo': 'Daha Fazla Bilgi Gerekiyor',
    'feedback.detail.issueCopy': 'Sorun Kimliğini Kopyala',
    'feedback.detail.issueCopied': 'Sorun Kimliği Kopyalandı',
    'feedback.process.currentLatest': 'En Son:',
    'feedback.timeline.officialReply': 'Ekip Yanıtı',
    'feedback.timeline.event.progressUpdated': 'İlerleme Güncellendi',
    'feedback.timeline.event.conclusion': 'Sonuç Eklendi',
    'feedback.supplement.send': 'Güncellemeyi Gönder',
    'feedback.type.usage.label': 'Kullanım Yardımı',
    'feedback.submit.feature.helper.2': 'Mevcut Zorluk / Sorun',
    'feedback.submit.template.feature.currentPain': 'Mevcut Zorluk:',
    'feedback.submit.feature.supplementalDescription': 'Öncelik ve etkiyi değerlendirebilmemiz için bir modül seçin.',
    'feedback.submit.performance.helper.2': 'Hissedilen Gecikme',
    'feedback.submit.performance.helper.3': 'Yeniden Oluşturma Adımları',
    'feedback.submit.template.performance.reproducible': 'Tekrarlanabilirlik:',
    'feedback.submit.template.usage.blockedStep': 'Takılınan Adım:',
    'feedback.submit.template.usage.help': 'İhtiyaç Duyulan Yardım:',
    'feedback.submit.type.label': 'Geri Bildirim Türü',
    'feedback.submit.model.label': 'Mevcut Yapay Zekâ Modeli',
    'feedback.submit.continueUpload': 'Yüklemeye Devam Et',
    'feedback.submit.template.section.taskLogPath': 'Görev Günlüğü: {path}'
}

with open('tr_dictionary_zcode.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

count = 0
for k, v in updates.items():
    if k in d:
        old = d[k]
        d[k] = v
        count += 1
        print(f"[DEGISIKLIK] {k}: '{old}' -> '{v}'")
    else:
        d[k] = v
        count += 1
        print(f"[EKLENDI] {k}: '{v}'")

with open('tr_dictionary_zcode.json', 'w', encoding='utf-8') as f:
    json.dump(d, f, ensure_ascii=False, indent=2)

print(f"\nToplam {count} anahtar basariyla guncellendi.")
