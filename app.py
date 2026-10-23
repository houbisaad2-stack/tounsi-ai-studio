import os, re, tempfile, uuid
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 110 * 1024 * 1024
OUTPUT_DIR = Path(tempfile.gettempdir()) / "tounsi-ai-studio"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def clean_text(value, max_len=1600):
    return re.sub(r"\s+", " ", (value or "").strip())[:max_len]

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/health")
def health():
    return {"status": "ok", "app": "Tounsi AI Studio"}

@app.post("/api/script")
def make_script():
    data = request.get_json(silent=True) or {}
    topic = clean_text(data.get("topic"), 180) or "موقف تونسي يضحّك"
    mode = clean_text(data.get("mode"), 30) or "كوميديا تونسية"
    if mode == "كوميديا تونسية":
        script = f"""العنوان: {topic}

المشهد 1 — البداية:
واحد تونسي دخل للقهوة وقال للڨارسون: «عسلامة، عندك حاجة تفرّح القلب؟»
الڨارسون قالّو: «إي، الفاتورة متاع البارح خلّصها وتفرح!»

المشهد 2 — التصعيد:
قالّو: «ياخي حتى القهوة ولات عندها ذاكرة؟»
قالّو الڨارسون: «القهوة لا، أمّا الكاميرا عندها!»

الخاتمة:
التونسي شاف في الكاميرا وقال: «يا جماعة، حتى القهوة ولات تعمل فيّا محتوى!»
"""
    elif mode == "محتوى ديني":
        script = f"""العنوان: {topic}

رسالة قصيرة:
في زحمة الحياة، ما تنساش اللي الكلمة الطيبة صدقة، والفرج يجي مع الصبر والعمل.
خذ دقيقة اليوم باش تذكر ربي، تصلح خاطرك مع إنسان، وتعمل خير حتى لو صغير.

الخاتمة:
إذا الرسالة لمستك، شاركها مع شخص يحب يسمع كلمة طيبة.
"""
    else:
        script = f"""العنوان: {topic}

مقدمة:
اليوم باش نتعلّموا فكرة بسيطة ومفيدة: {topic}.

الفكرة الأولى:
قسّم الموضوع لخطوات صغيرة، وابدأ بأسهل خطوة تنجم تعملها اليوم.

الفكرة الثانية:
طبّق اللي تعلّمتو، وراجع النتيجة. التقدّم الصغير كل يوم خير من الانتظار.

الخاتمة:
احفظ الفيديو وارجع طبّق الخطوات، وابعثو لشخص ينجم يستفيد.
"""
    return jsonify({"title": topic[:90], "script": script.strip(), "note": "هذا نصّ أولي مولّد بقوالب محلية، موش اتصال بخدمة ذكاء اصطناعي مدفوعة."})

