import time
import json
from datetime import datetime
from collections import OrderedDict


class PipelineTracer:
    def __init__(self, request_id, max_traces=100):
        self.request_id = request_id
        self.max_traces = max_traces
        self.stages = []
        self._last_timed = None

    def log_stage(self, stage_name, data=None, reason=None):
        entry = {
            'stage': stage_name,
            'timestamp': time.time(),
        }
        if data is not None:
            entry['data'] = data
        if reason:
            entry['reason'] = reason
        self.stages.append(entry)

    def log_timed_stage(self, stage_name, data=None, reason=None):
        """Log a stage with duration since the previous timed stage."""
        now = time.time()
        if self._last_timed is not None and self.stages:
            duration = now - self._last_timed
            if 'duration_ms' not in self.stages[-1]:
                self.stages[-1]['duration_ms'] = int(duration * 1000)
        self._last_timed = now
        self.log_stage(stage_name, data, reason)

    def finish(self):
        """Stamp duration on the final stage."""
        now = time.time()
        if self._last_timed is not None and self.stages:
            duration = now - self._last_timed
            if 'duration_ms' not in self.stages[-1]:
                self.stages[-1]['duration_ms'] = int(duration * 1000)

    def stage_durations(self):
        return {s['stage']: s.get('duration_ms', 0) for s in self.stages}

    def get_trace(self):
        return self.stages

    def to_json(self):
        return json.dumps({
            'request_id': self.request_id,
            'stages': self.stages,
        }, indent=2)


class RequestLog:
    def __init__(self, request_id=None, query=''):
        self.request_id = request_id or str(int(time.time() * 1000))
        self.start_time = time.time()
        self.query = query
        self.user_id = None
        self.capabilities = []
        self.planner_used = False
        self.planner_intent = None
        self.planned_query = None
        self.tools_used = []
        self.search_provider = None
        self.search_time_ms = 0
        self.model = 'default'
        self.tokens_used = 0
        self.response_time_ms = 0
        self.fallback_used = False
        self.cache_hit = False
        self.errors = []
        self.tracer = None

    def complete(self):
        self.response_time_ms = int((time.time() - self.start_time) * 1000)

    def to_dict(self):
        d = {
            'request_id': self.request_id,
            'timestamp': datetime.now().isoformat(),
            'query': self.query[:200],
            'user_id': str(self.user_id) if self.user_id else None,
            'capabilities': self.capabilities,
            'planner_used': self.planner_used,
            'planner_intent': self.planner_intent,
            'planned_query': self.planned_query[:200] if self.planned_query else None,
            'tools_used': self.tools_used,
            'search_provider': self.search_provider,
            'search_time_ms': self.search_time_ms,
            'model': self.model,
            'response_time_ms': self.response_time_ms,
            'fallback_used': self.fallback_used,
            'cache_hit': self.cache_hit,
            'errors': self.errors,
        }
        if self.tracer:
            d['pipeline_trace'] = self.tracer.get_trace()
        return d

    def log(self):
        try:
            print(f'[ORCHESTRATOR] {json.dumps(self.to_dict())}')
        except Exception:
            pass


class Observability:
    _traces = {}
    _max_traces = 100

    @staticmethod
    def create_log(query='', user_id=None):
        return RequestLog(request_id=None, query=query)

    @staticmethod
    def create_tracer(request_id):
        tracer = PipelineTracer(request_id, Observability._max_traces)
        Observability._traces[request_id] = tracer
        return tracer

    @staticmethod
    def get_trace(request_id):
        tracer = Observability._traces.get(request_id)
        return tracer.get_trace() if tracer else None

    @staticmethod
    def clear_trace(request_id):
        Observability._traces.pop(request_id, None)

    @staticmethod
    def clear_all():
        Observability._traces.clear()
