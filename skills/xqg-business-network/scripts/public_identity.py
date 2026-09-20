"""Mask display names at the public API boundary; keep original profiles intact."""
import re

COMPOUND=('欧阳','司马','上官','诸葛','东方','皇甫','尉迟','公孙','慕容','司徒','司空','夏侯','令狐','宇文','长孙')

def mask_name(value):
    name=str(value or '').strip()
    if not name:return '＊'
    if re.fullmatch(r'(?:[\u4e00-\u9fff]{1,2}＊{1,2}|[A-Za-z]＊＊＊[\u4e00-\u9fff]?|＊)',name):return name
    if re.match(r'[\u4e00-\u9fff]',name):
        head=next((x for x in COMPOUND if name.startswith(x) and len(name)>2),name[0])
        return head+('＊' if len(name)-len(head)<=1 else '＊＊')
    if re.match('[A-Za-z]',name):
        surname=name[-1] if re.fullmatch(r'[A-Za-z]+[\u4e00-\u9fff]',name) else ''
        return name[0]+'＊＊＊'+surname
    return '＊'

def public_person(person):
    original=person.get('name','');masked=mask_name(original)
    # Also remove this person's exact name/aliases when repeated in their introduction.
    base=re.split(r'[（(]',original,maxsplit=1)[0]
    aliases=[original]+re.split(r'\s+|[/／|｜]',base)
    aliases=sorted({x.strip() for x in aliases if len(x.strip())>=2 and '＊' not in x},key=len,reverse=True)
    def redact(value):
        if isinstance(value,str):
            for alias in aliases:
                if re.fullmatch(r'[A-Za-z]+',alias):value=re.sub(r'(?<![A-Za-z])'+re.escape(alias)+r'(?![A-Za-z])',lambda m:masked,value,flags=re.I)
                else:value=value.replace(alias,masked)
            return value
        if isinstance(value,list):return [redact(x) for x in value]
        if isinstance(value,dict):return {k:(v if k in ('person_id','item_id') else redact(v)) for k,v in value.items()}
        return value
    result=redact(person);result['name']=masked;result['name_masked']=True
    return result
