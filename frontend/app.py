"""
ADIMLAR:
    1. Streamlit sayfa ayarlarını yap  (başlık, ikon, layout)
    2. Sayfa yüklenince günlük istatistikleri API'den çek
    3. Dashboard metrik kartlarını göster  (kazanç / toplam araç / aktif araç)
    4. Ayarlar panelini oluştur  (sadece saatlik ücret)
    5. Görüntü işleme bölümünü oluştur:
         a) Görsel sekmesi → canvas ile ROI çiz → YOLOv8 ile işle
         b) Video sekmesi  → ilk frame üzerinde ROI çiz → tüm video işle
    6. Tamamlanmış oturum listesini göster

KURULUM:
    1. Virtual environment oluşturun (henüz oluşturmadıysanız):
           python -m venv venv
    2. Virtual environment'ı aktif edin:
           - Windows : venv\\Scripts\\activate
           - Mac/Linux: source venv/bin/activate
    3. Bağımlılıkları yükle:
           pip install -r requirements.txt
    4. Uygulamayı başlat:
           streamlit run app.py
    5. Tarayıcıda otomatik açılır:
           http://localhost:8501

NOT:
    streamlit-drawable-canvas >= 1.35 Streamlit ile uyumsuz olduğundan
    image_to_url yama bloğu dosyanın en başında uygulanır.
    st.session_state: Sayfa her etkileşimde yeniden çalışır;
    bu veri tarayıcı oturumu boyunca bellekte tutulur.
"""

# =========================================================
# 0. streamlit-drawable-canvas uyumluluk yaması
#
#    st_canvas eski imzayla çağırır:
#      image_to_url(image, width:int, clamp, channels, output_format, image_id)
#
#    Yeni Streamlit ikinci parametreyi layout_config objesine taşıdı
#    ve clamp'i kaldırdı. inspect ile param listesi runtime'da okunur,
#    layout_config'den sonraki argümanlar dinamik olarak gönderilir.
# =========================================================
import inspect
import streamlit.elements.image as _st_img_elem

# image_to_url daha önce bağlanmadıysa bir kez çalıştır (tekrar sarmalamayı önler)
if not hasattr(_st_img_elem, "image_to_url"):
    from streamlit.elements.lib.image_utils import image_to_url as _base_itu

    # Yüklü Streamlit'in gerçek parametre isimlerini çalışma zamanında oku
    _itu_params = list(inspect.signature(_base_itu).parameters.keys())

    # "layout_config" varsa yeni Streamlit imzası, yoksa eski imza
    if "layout_config" in _itu_params:
        # Yeni imzada olmayan parametreler için kullanılacak varsayılan değerler
        _OLD_TO_NEW = {
            "channels":      "RGB",
            "output_format": "PNG",
            "image_id":      "",
            "clamp":         True,
        }

        # Eski imzayı (width, clamp, channels…) kabul eden, yeni imzaya çeviren sarmalayıcı
        def _compat_image_to_url(
            image,
            width=0,
            clamp=True,
            channels="RGB",
            output_format="PNG",
            image_id="",
            **kw,
        ):
            # width bir int değilse zaten yeni imzayla çağrılmış demektir, direkt ilet
            if not isinstance(width, int):
                return _base_itu(image, width, clamp, channels, output_format, image_id, **kw)

            # Yeni Streamlit'in beklediği layout_config nesnesini simüle et
            # (özel bir sınıf şart değil, duck-typing yeterli)
            class _LC:
                pass

            lc          = _LC()
            lc.width    = width    # eski width parametresi buraya taşındı
            lc.clamp    = clamp
            lc.channels = channels

            # layout_config'den sonra gelen parametreleri Streamlit'in beklediği
            # sıraya göre topla; sıra sürümden sürüme değişebildiği için dinamik yap
            extra = []
            for p in _itu_params[2:]:   # [0]=image ve [1]=layout_config'i atla
                if p == "channels":
                    extra.append(channels)
                elif p == "output_format":
                    extra.append(output_format)
                elif p == "image_id":
                    extra.append(image_id)
                elif p == "clamp":
                    extra.append(clamp)
                else:
                    # Bilinmeyen parametre gelirse varsayılan değerini kullan
                    extra.append(_OLD_TO_NEW.get(p))

            return _base_itu(image, lc, *extra)

        # Sarmalayıcıyı modüle bağla, artık her çağrı buraya gelecek
        _st_img_elem.image_to_url = _compat_image_to_url
    else:
        # Eski imza (6 ayrı parametre) — sarmalamaya gerek yok, direkt bağla
        _st_img_elem.image_to_url = _base_itu


