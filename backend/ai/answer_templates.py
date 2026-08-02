class AnswerTemplate:
    @staticmethod
    def get_template(intent):
        templates = {
            'weather': AnswerTemplate._weather_template,
            'finance': AnswerTemplate._finance_template,
            'maps': AnswerTemplate._maps_template,
            'company': AnswerTemplate._company_template,
        }
        return templates.get(intent)

    @staticmethod
    def _weather_template(answer, search_results, verified=None):
        return answer

    @staticmethod
    def _finance_template(answer, search_results, verified=None):
        return answer

    @staticmethod
    def _maps_template(answer, search_results, verified=None):
        return answer

    @staticmethod
    def _company_template(answer, search_results, verified=None):
        return answer

    @staticmethod
    def format(answer, search_results=None, verified=None, intent=None):
        formatter = AnswerTemplate.get_template(intent)
        if formatter:
            return formatter(answer, search_results, verified)
        return answer