"""Auditable concept expansion. Candidate evidence is interpreted by the receiving AI.

This is not an embedding model; explicit geographic and platform context is retained.
"""
import re

OVERSEAS = ('跨境','出海','海外','外贸','进出口','进口','出口','国际贸易','国际物流','国际运邮','海外仓','亚马逊','amazon','tiktok','tikok','虾皮','shopee','lazada','速卖通','aliexpress','temu','ebay','shopify','独立站','reddit','facebook','instagram')
REGIONS = ('法国','意大利','美国','加拿大','香港','澳门','新加坡','日本','马来西亚','越南','泰国','印度','印度尼西亚','印尼','菲律宾','韩国','英国','德国','西班牙','葡萄牙','澳大利亚','澳洲','新西兰','俄罗斯','巴西','墨西哥','阿联酋','迪拜','沙特','南非','欧洲','北美','南美','东南亚','中东','非洲','拉美','纽约','洛杉矶','旧金山','硅谷','多伦多','温哥华','伦敦','巴黎','东京','大阪','吉隆坡','曼谷','美区','美國','香港','澳門','新加坡','日本','馬來西亞','臺灣','台湾','台北')
BROAD = {'跨境','跨境电商','跨境出海','出海','海外','海外生意','国外生意','国际业务','跨境业务','海外业务','海外资源','跨境资源','出海资源'}
ALIASES = [('亚马逊','amazon'),('tiktok','tikok','tiktok shop'),('虾皮','shopee'),('ai','人工智能','智能体'),('海外仓','海外倉'),('新加坡','singapore'),('美国','美國','美区','united states'),('加拿大','canada'),('法国','france'),('意大利','italy'),('日本','japan'),('马来西亚','馬來西亞','malaysia'),('澳门','澳門','macau'),('香港','hong kong')]

def contains(text, term):
    text=text.casefold();term=term.casefold()
    if re.fullmatch(r'[a-z0-9 ]+',term):
        return re.search(r'(?<![a-z0-9])'+re.escape(term)+r'(?![a-z0-9])',text) is not None
    return term in text

def groups(query):
    out=[]
    for term in query.casefold().split():
        if term in BROAD:out.append(OVERSEAS+REGIONS)
        else:out.append(next((g for g in ALIASES if term in g),(term,)))
    return out

def matches(text, query):
    return all(any(contains(text,t) for t in group) for group in groups(query))

def rank(p,query,kind):
    from profile_schema import portfolio_text
    businesses=' '.join(p.get('businesses',[]))+ ' ' + portfolio_text(p,kind)
    items=[i for i in p.get('items',[]) if kind is None or i['kind']==kind]
    relevant=[i for i in items if matches(i['text'],query)]
    business=matches(businesses,query)
    geo=' '.join(p.get('cities',[])+p.get('companies',[]))
    alltext=' '.join([businesses,geo]+[i['text'] for i in items])
    if not matches(alltext,query):return None
    if kind=='need' and not relevant:return None
    if kind=='resource' and not (relevant or business):return None
    result=dict(p)
    if kind:result['items']=relevant
    result['match_basis']='business_or_resource' if business or any(i['kind']=='resource' for i in relevant) else ('stated_need' if relevant else 'regional_connection')
    if kind=='resource' and not relevant:result['confirmation_status']='业务相关线索，具体可提供的资源仍需确认；'+str(p.get('confirmation_status',''))
    return 100*bool(relevant)+30*business+5*matches(geo,query),result