# =========================================================
# 1. Streamlit sayfa ayarlarını yap
# =========================================================
import os
import tempfile

import cv2
import pandas as pd
import streamlit as st
from datetime import datetime
from PIL import Image as PILImage
from streamlit_drawable_canvas import st_canvas

from api_client import (
    get_daily_stats,
    get_active_vehicles,
    update_roi,
    update_pricing,
    process_frame,
    clear_database,
)

st.set_page_config(
    page_title="Otopark Kazanç Paneli",
    page_icon="🚗",
    layout="wide",
)


# =========================================================
# 2. Günlük istatistikleri API'den çek
# =========================================================
def _load_stats():
    """
    FastAPI üzerinden günlük istatistikleri ve aktif araç sayısını çekip
    session_state'e kaydeder. Hata durumunda session_state'e dokunulmaz.
    """
    try:
        st.session_state.stats  = get_daily_stats()
        st.session_state.active = get_active_vehicles()
    except Exception:
        pass


if "stats" not in st.session_state:
    _load_stats()

if "stats" not in st.session_state:
    st.error("⚠️ Backend'e bağlanılamadı. `uvicorn main:app --reload` komutunu çalıştırın.")
    if st.button("🔄 Yeniden Dene"):
        st.rerun()
    st.stop()

stats  = st.session_state.stats
active = st.session_state.active

st.title("🚗 Otopark Görüntü İşleme — Günlük Kazanç Paneli")


# =========================================================
# 3. Dashboard metrik kartları
# =========================================================
col1, col2, col3 = st.columns(3)
col1.metric("💰 Günlük Kazanç",   f"{stats['total_earnings']} TL")
col2.metric("🚘 Toplam Araç",      stats["total_vehicles"])
col3.metric("🔴 Şu An Otoparkta", active.get("count", 0))

st.divider()


# =========================================================
# 4. Ayarlar paneli — sadece fiyatlandırma (ROI canvas'a taşındı)
# =========================================================
st.subheader("⚙️ Ayarlar")

with st.container(border=True):
    st.markdown("**Fiyatlandırma**")
    hourly_rate = st.number_input("Saatlik Ücret (TL)", min_value=1.0, value=10.0, step=1.0)
    if st.button("Ücreti Güncelle", use_container_width=True):
        try:
            update_pricing(hourly_rate)
            st.toast("Ücret güncellendi!", icon="✅")
        except Exception:
            st.error("Güncelleme başarısız.")

with st.container(border=True):
    st.markdown("**Tehlikeli Alan**")
    if st.button("🗑 Veritabanını Temizle", use_container_width=True, type="primary"):
        if st.session_state.get("_db_confirm"):
            try:
                clear_database()
                st.session_state["_db_confirm"] = False
                _load_stats()
                st.toast("Veritabanı temizlendi!", icon="✅")
                st.rerun()
            except Exception as e:
                st.error(f"Temizleme başarısız: {e}")
        else:
            st.session_state["_db_confirm"] = True
            st.rerun()
    if st.session_state.get("_db_confirm"):
        st.warning("Emin misiniz? Tüm oturumlar silinecek. Onaylamak için tekrar basın.")

