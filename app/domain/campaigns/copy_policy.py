"""Versioned demo copy policy, not a delivery-provider or legal compliance policy."""
POLICIES = {1: {
    'EMAIL': {'subject_max':120, 'body_max':5000, 'forbidden':['무조건 당첨'], 'required':[]},
    'PUSH': {'subject_max':60, 'body_max':300, 'forbidden':['무조건 당첨'], 'required':[]},
    'SMS': {'subject_max':0, 'body_max':500, 'forbidden':['무조건 당첨'], 'required':[]},
}}
CURRENT_VERSION = 1
