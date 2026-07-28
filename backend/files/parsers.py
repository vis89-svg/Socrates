def extract_text_from_pdf(file_path):
    try:
        import fitz
        doc = fitz.open(file_path)
        text = '\n'.join(page.get_text() for page in doc)
        doc.close()
        return text.strip()
    except Exception:
        return None


def extract_text(file_path, file_type):
    if file_type == 'pdf':
        return extract_text_from_pdf(file_path)
    return None
