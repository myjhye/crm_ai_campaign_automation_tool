"""One live, read-only comparison; no proposals or business writes."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy import select
from app.core.config import Settings
from app.db.session import Database
from app.models import Dataset
from app.ai.provider import OpenAIProvider
from app.ai.workspace_schemas import CompareRequest
from app.services.performance import compare_campaigns, campaign_performance


def main():
    settings=Settings()
    if not settings.openai_api_key or not settings.database_url:
        raise SystemExit('Database and live API configuration required.')
    db=Database(settings.database_url.get_secret_value())
    try:
        with db.sessions() as session:
            dataset=session.scalar(select(Dataset).where(Dataset.purpose=='ANALYSIS').order_by(Dataset.created_at.desc()).limit(1))
            if dataset is None:raise SystemExit('No analysis dataset.')
            dataset_id=dataset.id
        end=datetime.now(timezone.utc)+timedelta(days=1);start=end-timedelta(days=90)
        name,args,tokens=OpenAIProvider(settings).plan('선택 기간에 발송된 완료 캠페인을 전환율 높은 순으로 비교해줘',
            {'from':start.isoformat(),'to':end.isoformat(),'reference_at':end.isoformat(),'prior_context':None,'available_segments':[]})
        if name!='compare_campaigns':raise SystemExit('Unexpected tool selected.')
        parsed=CompareRequest.model_validate(args)
        if parsed.sort!='conversion_rate' or parsed.order!='desc':raise SystemExit('Unexpected comparison order.')
        with db.sessions() as session:
            result=compare_campaigns(session,dataset_id,args,start,end)
            from uuid import UUID
            for row in result['campaigns']:
                totals=campaign_performance(session,dataset_id,UUID(row['campaign_id']),result['from'],result['to'],result['reference_at'])['totals']
                assert row['conversion_rate']==totals['conversion_rate']['value']
                assert row['click_rate']==totals['click_rate']['value']
                assert row['sent_count']==totals['sent_customers']
                assert Decimal(row['revenue'])==Decimal(totals['revenue'])
        print(f"Live comparison passed: {len(result['campaigns'])} campaigns, {tokens} tokens. No business data written.")
    finally:db.dispose()


if __name__=='__main__':main()
