"""Portable validation for owner-confirmed catalogs. No URL fetching or file uploads."""
import ipaddress
import json
import re
from urllib.parse import urlsplit, parse_qsl

MAX_CARD_BYTES=48000

def text(value,maximum=800,empty=False):
    if not isinstance(value,str) or len(value)>maximum or (not empty and not value.strip()):raise ValueError('文字为空或过长')
    if any(ord(c)<32 and c not in '\n\t' for c in value):raise ValueError('含控制字符')
    if re.search(r'https?://|[\w.+-]+@[\w.-]+\.[a-z]{2,}|(?:\+?86[- ]?)?1[3-9](?:[- ]?\d){9}|\d{3,4}[- ]\d{7,8}|微信|wechat|电话|手机号',value,re.I):raise ValueError('正文不要含联系方式；公开链接放入链接字段')
    return value.strip()

def public_url(value):
    if not isinstance(value,str) or not 1<=len(value)<=1500 or re.search(r'[\s\\<>"\x00-\x1f]',value):raise ValueError('无效公开链接')
    u=urlsplit(value)
    if u.scheme!='https' or not u.hostname or u.username or u.password or u.fragment or u.port not in (None,443):raise ValueError('需要不含凭证的公开HTTPS链接')
    host=u.hostname.lower()
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?',host) or '..' in host or '.' not in host or host.endswith(('.local','.internal','.localhost','.lan','.home','.test','.invalid','.onion')):raise ValueError('不支持本机或内部链接')
    try:ipaddress.ip_address(host)
    except ValueError:pass
    else:raise ValueError('请使用公开网站域名')
    if any(re.search(r'token|secret|password|credential|signature|authorization|api.?key|^key$|^auth$|^sig$|^code$',k,re.I) for k,v in parse_qsl(u.query,keep_blank_values=True)):raise ValueError('不保存带访问凭证的链接')
    return value

def links(values):
    if not isinstance(values,list) or len(values)>5:raise ValueError('每组最多5个链接')
    out=[]
    for v in values:
        if not isinstance(v,dict) or set(v)!={'kind','title','url'}:raise ValueError('链接字段不匹配')
        if v['kind'] not in ('webpage','image','video','document'):raise ValueError('链接类型无效')
        out.append(dict(kind=v['kind'],title=text(v['title'],100),url=public_url(v['url'])))
    return out

def validate_portfolio(p):
    required={'entity_type','overview','offerings','cases','links'}
    if not isinstance(p,dict) or set(p)!=required:raise ValueError('业务档案字段不匹配')
    if p['entity_type'] not in ('company','opc','individual'):raise ValueError('档案类型无效')
    result=dict(entity_type=p['entity_type'],overview=text(p['overview'],800,True),offerings=[],cases=[],links=links(p['links']))
    ids=set()
    for group,maximum,required,optional in [
        ('offerings',12,{'id','kind','title','summary'},{'target_customers','markets','conditions'}),
        ('cases',12,{'id','title','summary','role'},{'customer','outcome','offering_ids','links'})]:
        if not isinstance(p[group],list) or len(p[group])>maximum:raise ValueError('产品服务和案例各最多12项')
        for entry in p[group]:
            if not isinstance(entry,dict) or not required<=set(entry) or set(entry)-required-optional:raise ValueError('条目字段不匹配')
            ident=entry['id']
            if not isinstance(ident,str) or not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_-]{0,39}',ident) or ident in ids:raise ValueError('条目标识重复或无效')
            ids.add(ident);e=dict(id=ident,title=text(entry['title'],100),summary=text(entry['summary'],1000))
            if group=='offerings':
                if entry['kind'] not in ('product','service'):raise ValueError('供给类型无效')
                e['kind']=entry['kind']
                for key in ('target_customers','markets','conditions'):
                    if key in entry:e[key]=text(entry[key],400,True)
            else:
                e['role']=text(entry['role'],200)
                for key in ('customer','outcome'):
                    if key in entry:e[key]=text(entry[key],500,True)
                if 'offering_ids' in entry:
                    refs=entry['offering_ids']
                    if not isinstance(refs,list) or len(refs)>12 or any(not isinstance(x,str) or x not in {o['id'] for o in result['offerings']} for x in refs):raise ValueError('案例对应的产品服务不存在')
                    e['offering_ids']=list(dict.fromkeys(refs))
                if 'links' in entry:e['links']=links(entry['links'])
            result[group].append(e)
    if len(json.dumps(result,ensure_ascii=False).encode())>40000:raise ValueError('业务档案过长，请精简后重新确认')
    return result

def portfolio_text(p,kind=None):
    if kind=='need':return ''  # cases and offered capabilities never imply purchasing intent
    portfolio=p.get('portfolio') or {}
    parts=[portfolio.get('overview','')]
    for key in ('offerings','cases'):
        for e in portfolio.get(key,[]):
            parts.extend(e.get(k,'') for k in ('title','summary','target_customers','markets','conditions','customer','role','outcome'))
    return '\n'.join(x for x in parts if x)
