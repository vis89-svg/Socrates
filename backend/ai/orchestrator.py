import os
from datetime import datetime
from django.conf import settings
from .task_analyzer import TaskAnalyzer
from .query_planner import QueryPlanner
from .tool_router import ToolRouter
from .decision_loop import DecisionLoop
from .context_builder import ContextBuilder
from .model_router import ModelRouter, api_quota_down
from .response_formatter import ResponseFormatter
from .observability import Observability
from .feature_flags import FeatureFlags
from .source_weighter import SourceWeighter
from .greetings import greeting_reply
from .weather_service import WeatherService
from .constraint_engine import ConstraintEngine
from .required_fields import RequiredFields
from .missing_info_recovery import MissingInfoRecovery
from .recommendation_engine import RecommendationEngine
from .temporal_constraint import TemporalConstraintEngine


_DEEP_RESEARCH_KEYWORDS = ['research', 'deep dive', 'thorough', 'comprehensive', 'full report',
                               'in-depth', 'detailed analysis', 'tell me everything about']

_WEATHER_INTENTS = {'weather'}
_FAST_INTENTS = {'weather', 'finance', 'maps', 'company'}


def generateResponse(query, history=None, user=None, conversation_id=None, files_data=None, web_search=None):
    log = Observability.create_log(query=query, user_id=getattr(user, 'id', None) if user else None)

    reply = greeting_reply(query)
    if reply is not None and not files_data:
        log.capabilities = []
        log.complete()
        yield {'type': 'analysis', 'capabilities': [], 'planned_query': query}
        yield {'type': 'token', 'content': reply}
        yield {'type': 'done', 'response': reply}
        return

    if web_search is not True and not files_data and api_quota_down():
        log.capabilities = ['offline']
        log.complete()
        yield {'type': 'analysis', 'capabilities': ['offline'], 'planned_query': query}
        context = ''
        try:
            yield {'type': 'tool_use', 'tool': 'search', 'label': '🔍 Searching the web...', 'args': {'query': query}}
            from .retrieval_service import RetrievalService
            info = RetrievalService().execute(query)
            results = info.get('results') or []
            log.search_provider = info.get('provider')
            if results:
                lines = ['Web search results:']
                for i, r in enumerate(results[:5], 1):
                    lines.append(f'{i}. {r.get("title", "Untitled")} — {r.get("url", "")}')
                    snippet = r.get('snippet') or ''
                    if snippet:
                        lines.append(f'   {snippet[:400]}')
                context = '\n'.join(lines)
        except Exception:
            context = ''
        prompt = (
            "You are Owl, running in offline mode because every online AI provider is "
            "quota-exhausted right now. Answer the user's question briefly using only "
            "the web search results below. If the results do not contain the answer, "
            "say so honestly and give only what can be inferred from them.\n\n"
            f"User: {query}\n\n"
            f"{context}\n\n"
            "Owl:"
        )
        full = ''
        for chunk in ModelRouter.generate_stream(prompt, model_key='fallback', max_tokens=300):
            full += chunk
            yield {'type': 'token', 'content': chunk}
        yield {'type': 'done', 'response': full}
        return

    # Create pipeline tracer if enabled
    tracer = None
    if FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
        tracer = Observability.create_tracer(log.request_id)
        log.tracer = tracer
        tracer.log_timed_stage('orchestrator_start', {'query': query})

    plan = QueryPlanner.plan(query, history=history)
    if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
        tracer.log_timed_stage('planner_complete', {'plan': plan})

    planned_query = query
    capabilities = TaskAnalyzer.analyze(query)
    plan_intent = None
    plan_required_sources = None

    if plan:
        planned_query = plan['rewritten_query']
        plan_intent = plan['intent']
        plan_required_sources = plan.get('required_sources') or None
        for cap in plan['tools']:
            capabilities.add(cap)
        if plan['needs_search'] is not None:
            if plan['needs_search']:
                capabilities.add('needs_search')
            else:
                capabilities.discard('needs_search')
        log.planner_used = True
        log.planner_intent = plan['intent']
        log.planned_query = planned_query

    if web_search is True:
        capabilities.add('needs_search')
    elif web_search is False and not (plan and (plan.get('needs_search') is True or 'needs_search' in (plan.get('tools') or []))):
        capabilities.discard('needs_search')
    if files_data:
        capabilities.add('needs_documents')
    log.capabilities = list(capabilities)

    constraints = ConstraintEngine.extract(planned_query)
    hard_constraints = ConstraintEngine.get_hard_constraints(constraints)
    soft_constraints = ConstraintEngine.get_soft_constraints(constraints)

    temporal_type = TemporalConstraintEngine.extract(planned_query)
    if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
        tracer.log_timed_stage('temporal_intent', {
            'temporal_type': temporal_type.value,
            'query': planned_query,
        })

    yield {'type': 'analysis', 'capabilities': list(capabilities), 'planned_query': planned_query}

    if plan_intent in _WEATHER_INTENTS and FeatureFlags.is_enabled('ENABLE_WEATHER'):
        yield from _generate_weather(planned_query, user=user, conversation_id=conversation_id,
                                         log=log, tracer=tracer)
        return

    use_agent = FeatureFlags.is_enabled('ENABLE_AGENT_LOOP')
    is_deep_research_hint = any(kw in planned_query.lower() for kw in _DEEP_RESEARCH_KEYWORDS)

    if use_agent and not is_deep_research_hint:
        yield from _generate_agent(planned_query, history, user=user, conversation_id=conversation_id,
                                       files_data=files_data, web_search=web_search, capabilities=capabilities,
                                       plan=plan, plan_intent=plan_intent,
                                       plan_required_sources=plan_required_sources, log=log, tracer=tracer,
                                       constraints=constraints)
    else:
        yield from _generate_legacy(planned_query, history, user=user, conversation_id=conversation_id,
                                         files_data=files_data, web_search=web_search, capabilities=capabilities,
                                         plan=plan, plan_intent=plan_intent,
                                         plan_required_sources=plan_required_sources, log=log, tracer=tracer,
                                         constraints=constraints)


