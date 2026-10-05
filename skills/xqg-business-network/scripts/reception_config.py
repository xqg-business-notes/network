"""Validate bounded reception configuration; never execute remote content."""
import json
import re
from pathlib import Path
BUNDLED_DEFAULT = {'schema': 1, 'revision': '2026-10-04.1', 'copy': {'intro': '我是小强哥商业人脉，是帮你寻找合作资源的 AI 助手。创业做生意，缺什么资源？说出你的需求，帮你找到能合作的人。这里已有 {count} 份来自各行业的创业者资源档案。', 'intro_without_count': '我是小强哥商业人脉，是帮你寻找合作资源的 AI 助手。创业做生意，缺什么资源？说出你的需求，帮你找到能合作的人。', 'find_people': '找供应商、找销售渠道、找专业服务，或者找有明确需求的潜在客户，都可以直接告诉我。', 'be_found': '让别人找到你：留下产品、业务或公司介绍，整理成资源档案，微信确认后方便有需求的创业者与你对接。', 'growth': '网络正在持续扩充，早一点留下资源档案，就能早一点参与合作匹配。', 'opening_question': '你现在做生意，最想找到哪方面的帮助？', 'choose_candidate': '想对接哪一位？', 'refine_invitation': '也可以多讲讲你的产品、平台、业务阶段或具体需求，我帮你再匹配。', 'profile_invitation': '你也可以详细介绍自己的产品、服务和能提供的资源，或直接发公司介绍。我帮你整理成创业资源档案，微信确认后方便其他创业者找到你、和你对接。', 'no_match': '这次还没匹配到合适的资源。网络还在持续扩充，你可以留下具体需求，也可以把产品、服务或公司介绍发给我，方便后续匹配。', 'wechat_reminder': '请务必添加小强哥微信，把上面的资源档案复制发给他，方便其他创业者有相关需求时，小强哥能及时联系你、协助对接。', 'update_notice': '我们有优化更新了，最新版已经上线。说“帮我更新”，我就帮你升级。'}, 'presentation': {'layout': 'compact', 'fields': ['id', 'business', 'city', 'resources']}, 'flow': {'max_recommendations': 100, 'max_followup_questions': 1, 'suggest_profile_on_no_match': True, 'ask_background_on_contact': True}}

COPY_KEYS={'intro','intro_without_count','find_people','be_found','growth','opening_question','choose_candidate','refine_invitation','profile_invitation','no_match','wechat_reminder','update_notice'}

def validate(value):
    if not isinstance(value,dict) or set(value)!={'schema','revision','copy','presentation','flow'}:raise ValueError('invalid_config')
    if type(value['schema']) is not int or value['schema']!=1:raise ValueError('unsupported_schema')
    if not isinstance(value['revision'],str) or not re.fullmatch(r'[0-9A-Za-z._-]{1,40}',value['revision']):raise ValueError('invalid_revision')
    copy=value['copy']
    if not isinstance(copy,dict) or set(copy)!=COPY_KEYS:raise ValueError('invalid_copy')
    for key,text in copy.items():
        if not isinstance(text,str) or not 1<=len(text)<=600 or any(ord(c)<32 and c not in '\n\t' for c in text):raise ValueError('invalid_text')
        if 'http://' in text.lower() or 'https://' in text.lower() or '```' in text:raise ValueError('text_is_not_plain_copy')
        remaining=text.replace('{count}','') if key=='intro' else text
        if '{' in remaining or '}' in remaining:raise ValueError('unsupported_placeholder')
    if copy['intro'].count('{count}')!=1:raise ValueError('count_placeholder_required')
    display=value['presentation']
    if not isinstance(display,dict) or set(display)!={'layout','fields'}:raise ValueError('invalid_presentation')
    fields=display['fields']
    if display['layout'] not in ('cards','compact') or not isinstance(fields,list) or not 1<=len(fields)<=5:raise ValueError('invalid_presentation')
    if any(not isinstance(x,str) or x not in ('business','resources','city','company','id') for x in fields) or len(set(fields))!=len(fields) or 'business' not in fields:raise ValueError('invalid_fields')
    flow=value['flow']
    if not isinstance(flow,dict) or set(flow)!={'max_recommendations','max_followup_questions','suggest_profile_on_no_match','ask_background_on_contact'}:raise ValueError('invalid_flow')
    if type(flow['max_recommendations']) is not int or not 1<=flow['max_recommendations']<=100:raise ValueError('invalid_limit')
    if type(flow['max_followup_questions']) is not int or not 0<=flow['max_followup_questions']<=1:raise ValueError('invalid_followup')
    if any(type(flow[k]) is not bool for k in ('suggest_profile_on_no_match','ask_background_on_contact')):raise ValueError('invalid_flag')
    return json.loads(json.dumps(value,ensure_ascii=False))

def read_config(path):
    data=Path(path).read_bytes()
    if len(data)>16384:raise ValueError('config_too_large')
    return validate(json.loads(data))

def effective(raw):
    try:return {'reception_config':validate(raw),'reception_config_source':'server'}
    except (ValueError,TypeError):
        try:return {'reception_config':validate(BUNDLED_DEFAULT),'reception_config_source':'bundled'}
        except (OSError,ValueError,TypeError):return {'reception_config_source':'skill_defaults'}
