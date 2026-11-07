"""Configuration diagnostics: never expose values or claim account connectivity."""
import importlib.util
import os

REQUIRED = {
    'planner': (['GEMINI_API_KEY', 'GEMINI_MODEL'], ['langgraph']),
    'gmail.read': (['COMPOSIO_API_KEY','COMPOSIO_GMAIL_AUTH_CONFIG','GMAIL_READ_TOOL','GMAIL_READ_VERSION'], ['composio']),
    'gmail.send': (['COMPOSIO_API_KEY','COMPOSIO_GMAIL_AUTH_CONFIG','GMAIL_SEND_TOOL','GMAIL_SEND_VERSION'], ['composio']),
    'calendar.cancel': (['COMPOSIO_API_KEY','COMPOSIO_GOOGLECALENDAR_AUTH_CONFIG','CALENDAR_CANCEL_TOOL','CALENDAR_CANCEL_VERSION'], ['composio']),
    'browser.inspect': (['BROWSERBASE_API_KEY','BROWSERBASE_PROJECT_ID','BROWSER_ALLOWED_HOSTS'], ['playwright']),
    'sandbox.python': (['E2B_API_KEY','E2B_TEMPLATE_ID'], ['e2b_code_interpreter']),
}

def readiness(demo):
    result = {}
    for name, (variables, modules) in REQUIRED.items():
        missing = [v for v in variables if not os.getenv(v)]
        absent = [m for m in modules if importlib.util.find_spec(m) is None]
        result[name] = {'mode': 'simulation' if demo else 'live',
            'configured': not missing and not absent, 'missing_settings': missing,
            'missing_packages': absent, 'connection_verified': False}
    return result
