"""Non-persistent creative suggestions; never create proposals or business rows."""
import re
from app.ai.campaigns import GeneratedCopy
from app.domain.campaigns.copy_policy import POLICIES, CURRENT_VERSION


def validate_advice(args):
    channel = args['channel']
    if channel not in ('EMAIL', 'PUSH', 'SMS', 'UNSPECIFIED'):
        raise ValueError('Invalid channel')
    copy = GeneratedCopy.model_validate({k:args[k] for k in ('variants','rationale')})
    if {v.variant_name for v in copy.variants} != {'A','B'}:
        raise ValueError('Expected A and B')
    policy = POLICIES[CURRENT_VERSION][channel if channel != 'UNSPECIFIED' else 'EMAIL']
    for variant in copy.variants:
        if len(variant.subject)>policy['subject_max'] or len(variant.body)>policy['body_max']:
            raise ValueError('Channel length exceeded')
        text = variant.subject + variant.body
        if re.search(r'[<>{}]',text) or any(word in text for word in policy['forbidden']):
            raise ValueError('Invalid copy')
    return {**copy.model_dump(), 'channel':channel}
