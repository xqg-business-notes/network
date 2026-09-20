"""Offline public display preview; sends no draft to the service."""
import argparse
import json
from pathlib import Path
from public_identity import public_person

def preview(card):
    fields=('name','cities','companies','businesses','resources','needs')
    if not isinstance(card,dict) or set(card)!=set(fields):raise ValueError('档案字段不匹配')
    if not isinstance(card['name'],str) or not card['name'].strip():raise ValueError('请提供称呼')
    for key in fields[1:]:
        if not isinstance(card[key],list) or any(not isinstance(v,str) for v in card[key]):raise ValueError('档案字段应为文字列表')
    p={k:card[k] for k in fields[:4]}
    p['items']=[dict(kind=kind,text=text) for key,kind in [('resources','resource'),('needs','need')] for text in card[key]]
    return public_person(p)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--file',required=True);args=parser.parse_args()
    print(json.dumps(preview(json.loads(Path(args.file).read_text())),ensure_ascii=False,indent=2))
