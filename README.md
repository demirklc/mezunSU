# mezunSU · İlk yayın sürümü

Sabancı Üniversitesi müfredatına göre ders ve mezuniyet planlama aracı. Resmi mezuniyet onayı vermez; kesin durum SUIS Degree Evaluation üzerinden kontrol edilmelidir.

Hesap açılmaz. Dersler, durumları ve planlanan dönemler yalnızca kullanıcının tarayıcısında saklanır. Tarayıcı veya cihaz değiştirirken JSON yedeği indirin ve yeni cihazda geri yükleyin. Site adresi değişirse eski adreste yedek almanız gerekir. Gizli gezinme veya tarayıcı verilerini temizlemek kayıtları silebilir.

Sunucu yalnızca genel SUIS müfredatını, ders bilgilerini ve ortak önbelleği sağlar. Mezuniyet hesabı tarayıcıda yapılır. Kişisel profil, ders ekleme ve planlama için sunucu uç noktası bulunmaz. Sunucuya ders bilgi isteğinde yalnızca ders kodları gönderilir.

## Bilgisayarda çalıştırma

Python 3.10 veya üzeri gerekir. Windows'ta `Baslat.cmd` dosyasını açın; ardından http://127.0.0.1:8787 adresine gidin. Mevcut yerel sürümden aldığınız JSON yedeğini “Yedekten geri yükle” ile aktarabilirsiniz. Eski kurulum bu sürüm tarafından değiştirilmez.

Diğer sistemlerde:
```sh
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8787
```

## GitHub ve Render üzerinden yayınlama

1. GitHub'da yeni bir repository oluşturun. Bu klasörün içeriğini yükleyin; eski kurulumun veritabanını veya kişisel JSON yedeklerini yüklemeyin. `.gitignore` gizli ve yerel dosyaları dışarıda tutar.
2. Render hesabında **New → Blueprint** seçin, GitHub repository'sini bağlayın. `render.yaml` ücretsiz web hizmetini tanımlar.
3. Oluşan HTTPS adresinde müfredat, ders ekleme, yedekleme ve geri yüklemeyi kontrol edin.

GitHub Pages Python sunucusunu çalıştırmaz. GitHub kaynak kodunu, Render çalışan uygulamayı barındırır. Render ücretsiz hizmeti boşta kaldığında uyuyabilir; ilk açılış gecikebilir. Ücretsiz sunucunun dosyaları yeniden başlatmada silinebilir: yalnızca ortak SUIS önbelleği yeniden hazırlanır, kullanıcıların tarayıcıdaki kayıtları etkilenmez. Kalıcı disk kullanırsanız `CACHE_DIR` yolunu ona yönlendirebilirsiniz.

Kaynaklar: [Render FastAPI](https://render.com/docs/deploy-fastapi), [ücretsiz hizmet sınırları](https://render.com/docs/free).

## Kontroller
```sh
python -m pytest -q
node tests/local-data.cjs
```

Karmaşık müfredat ve ön koşul kuralları otomatik doğrulanmış sayılmaz. Eksik alt kredi bilgisi tahmini sonuçlarda açıkça gösterilir. Program değiştirmek yeni bir yerel profil açar; mevcut kayıtlar silinmez.