def _generate_agent(planned_query, history, user, conversation_id, files_data, web_search,
                       capabilities, plan, plan_intent, plan_required_sources, log, tracer,
                       constraints=None):
    if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
        tracer.log_timed_stage('agent_start', {'capabilities': list(capabilities)})

    yield {'type': 'stage', 'label': 'Gathering information...'}

    context_caps = capabilities - {'needs_search', 'needs_math', 'needs_code'}
    tool_results = ToolRouter.execute(context_caps, planned_query, user=user,
                                      conversation_id=conversation_id, intent=plan_intent,
                                      required_sources=plan_required_sources, constraints=constraints)
    if files_data and not tool_results.get('documents'):
        tool_results['documents'] = files_data

    if tool_results.get('search'):
        yield {'type': 'stage', 'label': 'Search complete — analyzing results...'}

    model_key = 'chat'
    if plan and plan['model_route']:
        model_key = plan['model_route']
    elif 'needs_code' in capabilities:
        model_key = 'coding'
    elif 'needs_reasoning' in capabilities or 'needs_math' in capabilities:
        model_key = 'reasoning'
    log.model = model_key

    loop = DecisionLoop(
        planned_query, history=history, user=user, conversation_id=conversation_id,
        files_data=files_data, model_key=model_key, web_search=web_search,
        context_blocks=_context_blocks(tool_results, files_data), tracer=tracer,
        intent=plan_intent, required_sources=plan_required_sources,
    )

    yield {'type': 'stage', 'label': 'Generating answer...'}

    full_response = ''
    token_count = 0
    for event in loop.run():
        if event['type'] == 'token':
            full_response += event['content']
            token_count += 1
            yield event
        elif event['type'] in ('tool_use', 'search_results'):
            yield event

    log.tokens_used = token_count

    if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
        tracer.log_timed_stage('agent_generation_complete', {'tokens': token_count, 'chars': len(full_response)})

    formatted, citations = ResponseFormatter.format(full_response, loop.search_results or None)

    if citations:
        yield {'type': 'citations', 'citations': citations}

    log.complete()
    if FeatureFlags.is_enabled('ENABLE_OBSERVABILITY'):
        log.log()

    if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
        tracer.finish()
        yield {'type': 'timings', 'timings': _timings(tracer, log, None)}

    yield {'type': 'done', 'response': formatted}


