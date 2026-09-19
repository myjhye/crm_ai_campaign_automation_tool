"""Explicit live provider smoke test. Does not save business data."""
from app.core.config import Settings
from app.ai.provider import OpenAIProvider
from app.core.errors import AppError


def main():
    settings = Settings()
    if not settings.openai_api_key:
        raise SystemExit('OPENAI_API_KEY is not configured; live verification was not run.')
    try:
        name, args, tokens = OpenAIProvider(settings).plan('선택한 기간의 활성 고객 수를 알려줘',
            {'from':'2026-08-19T00:00:00Z', 'to':'2026-09-19T00:00:00Z', 'reference_at':'2026-09-19T00:00:00Z'})
        if name != 'get_metric' or args != {'metric':'active_customers'}:
            raise SystemExit('Live tool selection did not match the expected metric.')
        print(f'Live tool selection passed; tokens={tokens}. Confirm the full UI flow separately.')
    except AppError as error:
        raise SystemExit(error.code) from None


if __name__ == '__main__':
    main()
