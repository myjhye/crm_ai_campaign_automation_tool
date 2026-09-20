import csv
import io
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter,Depends,Query,Response
from sqlalchemy.orm import Session
from app.api.deps import get_session
from app.core.errors import AppError
from app.services.datasets import require_dataset
from app.services.performance import campaign_rows

router=APIRouter(prefix='/reports',tags=['reports'])
DB=Annotated[Session,Depends(get_session)]

def _period(start,end):
    if end<=start:raise AppError('INVALID_PERIOD','성과 기간의 시작과 종료를 올바르게 입력해주세요.',422)

def _safe(value):
    text=str(value)
    return "'"+text if text[:1] in ('=','+','-','@') else text

def _aggregate(rows):
    delivered=sum(row['totals']['delivered_customers'] for row in rows);converted=sum(row['totals']['conversion_customers'] for row in rows)
    revenue=sum((Decimal(row['totals']['revenue']) for row in rows),Decimal('0'))
    return {'campaign_count':len(rows),'delivered_customers':delivered,'conversion_customers':converted,
        'conversion_rate':None if not delivered else round(converted/delivered*100,2),'attributed_revenue':f'{revenue:.2f}'}

def _groups(rows,key):
    grouped=defaultdict(list)
    for row in rows:grouped[key(row)].append(row)
    return [{'name':name,**_aggregate(items)} for name,items in sorted(grouped.items())]

@router.get('/campaigns')
def campaigns(dataset_id:UUID,session:DB,start:Annotated[datetime,Query(alias='from')],end:Annotated[datetime,Query(alias='to')],
              observation_to:datetime|None=None,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100)):
    _period(start,end);require_dataset(session,dataset_id);rows=campaign_rows(session,dataset_id,start,end,observation_to)
    items=[{'campaign':row['campaign'],'totals':row['totals'],'variants':row['variants'],'experiment':row['experiment'],'observation':row['observation'],'contains_simulated_data':row['contains_simulated_data']} for row in rows]
    offset=(page-1)*page_size
    return {'items':items[offset:offset+page_size],'total':len(items),'page':page,'page_size':page_size}

@router.get('/summary')
def summary(dataset_id:UUID,session:DB,start:Annotated[datetime,Query(alias='from')],end:Annotated[datetime,Query(alias='to')],observation_to:datetime|None=None):
    _period(start,end);require_dataset(session,dataset_id);rows=campaign_rows(session,dataset_id,start,end,observation_to)
    previous_end=start;previous_start=start-(end-start);previous=campaign_rows(session,dataset_id,previous_start,previous_end,observation_to)
    return {'period':{'from':start,'to':end},**_aggregate(rows),'previous_period':{'from':previous_start,'to':previous_end,**_aggregate(previous)},
        'by_channel':_groups(rows,lambda row:row['campaign']['channel']),
        'by_segment':_groups(rows,lambda row:row['campaign']['segment_name'] or '이름 없는 세그먼트'),
        'contains_simulated_data':any(row['contains_simulated_data'] for row in rows),'incremental_metrics':{'status':'not_available'}}

@router.get('/export')
def export(dataset_id:UUID,session:DB,start:Annotated[datetime,Query(alias='from')],end:Annotated[datetime,Query(alias='to')],observation_to:datetime|None=None):
    _period(start,end);require_dataset(session,dataset_id);rows=campaign_rows(session,dataset_id,start,end,observation_to)
    output=io.StringIO();writer=csv.writer(output);writer.writerow(['campaign_id','campaign_name','channel','period_from','period_to','simulated','delivered','opens','clicks','conversions','revenue','experiment_status','winner'])
    for row in rows:
        totals=row['totals'];writer.writerow([row['campaign']['id'],_safe(row['campaign']['name']),row['campaign']['channel'],start.isoformat(),end.isoformat(),row['contains_simulated_data'],totals['delivered_customers'],totals['open_customers'],totals['click_customers'],totals['conversion_customers'],totals['revenue'],row['experiment']['status'],row['experiment']['winner'] or ''])
    return Response('\ufeff'+output.getvalue(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="growthpilot-report.csv"'})
