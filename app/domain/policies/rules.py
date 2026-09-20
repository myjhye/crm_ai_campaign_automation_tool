from dataclasses import dataclass

REASON_ORDER = ('WITHDRAWN','NO_CONSENT','INVALID_CONTACT','EXCLUDED_SEGMENT','DUPLICATE_CAMPAIGN','DAILY_LIMIT','WEEKLY_LIMIT')
MESSAGES = {
    'WITHDRAWN':'탈퇴 고객','NO_CONSENT':'채널 수신 미동의','INVALID_CONTACT':'연락처 없음·무효·하드 바운스',
    'EXCLUDED_SEGMENT':'명시적 제외 세그먼트','DUPLICATE_CAMPAIGN':'같은 캠페인 기수신',
    'DAILY_LIMIT':'일일 노출 한도 초과','WEEKLY_LIMIT':'최근 7일 노출 한도 초과',
}

def ordered_reasons(*, withdrawn, consent, contact, valid, hard_bounce, excluded, duplicate, daily, weekly, daily_limit, weekly_limit):
    flags = {'WITHDRAWN':withdrawn,'NO_CONSENT':not consent,'INVALID_CONTACT':not contact or not valid or hard_bounce,
             'EXCLUDED_SEGMENT':excluded,'DUPLICATE_CAMPAIGN':duplicate,'DAILY_LIMIT':daily >= daily_limit,'WEEKLY_LIMIT':weekly >= weekly_limit}
    return [code for code in REASON_ORDER if flags[code]]

def rule_results(reason_counts):
    return [{'rule_code':code,'severity':'EXCLUDE','passed':reason_counts.get(code,0) == 0,
             'affected_count':reason_counts.get(code,0),'message':MESSAGES[code]} for code in REASON_ORDER]