def _generate_legacy(planned_query, history, user, conversation_id, files_data, web_search,
                       capabilities, plan, plan_intent, plan_required_sources, log, tracer,
                       constraints=None):
    if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
        tracer.log_timed_stage('tool_router_start', {'capabilities': list(capabilities)})

    yield {'type': 'stage', 'label': 'Gathering information...'}

    tool_results = ToolRouter.execute(capabilities, planned_query, user=user, conversation_id=conversation_id,
                                          intent=plan_intent, required_sources=plan_required_sources,
                                          constraints=constraints)
    if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
        tracer.log_timed_stage('tool_router_complete', {'tools_used': list(tool_results.keys())})

    if tool_results.get('search'):
        yield {'type': 'stage', 'label': 'Search complete — analyzing results...'}

    if files_data and not tool_results.get('documents'):
        tool_results['documents'] = files_data
    search_info = tool_results.get('search')
    log.search_provider = search_info.get('provider') if search_info else None
    log.search_time_ms = search_info.get('time_ms', 0) if search_info else 0

    if search_info is not None:
        evidence = [
            {
                'url': r.get('url', ''),
                'title': (r.get('title') or 'Untitled')[:120],
                'published_date': r.get('published_date', '') or r.get('date', '') or '',
            }
            for r in (search_info.get('results') or [])[:10]
            if r.get('url')
        ]
        yield {'type': 'search_results', 'count': search_info.get('count', 0),
               'provider': search_info.get('provider'), 'evidence': evidence,
               'intent': search_info.get('intent'), 'coverage': search_info.get('coverage')}

    use_research_prompt = search_info is not None and search_info.get('count', 0) > 0
    is_deep_research = use_research_prompt and any(kw in planned_query.lower() for kw in _DEEP_RESEARCH_KEYWORDS)

    verified_facts = None
    if is_deep_research:
        yield {'type': 'stage', 'label': 'Researching — filling gaps and extracting facts...'}
        prompt, search_results_raw, loop_summary, verified_facts = _build_deep_research_prompt(planned_query, search_info, history, capabilities, tool_results, tracer)
        if loop_summary:
            prompt = loop_summary + '\n\n' + prompt
    elif use_research_prompt:
        prompt, search_results_raw = _build_enhanced_prompt(planned_query, search_info, history, capabilities, tool_results, tracer)
    else:
        prompt = ContextBuilder.build(planned_query, capabilities, tool_results, history)
        search_results_raw = search_info.get('results') if search_info else None

    if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
        tracer.log_timed_stage('prompt_built', {'prompt_length': len(prompt), 'deep_research': is_deep_research})

    yield {'type': 'stage', 'label': 'Writing answer...'}

    model_key = 'chat'
    if plan and plan['model_route']:
        model_key = plan['model_route']
    elif 'needs_code' in capabilities:
        model_key = 'coding'
    elif 'needs_reasoning' in capabilities or 'needs_math' in capabilities:
        model_key = 'reasoning'

    log.model = model_key

    max_tokens = 1536 if use_research_prompt else None

    full_response = ''
    token_count = 0
    attempts = [model_key, model_key, 'fallback']
    try:
        for attempt in attempts:
            if token_count > 0:
                break
            if attempt != model_key:
                log.fallback_used = True
            try:
                for token in ModelRouter.generate_stream(prompt, model_key=attempt, max_tokens=max_tokens):
                    full_response += token
                    token_count += 1
                    yield {'type': 'token', 'content': token}
            except Exception:
                if token_count == 0:
                    continue
                raise
            if not full_response.strip():
                continue
    except Exception:
        log.fallback_used = True
        for token in ModelRouter.generate_stream(prompt, model_key='fallback', max_tokens=max_tokens):
            full_response += token
            token_count += 1
            yield {'type': 'token', 'content': token}

    log.tokens_used = token_count

    if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
        tracer.log_timed_stage('generation_complete', {'tokens': token_count, 'chars': len(full_response)})

    formatted, citations = ResponseFormatter.format(full_response, search_results_raw, verified=verified_facts)

    if verified_facts is not None:
        yield {'type': 'research_summary', 'summary': _research_summary(verified_facts, search_info)}

    if citations:
        yield {'type': 'citations', 'citations': citations}

    log.complete()
    if FeatureFlags.is_enabled('ENABLE_OBSERVABILITY'):
        log.log()

    if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
        tracer.finish()
        yield {'type': 'timings', 'timings': _timings(tracer, log, search_info)}

    yield {'type': 'done', 'response': formatted}


