"""One live analysis call against local aggregates; no proposal or campaign writes."""
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func
from app.core.config import Settings
from app.core.errors import AppError
from app.db.session import Database
from app.models.campaigns import Campaign, CampaignDelivery
from app.services.performance import campaign_performance
from app.ai.performance import evidence, analysis_tool, validate_selection, HYPOTHESES, ACTIONS
from app.ai.provider import OpenAIProvider


def main():
    settings=Settings()
    if not settings.openai_api_key or not settings.database_url:
        raise SystemExit('Live verification requires OPENAI_API_KEY and DATABASE_URL.')
    database=Database(settings.database_url.get_secret_value())
    try:
        with database.sessions() as session:
            row=session.scalar(select(Campaign).where(Campaign.status=='COMPLETED',Campaign.archived_at.is_(None)).order_by(Campaign.created_at.desc()).limit(1))
            if row is None:raise SystemExit('Complete a simulated campaign before running this check.')
            start=session.scalar(select(func.min(CampaignDelivery.sent_at)).where(CampaignDelivery.campaign_id==row.id,CampaignDelivery.status=='SENT'))
            if start is None:raise SystemExit('No sent recipients in the completed campaign.')
            report=campaign_performance(session,row.dataset_id,row.id,start,datetime.now(timezone.utc)+timedelta(days=1))
        refs=evidence(report)
        name,args,tokens=OpenAIProvider(settings).plan('근거 지표와 다음 실험을 선택해주세요.',{
            'performance':{'metric_refs':refs,'experiment':report['experiment'],
                'contains_simulated_data':report['contains_simulated_data'],'hypotheses':HYPOTHESES,'actions':ACTIONS},
            'analysis_tool':analysis_tool(refs)})
        if name!='analyze_campaign':raise SystemExit('Unexpected tool selected.')
        result=validate_selection(args,refs,report)
        print(f'Live analysis passed: {len(result.facts)} verified metric references; tokens={tokens}. No business writes.')
    except AppError as error:
        raise SystemExit(error.code) from None
    finally:
        database.dispose()


if __name__=='__main__':main()
