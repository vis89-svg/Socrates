def extract_text_from_pdf(file_path):
    try:
        import fitz
        doc = fitz.open(file_path)
        text = '\n'.join(page.get_text() for page in doc).strip()
        if len(text) > 50:
            doc.close()
            return text
        import pytesseract
        from PIL import Image
        import io
        pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        pages = []
        for page in doc:
            pix = page.get_pixmap(dpi=300)
            img = Image.open(io.BytesIO(pix.tobytes('png')))
            ocr_text = pytesseract.image_to_string(img).strip()
            if ocr_text:
                pages.append(ocr_text)
        doc.close()
        return '\n\n'.join(pages) if pages else (text or None)
    except Exception:
        return None


def extract_text(file_path, file_type):
    if file_type == 'pdf':
        return extract_text_from_pdf(file_path)
    return None
