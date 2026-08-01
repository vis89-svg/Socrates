from .citation_service import CitationService
from .confidence_scorer import ConfidenceScorer


class ResponseFormatter:
    @staticmethod
    def format(response_text, search_results=None, verified=None):
        enriched, citations, notes = ConfidenceScorer.analyze_response(response_text, search_results, verified=verified)

        if not citations:
            citations = CitationService.extract(response_text, search_results)

        citation_block = CitationService.format_citations(citations)

        final_response = enriched + citation_block

        if notes:
            note_text = '\n\n**Quality Notes:**'
            for n in notes:
                note_text += f'\n- {n}'
            final_response += note_text

        return final_response, citations
