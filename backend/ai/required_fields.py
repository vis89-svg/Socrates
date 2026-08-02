REQUIRED_FIELDS = {
    'weather': {
        'temperature': {
            'label': 'Temperature',
            'description': 'Current temperature in Celsius or Fahrenheit',
            'critical': True,
        },
        'condition': {
            'label': 'Conditions',
            'description': 'Current weather condition (sunny, rainy, cloudy, etc.)',
            'critical': True,
        },
        'humidity': {
            'label': 'Humidity',
            'description': 'Current humidity percentage',
            'critical': False,
        },
        'wind': {
            'label': 'Wind',
            'description': 'Wind speed and direction',
            'critical': False,
        },
        'alert': {
            'label': 'Weather Alerts',
            'description': 'IMD warnings, flood alerts, cyclone warnings',
            'critical': True,
        },
        'forecast': {
            'label': 'Forecast',
            'description': 'Short-term forecast (next 24-48 hours)',
            'critical': False,
        },
        'rain_probability': {
            'label': 'Rain Probability',
            'description': 'Chance of rain in percentage',
            'critical': False,
        },
    },
    'finance': {
        'price': {
            'label': 'Price',
            'description': 'Current price or value',
            'critical': True,
        },
        'change': {
            'label': 'Change',
            'description': 'Price change (absolute and percentage)',
            'critical': False,
        },
        'trend': {
            'label': 'Trend',
            'description': 'Recent price trend direction',
            'critical': False,
        },
        'volume': {
            'label': 'Volume',
            'description': 'Trading volume',
            'critical': False,
        },
        'source': {
            'label': 'Source',
            'description': 'Official source of the financial data',
            'critical': True,
        },
    },
    'company': {
        'name': {
            'label': 'Company Name',
            'description': 'Full legal company name',
            'critical': True,
        },
        'headquarters': {
            'label': 'Headquarters',
            'description': 'Location of company headquarters',
            'critical': False,
        },
        'ceo': {
            'label': 'CEO / Leadership',
            'description': 'Current CEO or key leadership',
            'critical': False,
        },
        'revenue': {
            'label': 'Revenue',
            'description': 'Latest annual revenue',
            'critical': False,
        },
        'founded': {
            'label': 'Founded',
            'description': 'Year the company was founded',
            'critical': False,
        },
        'employees': {
            'label': 'Employees',
            'description': 'Number of employees',
            'critical': False,
        },
    },
    'research': {
        'summary': {
            'label': 'Executive Summary',
            'description': 'Key findings from research',
            'critical': True,
        },
        'facts': {
            'label': 'Key Facts',
            'description': 'Verified factual claims',
            'critical': True,
        },
        'sources': {
            'label': 'Sources',
            'description': 'Authoritative sources cited',
            'critical': True,
        },
        'confidence': {
            'label': 'Confidence Level',
            'description': 'How confident the answer is',
            'critical': False,
        },
    },
    'comparison': {
        'items': {
            'label': 'Items Compared',
            'description': 'The items being compared',
            'critical': True,
        },
        'criteria': {
            'label': 'Comparison Criteria',
            'description': 'Dimensions of comparison',
            'critical': True,
        },
        'winner': {
            'label': 'Recommendation',
            'description': 'Which item is better and why',
            'critical': True,
        },
        'tradeoffs': {
            'label': 'Tradeoffs',
            'description': 'Pros and cons of each option',
            'critical': False,
        },
    },
    'coding': {
        'solution': {
            'label': 'Solution',
            'description': 'The code or implementation',
            'critical': True,
        },
        'explanation': {
            'label': 'Explanation',
            'description': 'How the solution works',
            'critical': True,
        },
        'complexity': {
            'label': 'Complexity',
            'description': 'Time and space complexity if applicable',
            'critical': False,
        },
    },
    'maps': {
        'location': {
            'label': 'Location',
            'description': 'The place being looked up',
            'critical': True,
        },
        'coordinates': {
            'label': 'Coordinates',
            'description': 'Latitude and longitude',
            'critical': False,
        },
        'distance': {
            'label': 'Distance',
            'description': 'Distance between locations',
            'critical': False,
        },
    },
}


class RequiredFields:
    @staticmethod
    def get_fields(intent):
        return REQUIRED_FIELDS.get(intent, {})

    @staticmethod
    def get_critical_fields(intent):
        fields = REQUIRED_FIELDS.get(intent, {})
        return {k: v for k, v in fields.items() if v.get('critical', False)}

    @staticmethod
    def get_missing_fields(intent, provided_fields):
        required = RequiredFields.get_fields(intent)
        missing = []
        for field_id, field_info in required.items():
            if field_id not in provided_fields and field_info.get('critical', False):
                missing.append(field_id)
        return missing

    @staticmethod
    def has_all_critical(intent, provided_fields):
        critical = RequiredFields.get_critical_fields(intent)
        return all(f in provided_fields for f in critical)