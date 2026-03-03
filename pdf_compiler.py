"""
PDF Compiler Module for StoryBook Generator.
Compiles the text-overlaid images into a beautiful PDF storybook.
Uses fpdf2 for PDF generation.
"""

import os
from fpdf import FPDF
from PIL import Image


class StoryBookPDF:
    """Compiles storybook images into a PDF document."""

    def __init__(self):
        pass

    def compile_pdf(
        self,
        story: dict,
        image_paths: list[str],
        output_path: str,
    ) -> str:
        """
        Compile all text-overlaid images into a single PDF storybook.

        Each image becomes a full page in the PDF, maintaining aspect ratio.
        Page size is determined by finding the maximum dimensions across ALL
        images so every PDF page is uniform.

        Args:
            story: The structured story data
            image_paths: Paths to the text-overlaid scene images (in order)
            output_path: Path for the output PDF file

        Returns:
            str: Path to the generated PDF
        """
        # Find max dimensions across ALL images for uniform pages
        max_width = 0
        max_height = 0
        for path in image_paths:
            with Image.open(path) as img:
                w, h = img.size
                max_width = max(max_width, w)
                max_height = max(max_height, h)

        # Convert pixels to mm (assuming 96 DPI)
        dpi = 96
        page_width_mm = (max_width / dpi) * 25.4
        page_height_mm = (max_height / dpi) * 25.4

        # Cap at A4-ish dimensions for readability
        max_width_mm = 210   # A4 portrait width
        max_height_mm = 297  # A4 portrait height

        # Detect orientation from aspect ratio
        if page_width_mm > page_height_mm:
            # Landscape image — swap caps
            max_width_mm, max_height_mm = 297, 210
            orientation = "L"
        else:
            orientation = "P"

        scale = min(max_width_mm / page_width_mm, max_height_mm / page_height_mm, 1.0)
        final_width = page_width_mm * scale
        final_height = page_height_mm * scale

        pdf = FPDF(orientation=orientation, unit="mm", format=(final_width, final_height) if orientation == "P" else (final_height, final_width))
        pdf.set_auto_page_break(auto=False)

        # Set PDF metadata
        pdf.set_title(story["title"])
        pdf.set_author("StoryBook Generator")
        pdf.set_subject(f"A children's bedtime story: {story['title']}")
        pdf.set_keywords("children, bedtime, story, storybook")

        # Add each scene image as a full page
        for image_path in image_paths:
            pdf.add_page()
            pdf.image(image_path, x=0, y=0, w=final_width, h=final_height)

        # Save the PDF
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        pdf.output(output_path)

        return output_path

    def compile_with_cover(
        self,
        story: dict,
        image_paths: list[str],
        output_path: str,
    ) -> str:
        """
        Compile PDF with a generated cover page plus all scene illustrations.

        The cover page uses the first scene's image as background with
        a prominent title overlay.

        Args:
            story: The structured story data
            image_paths: Paths to all text-overlaid scene images
            output_path: Path for the output PDF file

        Returns:
            str: Path to the generated PDF
        """
        # For now, just use the standard compilation
        # First image already has the title overlay from TextOverlay
        return self.compile_pdf(story, image_paths, output_path)