def _research_summary(verified, search_info):
    counts = {'high': 0, 'medium': 0, 'low': 0, 'none': 0}
    fields = 0
    for entry in verified.values():
        if not isinstance(entry, dict):
            continue
        if entry.get('value') is None:
            continue
        fields += 1
        counts[entry.get('confidence', 'none')] = counts.get(entry.get('confidence', 'none'), 0) + 1
    domains = {}
    for r in (search_info.get('results') or [])[:10]:
        url = r.get('url', '')
        domain = url.split('/')[2] if '//' in url else url
        domain = domain[4:] if domain.startswith('www.') else domain
        if domain:
            domains[domain] = domains.get(domain, 0) + 1
    top_domains = sorted(domains, key=domains.get, reverse=True)[:4]
    return {
        'sources': search_info.get('count', 0) if search_info else 0,
        'fields_verified': fields,
        'confidence': counts,
        'top_domains': top_domains,
    }


def _timings(tracer, log, search_info):
    durations = tracer.stage_durations()
    extract_ms = durations.get('extraction_complete', 0) + durations.get('gap_fill_complete', 0)
    if extract_ms == 0:
        extract_ms = durations.get('research_pipeline_complete', 0)
    return {
        'planner_ms': durations.get('planner_complete', 0),
        'search_ms': (search_info.get('time_ms', 0) if search_info else 0) or durations.get('tool_router_complete', 0),
        'agent_loop_ms': durations.get('decision_loop_complete', 0) or durations.get('agent_loop_complete', 0),
        'extract_ms': extract_ms,
        'verify_ms': durations.get('verification_complete', 0),
        'generation_ms': durations.get('generation_complete', 0),
        'total_ms': log.response_time_ms,
    }