st.divider()


# =========================================================
# 5. Yardımcı: Kapı çizgisi canvas bileşeni
# =========================================================
def _canvas_to_coords(obj, sx: float, sy: float) -> list[int]:
    # Fabric.js Line: left/top = nesnenin MERKEZİ (originX/Y='center')
    # x1,y1,x2,y2 merkeze göre görelidir.
    x1   = obj.get("x1", 0)
    y1   = obj.get("y1", 0)
    x2   = obj.get("x2", 0)
    y2   = obj.get("y2", 0)
    left = obj.get("left",   0)
    top  = obj.get("top",    0)
    sc_x = obj.get("scaleX", 1)
    sc_y = obj.get("scaleY", 1)
    return [
        max(0, int((left + x1 * sc_x) * sx)),
        max(0, int((top  + y1 * sc_y) * sy)),
        max(0, int((left + x2 * sc_x) * sx)),
        max(0, int((top  + y2 * sc_y) * sy)),
    ]


def _draw_gate_preview(
    pil_img: PILImage.Image,
    gate_lines: list[list[int]],
    reverse_dirs: list[bool],
    canvas_w: int = 580,
) -> PILImage.Image:
    """Her çizgiyi turuncu çizer, kendi yönüne göre giriş/çıkış okları ekler."""
    import numpy as _np

    frame = cv2.cvtColor(_np.array(pil_img), cv2.COLOR_RGB2BGR)

    for i, gate_line in enumerate(gate_lines):
        x1, y1, x2, y2 = gate_line
        cv2.line(frame, (x1, y1), (x2, y2), (0, 165, 255), 4)
        cv2.putText(frame, f"#{i+1}", (x1, y1 - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 165, 255), 2)

        mx, my = (x1 + x2) // 2, (y1 + y2) // 2
        dx, dy = x2 - x1, y2 - y1
        length = max(1, (dx**2 + dy**2) ** 0.5)
        nx, ny = -dy / length, dx / length
        if i < len(reverse_dirs) and reverse_dirs[i]:
            nx, ny = -nx, -ny

        a = 35
        ax, ay = int(mx + nx * a), int(my + ny * a)
        bx, by = int(mx - nx * a), int(my - ny * a)
        cv2.arrowedLine(frame, (mx, my), (ax, ay), (0, 210, 0), 2, tipLength=0.4)
        cv2.putText(frame, "G", (ax + 4, ay + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 210, 0), 2)
        cv2.arrowedLine(frame, (mx, my), (bx, by), (0, 0, 210), 2, tipLength=0.4)
        cv2.putText(frame, "C", (bx + 4, by + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 210), 2)

    preview = PILImage.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    orig_w, orig_h = pil_img.size
    canvas_h = max(1, int(orig_h * canvas_w / orig_w))
    return preview.resize((canvas_w, canvas_h), PILImage.LANCZOS)

    
