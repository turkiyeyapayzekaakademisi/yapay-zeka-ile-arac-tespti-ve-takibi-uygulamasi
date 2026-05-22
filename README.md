# Yapay Zeka ile Araç Tespiti ve Takibi Uygulaması

YOLOv8, FastAPI, PostgreSQL, Streamlit, Docker ve Railway kullanarak
uçtan uca bir trafik takip ve araç sayım uygulaması.

---

## Proje Akışı

```
YOLOv8 → PostgreSQL → FastAPI → Streamlit → Docker → Deploy
```

Her adım bir öncekinin üzerine inşa edilir. Adımları sırayla takip edin.

---

## Adım 1 —  YOLO ile Araç Tespiti ve Takibi Algoritmaları Geliştirme

**Ne yapacağız?**
Gerçek bir trafik videosu üzerinde araçları tespit edip takip edeceğiz.
Giriş/çıkış çizgisi çizerek araçların çizgiyi hangi yönde geçtiğini
algılayacağız. Park eden araçları otomatik olarak tespit edeceğiz.

**Dosya:** `backend/app/services/detection_service.py`

**Ne öğreneceğiz?**
- `ultralytics` ve `opencv-python` kurulumu
- `YOLO("yolov8n.pt")` ile model yükleme ve ilk görsel tespiti
- `model.track(persist=True)` ile nesne takibi ve ID atama
- Vektörel çizgi geçiş algoritması (cross product)
- Hareketsizlik tespiti ile otomatik park algılama
- `cv2.imshow` ile gerçek zamanlı görselleştirme

**Test:**
```bash
cd backend

# Tek görsel ile test (2.2 + 2.3)
python app/services/detection_service.py --image araba.jpg

# Video ile test (2.4)
python app/services/detection_service.py --video trafik.mp4

# Giriş/çıkış çizgisi ile test (2.5 + 2.6)
python app/services/detection_service.py --video trafik.mp4 --line 100,300,540,300

# İşlenmiş videoyu kaydet (2.7)
python app/services/detection_service.py --video trafik.mp4 --line 100,300,540,300 --save
```

## Adım 2- PostgreSQL ile Araç Oturumlarını Kaydetme

**Ne yapacağız?**
Her araç giriş/çıkış yaptığında veya park haline geçitğinde oturum bilgilerini (süre, ücret, araç, tpi)
veritabanına kaydedeceğiz. Böylece geçmiş bilgileri güvenle tutup istenildiği zaman istatistik halinde dönebilceğiz.

**Dosyalar:**
- `backend/app/core/config.py` - ortam değişkenlerimi okuyacak
- `backend/app/db/database.py` - async engine, session, get_db
- `backend/app/models/parking.py` - vehicle_sessions tablosu ORM modeli

**Ne öğreneceğiz?**
- Pydatnic Settings ile `.env` dosyasından config okuma
- SQLALchemy async engine kurulumu
- ORM model tanımlama
- Async session yönetimi 

**Bağlantı string formatı:**

postgresql+asyncpg://kullanici:sifre@host:5432/veritabanı_ismi

## Adım 3 - FastAPI ile Backend Servisi Geliştirme

**Ne yapacağız?**

Yolo ve Postgresql servislerini bir REST API ile birbirlerine bağlyacağız. Video framelerini alacak ve istatistikler çekecek bir endpoint yazacağız.

**Dosyalar:**

- `backend/main.py` -> uygulamanın giriş noktası, CORS, lifespan
- `backend/app/schemas/schemas.py` -> request/response şemalarını 
- `backend/app/api/routes/parking.py` -> endpoint tanımları
- `backend/app/services/parking_service.py` - Bussines Logic

**Ne öğreneceğiz?**
- FastAPI kurulumu ve async uygulama oluşturma
- `UploadFile` ile görüntü stream alma ve işleme
- Pydantic ile otomatik veri doğrulama
- CORS  middleware 
- `lifespan` ile uygulama başlangıcında model yükleme


## Adım 4 - Streamlit ile Kullanıcı Arayüzü Geliştirme

**Ne yapacağız?**

Kullanıcnın video yükleyip giriş/çıkış çizgisi çizebildiği, işlem sırasında canlı görüntü ve istatisitk görebildiği bir web arayüzü oluşturacağız.

**Dosyalar:**

- `frontend/api_client.py` - FastAPIye HTTP isteklerini atacak
- `frotend/app.py` - dashboard, canvas ve video işleme akışını

**Ne öğreneceğiz?**

- Streamlit kurmayı ve `streamlit run` komutunu
- `session_state` ile sayfa yenilenince veriyi korumayı
- `streamlit-drawable-canvas` ile interaktif çizgi çizmeyi
- `requests` kütüphanesi ile FastAPIya istek atmayı

# Adım 5 - Docker ile Paketleme

**Ne yapacağız?**

Tüm servisleri (PostgreSQL, FastAPI, Streamlit) Docker containerlarına paketleyeceğiz. 

**Dosyalar:**
- `backend/Dockerfile`
- `frontend/Dockerfile`
- `docker-compose.yml`

**Neler Öğreneceğiz?**
- `Dockerfile` yazımı
- Docker layer cache mantığı
- `docker-compose.yml` ile çok servisli yapı kurma
- Servisler arası iletişim
- Volume kullnamını

## Adım 6 - Deploy (Railway)

**Ne yapacağız?**

Uygulamayı Railsway üzerinde deploy edeceğiz. Backend Frotend ve Veritabanı servislerini ayrı ayrı çalıştırıp
Public bir domain üzerinden ulaşılabilir yapacağız.

**Ne Öğreneceğiz?**
- Railway üzerinden monorepo yapısıyla çoklu servis deploy etme
- Root directory ile farklı klasörleri ayrı servislere bağlama
- Ortam değişkenlerinin Railway Referenced syntax ile yazılımı
- Dockerfile'ı platform-agnostic hale getirmeyi

# yapay-zeka-ile-arac-tespti-ve-takibi-uygulamasi