def _load_prompt(name):
    path = os.path.join(os.path.dirname(__file__), 'prompts', name)
    try:
        with open(path, encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return ''


def _context_blocks(tool_results, files_data):
    """Pre-rendered context blocks (memories, documents) for the agent loop."""
    blocks = []
    memories = tool_results.get('memories') or []
    if memories:
        mem_lines = '\n'.join(f'- {m["content"]}' for m in memories)
        blocks.append('Relevant information from the user\'s history:\n' + mem_lines)
    documents = tool_results.get('documents') or []
    if not documents and files_data:
        documents = files_data
    if documents:
        doc_lines = []
        for d in documents:
            if d.get('text'):
                doc_lines.append(f'--- {d["name"]} ---\n{d["text"]}')
            else:
                doc_lines.append(f'--- {d["name"]} ---\n[The user attached a file named "{d["name"]}" (type: {d.get("type", "unknown")}). It could not be read as text.]')
        blocks.append('The user is asking about uploaded documents. Analyze them and answer their questions.\n\nDocuments:\n' + '\n\n'.join(doc_lines))
    return blocks


def _build_enhanced_prompt(query, search_info, history, capabilities, tool_results, verified_dataset=None, tracer=None):
    if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
        tracer.log_timed_stage('build_enhanced_prompt_start', {'has_verified_dataset': verified_dataset is not None})

    results = search_info.get('results', [])
    weighted = SourceWeighter.priority_sort(results)

    search_info['results'] = weighted
    search_info['count'] = len(weighted)
    weighted_summary = _rebuild_summary(search_info, weighted)
    search_info['summary'] = weighted_summary

    date_str = datetime.now().strftime('%A, %B %d, %Y')
    parts = []

    system = _load_prompt('system.md')
    if system:
        system = system.replace('{{DATE}}', date_str)
        parts.append(f'\n\n{system}')

    writer = _load_prompt('write.md')
    if writer:
        parts.append(f'\n\n{writer}')

    if tool_results.get('memories'):
        memory_prompt = _load_prompt('memory.md')
        mem_text = '\n'.join(f'- {m["content"]}' for m in tool_results['memories'])
        memory_prompt = memory_prompt.replace('{{MEMORIES}}', mem_text)
        parts.append(f'\n{memory_prompt}')

    if tool_results.get('calculation'):
        calc = tool_results['calculation']
        parts.append(f'\n\nCalculator result: {calc["expression"]} = {calc["result"]}')

    if tool_results.get('code_result'):
        parts.append(f'\n\nCode output:\n{tool_results["code_result"]}')

    if tool_results.get('documents'):
        doc_lines = []
        for d in tool_results['documents']:
            if d.get('text'):
                doc_lines.append(f'--- {d["name"]} ---\n{d["text"]}')
            else:
                doc_lines.append(f'--- {d["name"]} ---\n[The user attached a file named "{d["name"]}" (type: {d.get("type", "unknown")}). It could not be read as text.]')
        doc_prompt = _load_prompt('document.md')
        if doc_prompt:
            doc_prompt = doc_prompt.replace('{{DOCUMENTS}}', '\n\n'.join(doc_lines))
            parts.append(f'\n{doc_prompt}')

    parts.append(f'\n\nSearch Results:\n{weighted_summary}')

    if verified_dataset:
        parts.append(f'\n\nVerified Fact Dataset (extracted and cross-checked from the search results above — use these as your primary source of truth):\n{verified_dataset}')

    if history:
        for msg in history[-10:]:
            role = msg['role'] if isinstance(msg, dict) else msg.role
            content = msg['content'] if isinstance(msg, dict) else msg.content
            parts.append(f'\n\n{role}\n{content}')

    parts.append(f'\n\nuser\n{query}')
    parts.append('\n\nassistant\n')

    if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
        tracer.log_timed_stage('prompt_built', {'prompt_length': len(''.join(parts))})

    return ''.join(parts), weighted


def _build_deep_research_prompt(query, search_info, history, capabilities, tool_results, tracer=None):
    from .agent_loop import AgentLoop
    from .research_pipeline import ResearchPipeline

    if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
        tracer.log_timed_stage('deep_research_start', {})

    all_results, gap_findings, loop_summary = AgentLoop.run(query, search_info)

    if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
        tracer.log_timed_stage('agent_loop_complete', {'iterations': len(gap_findings), 'total_results': len(all_results)})

    merged_info = dict(search_info)
    merged_info['results'] = all_results
    merged_info['count'] = len(all_results)
    merged_info['summary'] = _rebuild_summary(merged_info, all_results)

    dataset_text = None
    verified = None
    try:
        dataset_text, verified, weighted = ResearchPipeline.run(merged_info, query, tracer=tracer)
        merged_info['results'] = weighted
        merged_info['count'] = len(weighted)
    except Exception:
        dataset_text, verified = None, None

    if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
        tracer.log_timed_stage('research_pipeline_complete', {'verified_fields': len(verified) if verified else 0})

    prompt, results_raw = _build_enhanced_prompt(query, merged_info, history, capabilities, tool_results, verified_dataset=dataset_text, tracer=tracer)
    return prompt, results_raw, loop_summary, verified

def _rebuild_summary(search_info, weighted_results):
    max_excerpt = getattr(settings, 'MAX_PAGE_EXCERPT', 500)
    parts = []
    parts.append('The following search results contain information that may answer the question.')
    parts.append('')
    for i, r in enumerate(weighted_results[:12], 1):
        title = r.get('title', 'Untitled')
        snippet = r.get('snippet', '')
        url = r.get('url', '')
        tier = SourceWeighter.tier_label(url)
        parts.append(f'--- Source {i}: {title} ---')
        parts.append(f'URL: {url}')
        parts.append(f'Authority: {tier}')
        if snippet:
            parts.append(f'Content: {snippet[:300]}')
        if r.get('page_text'):
            parts.append(f'Full page excerpt:')
            parts.append(r['page_text'][:max_excerpt])
        parts.append('')
    coverage = search_info.get('coverage')
    if coverage and coverage.get('required'):
        parts.append('Source coverage report:')
        parts.append(f"Required authorities: {', '.join(coverage['required'])}")
        if coverage['found']:
            parts.append(f"Found: {', '.join(coverage['found'])}")
        if coverage['missing']:
            parts.append(f"Searched but no relevant results found: {', '.join(coverage['missing'])}")
        parts.append('')
    return '\n'.join(parts)


def _generate_weather(planned_query, user, conversation_id, log, tracer):
    if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
        tracer.log_timed_stage('weather_start', {'query': planned_query})

    yield {'type': 'stage', 'label': '🌤 Fetching weather data...'}

    weather_data = WeatherService.get_weather(planned_query)

    if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
        tracer.log_timed_stage('weather_fetch_complete', {'time_ms': weather_data.get('time_ms', 0)})

    provided_fields = {}
    imd = weather_data.get('imd_data')
    if imd:
        if imd.get('temperature'):
            provided_fields['temperature'] = imd['temperature']
        if imd.get('condition'):
            provided_fields['condition'] = imd['condition']
        if imd.get('humidity'):
            provided_fields['humidity'] = imd['humidity']
        if imd.get('wind'):
            provided_fields['wind'] = imd['wind']
        if imd.get('alert'):
            provided_fields['alert'] = imd['alert']

    missing = RequiredFields.get_missing_fields('weather', provided_fields)
    if missing:
        if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
            tracer.log_timed_stage('weather_missing_fields', {'missing': missing})

        yield {'type': 'stage', 'label': 'Searching for missing weather data...'}
        recovered, recovery_searches = MissingInfoRecovery.check_and_recover(
            'weather', provided_fields, planned_query, tracer=tracer
        )
        provided_fields.update(recovered)

        if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
            tracer.log_timed_stage('weather_recovery_complete', {
                'recovery_searches': recovery_searches,
            })

    yield {'type': 'stage', 'label': 'Formatting answer...'}

    answer = WeatherService.format_answer(weather_data, planned_query)

    if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
        tracer.log_timed_stage('weather_complete', {'answer_length': len(answer)})

    log.complete()
    if FeatureFlags.is_enabled('ENABLE_OBSERVABILITY'):
        log.log()

    if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
        tracer.finish()
        yield {'type': 'timings', 'timings': _weather_timings(tracer, log, weather_data)}

    yield {'type': 'done', 'response': answer}


def _weather_timings(tracer, log, weather_data):
    durations = tracer.stage_durations()
    return {
        'weather_fetch_ms': weather_data.get('time_ms', 0),
        'total_ms': log.response_time_ms,
    }
