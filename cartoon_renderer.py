import asyncio
import math
from pathlib import Path

def render_cartoon_video(title, script, output_path, audio_path):
    """Render a simple original 2D cartoon with bobbing, blinking and talking mouth."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    from moviepy.editor import AudioFileClip, VideoClip
    import edge_tts
    from gtts import gTTS

    title = (title or "حكاية تونسية")[:90]
    script = " ".join((script or "").split())[:700]
    if len(script) < 8:
        raise ValueError("اكتب نصّ تونسي قصير قبل التصدير.")

    spoken = (title + ". " + script)[:700]
    audio = None
    try:
        async def make_voice():
            task = edge_tts.Communicate(spoken, voice="ar-TN-HediNeural", rate="+0%", volume="+0%")
            await asyncio.wait_for(task.save(str(audio_path)), timeout=22)
        asyncio.run(make_voice())
        if Path(audio_path).is_file() and Path(audio_path).stat().st_size > 1000:
            audio = AudioFileClip(str(audio_path))
    except Exception:
        audio = None
    if audio is None:
        try:
            gTTS(text=spoken, lang="ar", timeout=(5, 15)).save(str(audio_path))
            if Path(audio_path).is_file() and Path(audio_path).stat().st_size > 1000:
                audio = AudioFileClip(str(audio_path))
        except Exception:
            audio = None
    if audio is None:
        raise RuntimeError("ما نجّمش نولّد الصوت الآلي. تأكّد من اتصال الإنترنت وعاود.")

    W, H, fps = 540, 960, 15
    duration = min(24.0, max(6.0, float(audio.duration)))
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    try:
        title_font = ImageFont.truetype(font_path, 27)
        caption_font = ImageFont.truetype(font_path, 23)
        small_font = ImageFont.truetype(font_path, 18)
    except Exception:
        title_font = caption_font = small_font = ImageFont.load_default()

    words = script.split()
    chunks = [" ".join(words[i:i+7]) for i in range(0, len(words), 7)] or [title]
    def draw_frame(t):
        im = Image.new("RGB", (W, H), "#c6efff")
        d = ImageDraw.Draw(im)
        # cartoon outdoor scene
        d.ellipse((-100, 610, 640, 1120), fill="#83d69b")
        d.ellipse((390, 85, 485, 180), fill="#ffd75e")
        d.rounded_rectangle((22, 22, W-22, 108), radius=22, fill="#12233b")
        d.text((W//2, 64), title[:34], font=title_font, fill="white", anchor="mm", direction="rtl")
        bob = int(7 * math.sin(t * 5.0))
        cx, cy = 270, 420 + bob
        # legs and shoes
        d.line((cx-34, cy+185, cx-52, cy+260), fill="#26354d", width=25)
        d.line((cx+34, cy+185, cx+48, cy+260), fill="#26354d", width=25)
        d.ellipse((cx-88, cy+245, cx-25, cy+272), fill="#e85d43")
        d.ellipse((cx+18, cy+245, cx+82, cy+272), fill="#e85d43")
        # body / shirt
        d.rounded_rectangle((cx-92, cy+50, cx+92, cy+210), radius=48, fill="#ed684f", outline="#26354d", width=5)
        d.line((cx-80, cy+90, cx-135, cy+150+int(15*math.sin(t*4))), fill="#d89a6a", width=27)
        d.line((cx+80, cy+90, cx+132, cy+135-int(12*math.sin(t*4))), fill="#d89a6a", width=27)
        # ears and head
        d.ellipse((cx-108, cy-85, cx-68, cy-25), fill="#d89a6a", outline="#26354d", width=4)
        d.ellipse((cx+68, cy-85, cx+108, cy-25), fill="#d89a6a", outline="#26354d", width=4)
        d.ellipse((cx-92, cy-145, cx+92, cy+40), fill="#e9b17e", outline="#26354d", width=5)
        # hair
        d.pieslice((cx-96, cy-157, cx+96, cy-10), 180, 360, fill="#26354d")
        d.rectangle((cx-90, cy-90, cx+90, cy-55), fill="#26354d")
        # eyes blink occasionally
        blink = (int(t*2.2) % 7 == 0 and (t*2.2)%1 < 0.12)
        for ex in (cx-38, cx+38):
            if blink:
                d.line((ex-10, cy-60, ex+10, cy-60), fill="#26354d", width=5)
            else:
                d.ellipse((ex-13, cy-72, ex+13, cy-43), fill="white", outline="#26354d", width=3)
                d.ellipse((ex-5, cy-64, ex+5, cy-49), fill="#26354d")
        d.arc((cx-19, cy-47, cx+19, cy-12), 10, 165, fill="#8c4b37", width=4)
        # mouth movement synced approximately to speech duration
        talking = int(t*8) % 3
        if talking == 0:
            d.ellipse((cx-17, cy-6, cx+17, cy+17), fill="#742d3b", outline="#26354d", width=3)
        elif talking == 1:
            d.rounded_rectangle((cx-18, cy-4, cx+18, cy+8), radius=5, fill="#742d3b")
        else:
            d.line((cx-16, cy+3, cx+16, cy+3), fill="#26354d", width=4)
        # captions
        ci = min(len(chunks)-1, int(t / duration * len(chunks)))
        caption = chunks[ci]
        d.rounded_rectangle((24, 720, W-24, 850), radius=24, fill="#12233b", outline="#ffd75e", width=3)
        tokens, lines, line = caption.split(), [], ""
        for token in tokens:
            candidate = (line + " " + token).strip()
            if len(candidate) > 30 and line:
                lines.append(line); line = token
            else: line = candidate
        if line: lines.append(line)
        for i, ln in enumerate(lines[:3]):
            d.text((W//2, 758+i*32), ln, font=caption_font, fill="white", anchor="mm", direction="rtl")
        d.text((W//2, 900), "شخصية كرتونية تجريبية • تونس 🇹🇳", font=small_font, fill="#12233b", anchor="mm", direction="rtl")
        return np.array(im)

    video = None
    try:
        video = VideoClip(make_frame=draw_frame, duration=duration)
        audio_part = audio.subclip(0, min(duration, audio.duration))
        video = video.set_audio(audio_part)
        video.write_videofile(str(output_path), fps=fps, codec="libx264", audio_codec="aac",
                              preset="ultrafast", logger=None, threads=1,
                              ffmpeg_params=["-crf", "27"])
        if not Path(output_path).is_file() or Path(output_path).stat().st_size < 10000:
            raise RuntimeError("ملف MP4 الناتج ناقص أو فارغ.")
    finally:
        if video is not None:
            try: video.close()
            except Exception: pass
        if audio is not None:
            try: audio.close()
            except Exception: pass
        try: Path(audio_path).unlink(missing_ok=True)
        except Exception: pass
