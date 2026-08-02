from django.test import SimpleTestCase

from ai.greetings import greeting_reply


class GreetingTests(SimpleTestCase):
    def test_plain_greetings(self):
        for q in ['hi', 'hi!', 'Hello', 'HEY', 'hey there?? ', 'yo', 'hola', 'namaste']:
            self.assertIsNotNone(greeting_reply(q), q)

    def test_goodbye_and_thanks(self):
        self.assertIsNotNone(greeting_reply('thanks'))
        self.assertIsNotNone(greeting_reply('thank you!'))
        self.assertIsNotNone(greeting_reply('bye'))
        self.assertIsNotNone(greeting_reply('good evening'))

    def test_how_are_you(self):
        self.assertIsNotNone(greeting_reply('how are you'))
        self.assertIsNotNone(greeting_reply('whats up?'))

    def test_acknowledgements(self):
        self.assertIsNotNone(greeting_reply('ok'))
        self.assertIsNotNone(greeting_reply('sure'))
        self.assertIsNotNone(greeting_reply('no problem'))

    def test_real_questions_are_not_greetings(self):
        for q in ['hey what is the capital of France', 'hello world in python',
                  'thanks but what about the report', 'what is quantum computing',
                  'ok so what happens next', 'hi how do I reset my password?']:
            self.assertIsNone(greeting_reply(q), q)

    def test_long_text_is_not_greeting(self):
        self.assertIsNone(greeting_reply('hi ' * 50))

    def test_empty_is_none(self):
        self.assertIsNone(greeting_reply(''))
        self.assertIsNone(greeting_reply(None))

    def test_replies_are_meaningful(self):
        self.assertIn('How can I help', greeting_reply('hello'))
        self.assertIn('welcome', greeting_reply('thanks').lower())
        self.assertIn('Goodbye', greeting_reply('bye'))