def gate_line_widget(
    pil_img: PILImage.Image,
    canvas_key: str,
    state_key: str,
    canvas_w: int = 580,
) -> tuple[list[list[int]], list[bool]]:
    """
    Birden fazla kapı çizgisi çizilir, her biri için bağımsız yön toggle'ı.

    Returns:
        (gate_lines, reverse_directions)
    """
    orig_w, orig_h = pil_img.size
    canvas_h       = max(1, int(orig_h * canvas_w / orig_w))
    sx             = orig_w / canvas_w
    sy             = orig_h / canvas_h

    gates_key = f"{state_key}_gates"
    revs_key  = f"{state_key}_revs"

    if st.button("🗑 Tüm Çizgileri Sil", use_container_width=True, key=f"{state_key}_clear_btn"):
        st.session_state[gates_key] = []
        st.session_state[revs_key]  = []
        st.rerun()

    st.caption("✏️ Tıkla & sürükle ile çizgi ekle — birden fazla çizebilirsin")

    result = st_canvas(
        fill_color="rgba(0,0,0,0)",
        stroke_width=2,
        stroke_color="#FFA500",
        background_image=pil_img,
        update_streamlit=True,
        width=canvas_w,
        height=canvas_h,
        drawing_mode="line",
        key=f"{canvas_key}_gate",
    )

    gate_lines: list[list[int]] = st.session_state.get(gates_key, [])
    rev_dirs:   list[bool]      = st.session_state.get(revs_key,  [])

    if result.json_data is not None:
        objs      = result.json_data.get("objects", [])
        all_lines = [o for o in objs if o.get("type") == "line"]
        new_gates = [_canvas_to_coords(o, sx, sy) for o in all_lines]
        if new_gates != gate_lines:
            # Yeni çizgiler eklendiyse rev listesini genişlet
            while len(rev_dirs) < len(new_gates):
                rev_dirs.append(False)
            rev_dirs = rev_dirs[:len(new_gates)]
            st.session_state[gates_key] = new_gates
            st.session_state[revs_key]  = rev_dirs
            gate_lines = new_gates

    if gate_lines:
        st.success(f"{len(gate_lines)} kapı çizgisi tanımlandı")

        # Her çizgi için bağımsız yön butonu
        for i in range(len(gate_lines)):
            rev = rev_dirs[i] if i < len(rev_dirs) else False
            label = f"Çizgi #{i+1} — {'↩ Ters' if rev else '↪ Düz'}  [R]"
            if st.button(label, key=f"{state_key}_rev_{i}"):
                rev_dirs[i] = not rev
                st.session_state[revs_key] = rev_dirs
                st.rerun()

        preview = _draw_gate_preview(pil_img, gate_lines, rev_dirs, canvas_w)
        st.image(preview, caption="Önizleme — G: Giriş  |  C: Çıkış", use_container_width=True)
    else:
        st.warning("Henüz kapı çizgisi çizilmedi")

    return gate_lines, rev_dirs


# =========================================================
# 5. Video işleme bölümü
# =========================================================
st.subheader("🎬 Video İşle")

video_file = st.file_uploader(
    "Video yükle (.mp4)",
    type=["mp4"],
    key="video_uploader",
)

