from pathlib import Path

def render_image_video(image_paths, title, script, output_path, audio_path):
    import asyncio
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    from moviepy.editor import ImageClip, AudioFileClip, CompositeVideoClip, concatenate_videoclips, vfx
    from gtts import gTTS
    import edge_tts

    W, H = 720, 1280
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    try:
        title_font = ImageFont.truetype(font_path, 34)
        cap_font = ImageFont.truetype(font_path, 30)
    except Exception:
        title_font = cap_font = ImageFont.load_default()

    audio = final = None
    clips = []
    try:
        spoken = (title + ". " + script)[:900]
        try:
            async def voice():
                task = edge_tts.Communicate(spoken, voice="ar-TN-HediNeural")
                await asyncio.wait_for(task.save(str(audio_path)), timeout=18)
            asyncio.run(voice())
            audio = AudioFileClip(str(audio_path))
        except Exception:
            try:
                gTTS(text=spoken, lang="ar").save(str(audio_path))
                audio = AudioFileClip(str(audio_path))
            except Exception:
                audio = None

        for path in image_paths[:8]:
            im = Image.open(path).convert("RGB")
            # Fill a 9:16 canvas without stretching the image.
            scale = max(W / im.width, H / im.height)
            im = im.resize((int(im.width * scale), int(im.height * scale)))
            left = max(0, (im.width - W) // 2)
            top = max(0, (im.height - H) // 2)
            im = im.crop((left, top, left + W, top + H))
            d = ImageDraw.Draw(im, "RGBA")
            d.rounded_rectangle((18, 24, W-18, 105), radius=18, fill=(5, 12, 25, 180))
            d.text((W//2, 64), title[:42], font=title_font, fill="white", anchor="mm", direction="rtl")
            clips.append(ImageClip(np.array(im)))
        if not clips:
            raise ValueError("ما فما حتى صورة صالحة.")
        duration = min(45, max(8, audio.duration if audio is not None else len(clips)*3))
        per = duration / len(clips)
        clips = [c.set_duration(per).fx(vfx.fadein, 0.2).fx(vfx.fadeout, 0.2) for c in clips]
        slideshow = concatenate_videoclips(clips, method="compose")
        words = script.split()
        chunks = [" ".join(words[i:i+7]) for i in range(0, len(words), 7)] or [title]
        layers = [slideshow]
        for i, chunk in enumerate(chunks):
            canvas = Image.new("RGBA", (W, 190), (0,0,0,0))
            d = ImageDraw.Draw(canvas)
            d.rounded_rectangle((20, 18, W-20, 170), radius=20, fill=(0,0,0,185), outline=(244,185,66,230), width=2)
            words2, lines, line = chunk.split(), [], ""
            for word in words2:
                test = (line+" "+word).strip()
                if len(test)>30 and line:
                    lines.append(line); line=word
                else: line=test
            if line: lines.append(line)
            for j, line in enumerate(lines[:2]):
                d.text((W//2, 65+j*45), line, font=cap_font, fill="white", anchor="mm", direction="rtl")
            start = i * duration / len(chunks)
            layer = ImageClip(np.array(canvas), transparent=True).set_start(start).set_duration(min(duration-start, duration/len(chunks)+0.03)).set_position(("center", 960))
            layers.append(layer)
        final = CompositeVideoClip(layers, size=(W,H)).set_duration(duration)
        if audio is not None:
            final = final.set_audio(audio.set_duration(min(audio.duration,duration)))
        final.write_videofile(str(output_path), fps=24, codec="libx264", audio_codec="aac", preset="ultrafast", logger=None, threads=2)
    finally:
        if final:
            try: final.close()
            except Exception: pass
        if audio:
            try: audio.close()
            except Exception: pass
        for c in clips:
            try: c.close()
            except Exception: pass
