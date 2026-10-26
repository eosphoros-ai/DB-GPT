"""Isolated single-page renderer; stdout contains only PNG bytes."""

import io
import math
import sys


def render(path, page_number):
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(path)
    try:
        if not 1 <= page_number <= len(document):
            raise IndexError("Page out of range")
        page = document[page_number - 1]
        try:
            width, height = page.get_size()
            if not all(math.isfinite(n) and n > 0 for n in (width, height)):
                raise ValueError("Invalid page dimensions")
            # Bound output dimensions before allocating the bitmap. No cropping,
            # OCR, rearrangement or synthetic highlighting of the source page.
            scale = min(2, 1800 / max(width, height))
            bitmap = page.render(scale=scale)
            try:
                image = bitmap.to_pil()
                try:
                    output = io.BytesIO()
                    image.save(output, format="PNG")
                    return output.getvalue()
                finally:
                    image.close()
            finally:
                bitmap.close()
        finally:
            page.close()
    finally:
        document.close()


if __name__ == "__main__":
    try:
        sys.stdout.buffer.write(render(sys.argv[1], int(sys.argv[2])))
    except IndexError:
        sys.exit(2)
    except Exception:
        sys.exit(1)
