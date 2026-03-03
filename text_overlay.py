"""
Text Overlay Module for StoryBook Generator.
Draws story text inside semi-transparent speech bubbles directly on the
illustration.  No canvas extension — output dimensions match the input image.
"""

import os
import textwrap
from PIL import Image, ImageDraw, ImageFont
from config import Config


class TextOverlay:
    """Adds speech-bubble text overlays to storybook illustrations."""

    # Fallback font paths for different operating systems
    FONT_PATHS = [
        # macOS
        "/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
        # Linux
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        # Windows
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]

    def __init__(self):
        self.font_path = self._find_font()

    def _find_font(self) -> str | None:
        """Find an available system font."""
        for path in self.FONT_PATHS:
            if os.path.exists(path):
                return path
        return None

    def _get_font(self, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        """Get a font at the specified size."""
        if self.font_path:
            try:
                return ImageFont.truetype(self.font_path, size)
            except Exception:
                pass
        return ImageFont.load_default(size=size)

    # ------------------------------------------------------------------
    # Text wrapping
    # ------------------------------------------------------------------

    def _wrap_text(
        self, text: str, font: ImageFont.FreeTypeFont, max_width: int
    ) -> tuple[list[str], int, int]:
        """
        Wrap *text* so each line fits within *max_width* pixels.

        Returns:
            (lines, total_height, line_height)
        """
        avg_char_width = font.getlength("A")
        chars_per_line = max(10, int(max_width / avg_char_width))
        lines = textwrap.wrap(text, width=chars_per_line)
        line_height = font.size + 8
        total_height = len(lines) * line_height
        return lines, total_height, line_height

    # ------------------------------------------------------------------
    # Drawing primitives
    # ------------------------------------------------------------------

    def _draw_rounded_rect_with_shadow(
        self,
        draw: ImageDraw.Draw,
        bbox: tuple[int, int, int, int],
        radius: int,
        fill: tuple,
        outline: tuple,
        outline_width: int = 2,
        shadow_offset: int = 4,
        shadow_color: tuple = (80, 60, 40, 40),
    ):
        """Draw a rounded rectangle with a subtle drop-shadow behind it."""
        x0, y0, x1, y1 = bbox

        # Shadow (shifted down-right)
        draw.rounded_rectangle(
            (x0 + shadow_offset, y0 + shadow_offset,
             x1 + shadow_offset, y1 + shadow_offset),
            radius=radius,
            fill=shadow_color,
        )

        # Main rectangle
        draw.rounded_rectangle(
            bbox,
            radius=radius,
            fill=fill,
            outline=outline,
            width=outline_width,
        )

    # ------------------------------------------------------------------
    # Speech bubble (bottom of image)
    # ------------------------------------------------------------------

    def _draw_speech_bubble(
        self,
        draw: ImageDraw.Draw,
        img_size: tuple[int, int],
        text: str,
        font: ImageFont.FreeTypeFont,
        moral_text: str | None = None,
        moral_font: ImageFont.FreeTypeFont | None = None,
    ):
        """
        Draw a speech bubble in the lower portion of the image containing
        *text* and an optional *moral_text* footer.
        """
        img_w, img_h = img_size
        padding = Config.TEXT_PADDING
        margin_bottom = 35
        tail_h = 18
        bubble_radius = 25
        max_text_width = img_w - padding * 4  # generous horizontal margin

        # --- measure body text ---
        body_lines, body_h, body_lh = self._wrap_text(text, font, max_text_width)

        # --- measure moral (optional) ---
        moral_lines: list[str] = []
        moral_h = 0
        moral_lh = 0
        separator_h = 0
        if moral_text and moral_font:
            moral_lines, moral_h, moral_lh = self._wrap_text(
                f"\u2728 {moral_text} \u2728", moral_font, max_text_width
            )
            separator_h = 24  # space for the decorative line

        # --- bubble dimensions ---
        content_h = body_h + separator_h + moral_h
        bubble_h = content_h + padding * 2
        bubble_w = min(img_w - padding * 2, max_text_width + padding * 2)

        bubble_x0 = (img_w - bubble_w) // 2
        bubble_y1 = img_h - margin_bottom - tail_h
        bubble_y0 = bubble_y1 - bubble_h
        bubble_x1 = bubble_x0 + bubble_w
        bbox = (bubble_x0, bubble_y0, bubble_x1, bubble_y1)

        # --- draw shadow + rounded rect ---
        fill = (255, 255, 255, 210)
        outline = (160, 145, 125, 240)
        self._draw_rounded_rect_with_shadow(draw, bbox, bubble_radius, fill, outline)

        # --- triangular tail ---
        tail_cx = bubble_x0 + bubble_w // 4  # left-of-centre
        tail_points = [
            (tail_cx - 12, bubble_y1),      # left base on bubble edge
            (tail_cx + 12, bubble_y1),      # right base on bubble edge
            (tail_cx - 6, bubble_y1 + tail_h),  # tip pointing down-left
        ]
        # Shadow for tail
        shadow_offset = 4
        shadow_tail = [(x + shadow_offset, y + shadow_offset) for x, y in tail_points]
        draw.polygon(shadow_tail, fill=(80, 60, 40, 40))
        # Main tail
        draw.polygon(tail_points, fill=fill, outline=outline)
        # Cover the outline overlap on the bubble's bottom edge
        draw.line(
            (tail_cx - 11, bubble_y1, tail_cx + 11, bubble_y1),
            fill=fill,
            width=3,
        )

        # --- render body text ---
        text_color = (60, 45, 25)
        cur_y = bubble_y0 + padding
        for line in body_lines:
            lw = font.getlength(line)
            x = bubble_x0 + (bubble_w - lw) // 2
            draw.text((x, cur_y), line, font=font, fill=text_color)
            cur_y += body_lh

        # --- render moral footer ---
        if moral_lines:
            # decorative separator
            sep_y = cur_y + separator_h // 2
            sep_margin = 40
            draw.line(
                (bubble_x0 + sep_margin, sep_y, bubble_x1 - sep_margin, sep_y),
                fill=(160, 145, 125, 180),
                width=1,
            )
            cur_y += separator_h

            moral_color = (139, 90, 43)
            for line in moral_lines:
                lw = moral_font.getlength(line)
                x = bubble_x0 + (bubble_w - lw) // 2
                draw.text((x, cur_y), line, font=moral_font, fill=moral_color)
                cur_y += moral_lh

    # ------------------------------------------------------------------
    # Title banner (top of image, first scene only)
    # ------------------------------------------------------------------

    def _draw_title_banner(
        self,
        draw: ImageDraw.Draw,
        img_size: tuple[int, int],
        title: str,
        font: ImageFont.FreeTypeFont,
    ):
        """Draw a warm banner bubble at the top of the image with the title."""
        img_w, _img_h = img_size
        padding = Config.TEXT_PADDING
        margin_top = 30
        banner_radius = 25
        max_text_width = img_w - padding * 4

        lines, text_h, line_h = self._wrap_text(title, font, max_text_width)

        banner_h = text_h + padding * 2
        banner_w = min(img_w - padding * 2, max_text_width + padding * 2)

        bx0 = (img_w - banner_w) // 2
        by0 = margin_top
        bx1 = bx0 + banner_w
        by1 = by0 + banner_h
        bbox = (bx0, by0, bx1, by1)

        # Warm cream fill with golden border
        fill = (255, 249, 235, 225)
        outline = (200, 170, 100, 240)
        self._draw_rounded_rect_with_shadow(draw, bbox, banner_radius, fill, outline)

        # Render title text (centred)
        title_color = (101, 67, 33)
        cur_y = by0 + padding
        for line in lines:
            lw = font.getlength(line)
            x = bx0 + (banner_w - lw) // 2
            draw.text((x, cur_y), line, font=font, fill=title_color)
            cur_y += line_h

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def overlay_text_on_image(
        self,
        image_path: str,
        text: str,
        output_path: str,
        scene_number: int,
        total_scenes: int,
        title: str = None,
        moral: str = None,
    ) -> str:
        """
        Overlay speech-bubble text on *image_path* and save to *output_path*.

        The output image has the **same dimensions** as the input — no canvas
        extension.  Text is rendered inside semi-transparent bubbles drawn
        directly over the illustration via RGBA compositing.
        """
        # Open image as RGBA for alpha compositing
        img = Image.open(image_path).convert("RGBA")
        img_w, img_h = img.size

        # Transparent overlay for all bubble drawing
        overlay = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Title banner (first scene only)
        if scene_number == 1 and title:
            title_font = self._get_font(Config.FONT_SIZE_TITLE)
            self._draw_title_banner(draw, (img_w, img_h), title, title_font)

        # Speech bubble with scene text (+ optional moral on last scene)
        body_font = self._get_font(Config.FONT_SIZE_BODY)
        moral_text = None
        moral_font = None
        if scene_number == total_scenes and moral:
            moral_text = moral
            moral_font = self._get_font(Config.FONT_SIZE_MORAL)

        self._draw_speech_bubble(
            draw, (img_w, img_h), text, body_font, moral_text, moral_font
        )

        # Composite overlay onto the original image
        img = Image.alpha_composite(img, overlay)

        # Save as JPEG (drop alpha channel)
        img = img.convert("RGB")
        img.save(output_path, "JPEG", quality=95)

        return output_path

    def process_all_scenes(
        self,
        story: dict,
        raw_image_paths: list[str],
        output_dir: str,
        progress_callback=None,
    ) -> list[str]:
        """
        Apply speech-bubble text overlays to all scene images.

        Args:
            story: The structured story data
            raw_image_paths: Paths to the raw generated images
            output_dir: Directory to save text-overlaid images
            progress_callback: Optional callback(scene_num, total, status)

        Returns:
            list[str]: Paths to all text-overlaid images
        """
        os.makedirs(output_dir, exist_ok=True)
        output_paths = []
        total = len(story["scenes"])

        for i, (scene, raw_path) in enumerate(zip(story["scenes"], raw_image_paths)):
            scene_num = scene["scene_number"]
            filename = f"scene_{scene_num:02d}.jpg"
            output_path = os.path.join(output_dir, filename)

            if progress_callback:
                progress_callback(scene_num, total, "overlaying")

            self.overlay_text_on_image(
                image_path=raw_path,
                text=scene["text"],
                output_path=output_path,
                scene_number=scene_num,
                total_scenes=total,
                title=story["title"] if scene_num == 1 else None,
                moral=story.get("moral") if scene_num == total else None,
            )

            output_paths.append(output_path)

            if progress_callback:
                progress_callback(scene_num, total, "done")

        return output_paths
