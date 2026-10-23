import asyncio
from pathlib import Path

def render_stock_video(video_paths, title, script, output_path, audio_path):
    """Join uploaded stock clips into a vertical short with narration and burned-in captions."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    from moviepy.editor import (
        VideoFileClip, AudioFileClip, ImageClip, CompositeVideoClip,
        concatenate_videoclips, vfx
    )
    import edge_tts
    from gtts import gTTS

    W, H = 540, 960
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    try:
        title_font = ImageFont.truetype(font_path, 28)
        caption_font = ImageFont.truetype(font_path, 24)
    except Exception:
        title_font = caption_font = ImageFont.load_default()

    raw_clips = []
    prepared = []
    audio = None
    final = None
    try:
        for path in video_paths[:2]:
            clip = VideoFileClip(str(path), audio=False)
            raw_clips.append(clip)
            # Keep decoding and compositing light for free-tier memory limits.
            clip = clip.subclip(0, min(clip.duration, 5))
            clip = clip.resize(height=960)
            if clip.w < 540:
                clip = clip.resize(width=540)
            clip = clip.crop(x_center=clip.w / 2, y_center=clip.h / 2, width=540, height=960)
            prepared.append(clip)

        if not prepared:
            raise ValueError("حمّل على الأقل مقطع فيديو واحد.")

        joined = concatenate_videoclips(prepared, method="compose")
        spoken_text = (title + ". " + script)[:900]
        try:
            async def make_voice():
                communicate = edge_tts.Communicate(
                    spoken_text, voice="ar-TN-HediNeural", rate="+0%", volume="+0%"
                )
                await asyncio.wait_for(communicate.save(str(audio_path)), timeout=18)
            asyncio.run(make_voice())
            if not Path(audio_path).is_file() or Path(audio_path).stat().st_size < 1000:
                raise RuntimeError("Tunisian voice was not generated")
            audio = AudioFileClip(str(audio_path))
        except Exception:
            try:
                gTTS(text=spoken_text, lang="ar").save(str(audio_path))
                audio = AudioFileClip(str(audio_path))
            except Exception:
                audio = None

        duration = min(30, max(8, audio.duration if audio is not None else min(joined.duration, 20)))
        if joined.duration < duration:
            base = joined.fx(vfx.loop, duration=duration)
        else:
            base = joined.subclip(0, duration)
        layers = [base]

        # Title banner.
        banner = Image.new("RGBA", (W, 90), (9, 16, 30, 170))
        d = ImageDraw.Draw(banner)
        d.text((W // 2, 45), title[:45], font=title_font, fill=(255, 255, 255, 255),
               anchor="mm", direction="rtl", stroke_width=1, stroke_fill=(0, 0, 0, 220))
        title_layer = ImageClip(np.array(banner), transparent=True).set_duration(duration).set_position(("center", 25))
        layers.append(title_layer)

        # Burn in short caption chunks, timed across the narration/video.
        words = script.split()
        chunks = [" ".join(words[i:i+7]) for i in range(0, len(words), 7)] or [title]
        caption_duration = duration / len(chunks)
        for i, chunk in enumerate(chunks):
            canvas = Image.new("RGBA", (W, 150), (0, 0, 0, 0))
            d = ImageDraw.Draw(canvas)
            # Keep each caption to two lines for a phone screen.
            tokens = chunk.split()
            lines, line = [], ""
            for token in tokens:
                candidate = (line + " " + token).strip()
                if len(candidate) > 30 and line:
                    lines.append(line)
                    line = token
                else:
                    line = candidate
            if line:
                lines.append(line)
            lines = lines[:2]
            d.rounded_rectangle((18, 15, W-18, 135), radius=22, fill=(0, 0, 0, 175),
                                outline=(244, 185, 66, 230), width=2)
            for j, text in enumerate(lines):
                d.text((W // 2, 52 + j * 38), text, font=caption_font, fill="white",
                       anchor="mm", direction="rtl", stroke_width=1, stroke_fill=(0, 0, 0, 180))
            layer = (ImageClip(np.array(canvas), transparent=True)
                     .set_start(i * caption_duration)
                     .set_duration(min(caption_duration + 0.04, duration - i * caption_duration))
                     .set_position(("center", 720)))
            layers.append(layer)

        final = CompositeVideoClip(layers, size=(W, H)).set_duration(duration)
        if audio is not None:
            final = final.set_audio(audio.set_duration(duration) if audio.duration >= duration else audio.set_duration(audio.duration))
        final.write_videofile(str(output_path), fps=15, codec="libx264", audio_codec="aac",
                              preset="ultrafast", logger=None, threads=1, ffmpeg_params=["-crf", "28"])
    finally:
        if final is not None:
            try: final.close()
            except Exception: pass
        if audio is not None:
            try: audio.close()
            except Exception: pass
        for clip in raw_clips:
            try: clip.close()
            except Exception: pass
        for clip in prepared:
            try: clip.close()
            except Exception: pass