@app.post("/api/render")
def render_video():
    data = request.get_json(silent=True) or {}
    title = clean_text(data.get("title"), 120) or "Tounsi AI Studio"
    script = clean_text(data.get("script"), 1500)
    if len(script) < 10:
        return jsonify({"error": "اكتب نصّ الفيديو قبل التصدير."}), 400
    try:
        from PIL import Image, ImageDraw, ImageFont
        import numpy as np
        from moviepy.editor import ImageClip, AudioFileClip
        from gtts import gTTS
        import asyncio
        import edge_tts
    except Exception as exc:
        return jsonify({"error": "مكتبات الفيديو غير جاهزة على الخادم. راجع سجلّات Render. " + str(exc)[:160]}), 500
    uid = uuid.uuid4().hex[:12]
    mp4_path = OUTPUT_DIR / f"tounsi_{uid}.mp4"
    audio_path = OUTPUT_DIR / f"tounsi_{uid}.mp3"
    W, H = 720, 1280
    image = Image.new("RGB", (W, H), "#101827")
    draw = ImageDraw.Draw(image)
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    try:
        title_font = ImageFont.truetype(font_path, 38)
        body_font = ImageFont.truetype(font_path, 25)
        small_font = ImageFont.truetype(font_path, 18)
    except Exception:
        title_font = body_font = small_font = ImageFont.load_default()
    draw.rounded_rectangle((28, 28, W-28, H-28), radius=32, outline="#f4b942", width=3)
    draw.text((W//2, 92), "TOUNSI AI STUDIO", font=small_font, fill="#f4b942", anchor="mm")
    draw.text((W//2, 170), title[:50], font=title_font, fill="white", anchor="mm")
    lines, current = [], ""
    for word in script.split():
        candidate = (current + " " + word).strip()
        if len(candidate) > 30:
            if current: lines.append(current)
            current = word
        else:
            current = candidate
    if current: lines.append(current)
    y = 280
    for line in lines[:19]:
        draw.text((W//2, y), line, font=body_font, fill="#e5e7eb", anchor="mm")
        y += 42
    draw.text((W//2, H-105), "تابعنا للمزيد", font=small_font, fill="#f4b942", anchor="mm", direction="rtl")
    frame = np.array(image)
    audio = None
    clip = None
    try:
        # Audio is optional: if the free text-to-speech service is unreachable,
        # still create a valid MP4 instead of failing the entire export.
        try:
            # Prefer Microsoft's Tunisian Arabic male voice when the free Edge TTS endpoint is reachable.
            spoken_text = (title + ". " + script)[:900]
            async def save_tunisian_voice():
                communicate = edge_tts.Communicate(spoken_text, voice="ar-TN-HediNeural", rate="+0%", volume="+0%")
                await communicate.save(str(audio_path))
            asyncio.run(save_tunisian_voice())
            audio = AudioFileClip(str(audio_path))
        except Exception:
            # Compatibility fallback: generic Arabic TTS; it may not sound Tunisian.
            try:
                gTTS(text=(title + ". " + script)[:900], lang="ar").save(str(audio_path))
                audio = AudioFileClip(str(audio_path))
            except Exception:
                audio = None
        duration = (audio.duration + 0.4) if audio is not None else max(8, min(45, len(script.split()) / 2.2))
        clip = ImageClip(frame).set_duration(duration)
        if audio is not None:
            clip = clip.set_audio(audio)
        clip.write_videofile(str(mp4_path), fps=24, codec="libx264", audio_codec="aac", logger=None, threads=2)
    except Exception as exc:
        for p in (mp4_path, audio_path):
            try: p.unlink(missing_ok=True)
            except Exception: pass
        return jsonify({"error": "تعذّر تركيب ملف MP4 على الخادم: " + str(exc)[:220]}), 500
    finally:
        try:
            if clip is not None: clip.close()
        except Exception: pass
        try:
            if audio is not None: audio.close()
        except Exception: pass
    try: audio_path.unlink(missing_ok=True)
    except Exception: pass
    return jsonify({"download_url": f"/download/{mp4_path.name}", "preview_url": f"/preview/{mp4_path.name}", "filename": mp4_path.name, "message": "الفيديو جاهز! تنجم تتفرّج فيه من المعاينة ولا تهبطو."})


@app.post("/api/render-stock")
def render_stock():
    from werkzeug.utils import secure_filename
    import tempfile
    data_title = clean_text(request.form.get("title"), 120) or "Tounsi AI Studio"
    script = clean_text(request.form.get("script"), 1500)
    uploads = [f for f in request.files.getlist("clips") if f and f.filename]
    if len(uploads) < 1:
        return jsonify({"error": "حمّل مقطع فيديو واحد على الأقل من Pexels."}), 400
    if len(uploads) > 4:
        return jsonify({"error": "اختار 4 مقاطع كحدّ أقصى في المرّة."}), 400
    if len(script) < 10:
        return jsonify({"error": "حضّر النصّ قبل إنشاء الفيديو."}), 400
    allowed = {".mp4", ".mov", ".webm", ".m4v"}
    for f in uploads:
        suffix = Path(secure_filename(f.filename)).suffix.lower()
        if suffix not in allowed:
            return jsonify({"error": "الملفات المقبولة: MP4 أو MOV أو WEBM."}), 400
    uid = uuid.uuid4().hex[:12]
    mp4_path = OUTPUT_DIR / f"tounsi_{uid}.mp4"
    audio_path = OUTPUT_DIR / f"voice_{uid}.mp3"
    try:
        with tempfile.TemporaryDirectory(prefix="tounsi-stock-") as temp_dir:
            input_paths = []
            for index, file in enumerate(uploads):
                path = Path(temp_dir) / f"clip_{index}{Path(secure_filename(file.filename)).suffix.lower()}"
                file.save(path)
                if path.stat().st_size > 25 * 1024 * 1024:
                    return jsonify({"error": "كل مقطع لازم يكون أقل من 25 ميغابايت."}), 413
                input_paths.append(path)
            from stock_renderer import render_stock_video
            render_stock_video(input_paths, data_title, script, mp4_path, audio_path)
        try: audio_path.unlink(missing_ok=True)
        except Exception: pass
        if not mp4_path.is_file() or mp4_path.stat().st_size < 10000:
            raise RuntimeError("ملف الفيديو النهائي ما تخلقش بالشكل الصحيح.")
        return jsonify({"download_url": f"/download/{mp4_path.name}", "preview_url": f"/preview/{mp4_path.name}", "filename": mp4_path.name, "message": "الفيديو بالمشاهد جاهز للمعاينة والتنزيل."})
    except Exception as exc:
        for path in (mp4_path, audio_path):
            try: path.unlink(missing_ok=True)
            except Exception: pass
        return jsonify({"error": "تعذّر تركيب مشاهد الفيديو: " + str(exc)[:220]}), 500

@app.get("/preview/<name>")
def preview(name):
    if not re.fullmatch(r"tounsi_[a-f0-9]{12}\.mp4", name):
        return "Not found", 404
    path = OUTPUT_DIR / name
    if not path.is_file():
        return "انتهت صلاحية الملف أو لم يعد موجودًا. أنشئ الفيديو من جديد.", 404
    return send_file(path, as_attachment=False, mimetype="video/mp4", conditional=True)

@app.get("/download/<name>")
def download(name):
    if not re.fullmatch(r"tounsi_[a-f0-9]{12}\.mp4", name):
        return "Not found", 404
    path = OUTPUT_DIR / name
    if not path.is_file():
        return "انتهت صلاحية الملف أو لم يعد موجودًا. أنشئ الفيديو من جديد.", 404
    return send_file(path, as_attachment=True, download_name="tounsi-ai-studio.mp4", mimetype="video/mp4")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
