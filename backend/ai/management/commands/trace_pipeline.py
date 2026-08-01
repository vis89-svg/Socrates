from django.core.management.base import BaseCommand
from ai.orchestrator import generateResponse
from ai.observability import Observability


class Command(BaseCommand):
    help = 'Run a query through the full pipeline and print the pipeline trace'

    def add_arguments(self, parser):
        parser.add_argument('query', type=str, help='The query to trace')
        parser.add_argument('--trace', action='store_true', help='Enable pipeline tracing')

    def handle(self, *args, **options):
        query = options['query']
        trace_enabled = options['trace']

        if trace_enabled:
            from django.conf import settings
            settings.ENABLE_PIPELINE_TRACE = True

        self.stdout.write(f'Running pipeline trace for: {query}')
        self.stdout.write('=' * 80)

        # Run the generator but just consume it
        for event in generateResponse(query, history=None, user=None):
            if event['type'] == 'analysis':
                self.stdout.write(f'Analysis: {event["capabilities"]}')
            elif event['type'] == 'search_results':
                self.stdout.write(f'Search: {event["count"]} results from {event["provider"]}')
            elif event['type'] == 'token':
                pass  # Skip tokens
            elif event['type'] == 'citations':
                self.stdout.write(f'Citations: {len(event["citations"])} sources')
            elif event['type'] == 'done':
                self.stdout.write('Done')

        # Get the trace from the last request
        # The last request_id would be from the Observability
        # We need to find the most recent trace
        if Observability._traces:
            latest_id = max(Observability._traces.keys())
            tracer = Observability._traces[latest_id]
            trace = tracer.get_trace()
            
            self.stdout.write('\n' + '=' * 80)
            self.stdout.write('PIPELINE TRACE')
            self.stdout.write('=' * 80)
            
            import json
            for stage in trace:
                self.stdout.write(f"\nStage: {stage['stage']}")
                if 'duration_ms' in stage:
                    self.stdout.write(f"  Duration: {stage['duration_ms']}ms")
                if 'data' in stage:
                    self.stdout.write(f"  Data: {json.dumps(stage['data'], indent=2, default=str)[:500]}")
                if 'reason' in stage:
                    self.stdout.write(f"  Reason: {stage['reason']}")
        else:
            self.stdout.write('\nNo trace available. Run with --trace to enable.')

        self.stdout.write('\nDone.')