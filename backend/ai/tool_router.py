from .feature_flags import FeatureFlags
from .search_service import search_service
from .memory_retriever import get_relevant_memories
from .retrieval_service import RetrievalService
from .calculator_service import evaluate_expression
from .document_service import get_conversation_documents
from .code_executor import execute_code


class ToolRouter:
    @staticmethod
    def execute(capabilities, query, user=None, conversation_id=None, intent=None,
                required_sources=None, constraints=None):
        results = {'search': None, 'memories': None, 'documents': None, 'calculation': None, 'code_result': None}

        if 'needs_search' in capabilities and FeatureFlags.is_enabled('ENABLE_SEARCH'):
            retrieval = RetrievalService()
            results['search'] = retrieval.execute(query, intent=intent, required_sources=required_sources,
                                                  constraints=constraints)

        if 'needs_math' in capabilities and FeatureFlags.is_enabled('ENABLE_CALCULATOR'):
            result, expr = evaluate_expression(query)
            if result is not None:
                results['calculation'] = {'expression': expr, 'result': result}

        if 'needs_documents' in capabilities and conversation_id:
            results['documents'] = get_conversation_documents(conversation_id)

        if 'needs_code' in capabilities and FeatureFlags.is_enabled('ENABLE_CODE_EXECUTION'):
            code_result = execute_code(query)
            if code_result['success'] and code_result['stdout']:
                results['code_result'] = code_result['stdout']

        if FeatureFlags.is_enabled('ENABLE_MEMORY') and user:
            results['memories'] = get_relevant_memories(user, query)

        return results
