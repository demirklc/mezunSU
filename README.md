# mezunSU

https://demirklc.github.io/mezunSU/

Sabancı Üniversitesi müfredatına göre ders ve mezuniyet planlama aracı. Resmi mezuniyet onayı vermez; kesin durum SUIS Degree Evaluation üzerinden kontrol edilmelidir.

Hesap açılmaz. Dersler, durumları ve planlanan dönemler yalnızca kullanıcının tarayıcısında saklanır. Tarayıcı veya cihaz değiştirirken JSON yedeği indirin ve yeni cihazda geri yükleyin. Site adresi değişirse eski adreste yedek almanız gerekir. Gizli gezinme veya tarayıcı verilerini temizlemek kayıtları silebilir.

GitHub Actions genel SUIS müfredatını ve ders bilgilerini hazırlayıp GitHub Pages üzerinden yayınlar. Ziyaret sırasında Python sunucusu kullanılmaz. Mezuniyet hesabı tarayıcıda yapılır. Kişisel profil, ders ekleme ve planlama için sunucu uç noktası bulunmaz. Sunucuya ders bilgi isteğinde yalnızca ders kodları gönderilir.

## Sunucusuz yayın ve otomatik güncelleme

Site GitHub Pages üzerinde çalışır. `.github/workflows/pages.yml` her gün 03:20 UTC'de (Türkiye saatiyle 06:20) ve main dalına kod yüklendiğinde çalışır. GitHub zamanlanmış işleri geciktirebilir. İlk hazırlamada bütün bölümler ve giriş dönemleri taranır; müfredat ve ders bilgileri en fazla yedi günlük önbellek süresiyle yenilenir. Son veri tarihi müfredat kaynak bağlantısının altında görünür.

SUIS'e ulaşılamazsa daha önce doğrulanmış veriler korunur. Hiç hazırlanamayan müfredatta açık bir hata gösterilir. Eksik ders alt kredileri bilinmiyor olarak kalır; tahmin edilmez. Veriler `snapshots` dalında tutulur, uygulama kaynakları `main` dalındadır. Güncelleme için Actions → Update SUIS and publish Pages → Run workflow kullanılabilir.

Eski Render adresindeki kayıtlar yeni adresin tarayıcı deposuna kendiliğinden taşınmaz. Eski sitede JSON yedeğini indirin ve yeni sitede geri yükleyin. Yedekler GitHub'a yüklenmemelidir.

## Kontroller
```sh
pip install -r requirements.txt
python -m pytest -q
node tests/local-data.cjs
```

`main.py` önceki yerel FastAPI sürümünün kaynak kodudur; GitHub Pages yayınında kullanılmaz. Resmi mezuniyet sonucu için SUIS Degree Evaluation gereklidir.
