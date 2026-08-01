from files.models import UserFile


def get_conversation_documents(conversation_id):
    if not conversation_id:
        return None
    try:
        files = UserFile.objects.filter(conversation_id=conversation_id).exclude(
            extracted_text__isnull=True
        ).exclude(extracted_text__exact='')
        if not files.exists():
            return None
        docs = []
        for f in files:
            text = f.extracted_text
            if len(text) > 5000:
                text = text[:5000] + '\n...[truncated]'
            docs.append({
                'name': f.original_name,
                'type': f.file_type,
                'text': text,
            })
        return docs
    except Exception:
        return None