if video_file:
    video_bytes = video_file.getvalue()

    # İlk frame'i bir kez çek ve session_state'e sakla
    frame_cache_key = f"_first_frame_{video_file.name}_{len(video_bytes)}"
    if frame_cache_key not in st.session_state:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
            tmp.write(video_bytes)
            tmp_path = tmp.name
        try:
            cap_tmp      = cv2.VideoCapture(tmp_path)
            ret, frame0  = cap_tmp.read()
            cap_tmp.release()
            if ret:
                st.session_state[frame_cache_key] = frame0
        finally:
            os.unlink(tmp_path)

    frame0 = st.session_state.get(frame_cache_key)

    if frame0 is not None:
        pil_first = PILImage.fromarray(cv2.cvtColor(frame0, cv2.COLOR_BGR2RGB))
        _skey     = f"_roi_{video_file.name}"
        gate_lines, reverse_dirs = gate_line_widget(
            pil_first,
            canvas_key=f"roi_vid_{video_file.name}",
            state_key=_skey,
        )

        target_fps = st.slider("İşlenecek FPS", min_value=1, max_value=15, value=5)

        start_btn = st.button(
            "▶️ Kapı Çizgilerini Uygula ve Videoyu İşle",
            use_container_width=True,
            disabled=not bool(gate_lines),
        )

        # Video özet sonuçları session_state'ten göster
        summary_key = f"_vid_summary_{video_file.name}"
        if summary_key in st.session_state:
            s = st.session_state[summary_key]
            st.success("✅ Video işleme tamamlandı!")
            r1, r2, r3, r4 = st.columns(4)
            r1.metric("🟢 Giriş",          s["entry"])
            r2.metric("🔴 Çıkış",           s["exit"])
            r3.metric("🚗 Tekil Araç",      s["unique"])
            r4.metric("🎞️ İşlenen Frame",   s["frames"])
            if s["all_events"]:
                with st.expander("Tüm olaylar"):
                    st.text("\n".join(s["all_events"]))

        if start_btn and gate_lines:
            st.session_state.pop(summary_key, None)
            update_roi(gate_lines, reverse_dirs)

            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp2:
                tmp2.write(video_bytes)
                proc_path = tmp2.name

            progress_bar  = st.progress(0, text="Hazırlanıyor...")
            frame_preview = st.empty()
            park_metric   = st.empty()
            event_log     = st.empty()
            all_events: list[str] = []
            entry_count   = 0
            exit_count    = 0
            unique_ids: set = set()

            try:
                cap          = cv2.VideoCapture(proc_path)
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                orig_fps     = max(1, cap.get(cv2.CAP_PROP_FPS))
                interval     = max(1, int(orig_fps / target_fps))
                frame_no     = 0
                sent_count   = 0

                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break

                    frame_no += 1
                    if frame_no % interval != 0:
                        continue

                    _, buf = cv2.imencode(".jpg", frame)
                    processed_bytes, events, parked = process_frame(buf.tobytes())

                    sent_count += 1
                    pct = min(int(frame_no / max(total_frames, 1) * 100), 100)
                    progress_bar.progress(
                        pct,
                        text=f"İşleniyor... {pct}%  ({sent_count} frame gönderildi)",
                    )

                    frame_preview.image(
                        processed_bytes,
                        caption=f"Frame {frame_no}",
                        use_container_width=True,
                    )

                    park_metric.metric("🅿️ Park Eden Araç", parked)

                    for ev in events:
                        unique_ids.add(ev["vehicle_id"])
                        if ev["event"] == "entry":
                            entry_count += 1
                            all_events.append(f"🟢 GİRİŞ | ID:{ev['vehicle_id']} {ev['vehicle_type']}")
                        else:
                            exit_count += 1
                            all_events.append(f"🔴 ÇIKIŞ | ID:{ev['vehicle_id']} {ev['vehicle_type']}")
                    event_log.text("\n".join(all_events[-10:]))

                cap.release()
                progress_bar.progress(100, text="Tamamlandı ✅")

                # Özeti session_state'e kaydet, rerun sonrası gösterilecek
                st.session_state[summary_key] = {
                    "entry":      entry_count,
                    "exit":       exit_count,
                    "unique":     len(unique_ids),
                    "frames":     sent_count,
                    "all_events": all_events,
                }
                _load_stats()
                st.rerun()

            except Exception as e:
                st.error(f"Video işlenemedi: {e}")
            finally:
                os.unlink(proc_path)


# =========================================================
# 6. Tamamlanan oturum listesi
# =========================================================
st.subheader(f"📋 {stats['date']} Tamamlanan Oturumlar")

sessions = stats.get("sessions", [])
if not sessions:
    st.info("Bugün henüz tamamlanmış oturum yok.")
else:
    df = pd.DataFrame(sessions)
    df = df[["vehicle_id", "vehicle_type", "entry_time", "exit_time", "duration_minutes", "fee"]]
    df.columns = ["ID", "Tür", "Giriş", "Çıkış", "Süre (dk)", "Ücret (TL)"]
    st.dataframe(df, use_container_width=True)

vehicles = active.get("vehicles", [])
if vehicles:
    st.subheader("🟢 Şu An Otoparkta")
    active_df = pd.DataFrame(vehicles)
    st.dataframe(
        active_df[["vehicle_id", "vehicle_type", "entry_time"]],
        use_container_width=True,
    )

st.divider()
st.caption(f"Son güncelleme: {datetime.now().strftime('%H:%M:%S')}")
if st.button("🔄 Yenile"):
    _load_stats()
    st.rerun()
