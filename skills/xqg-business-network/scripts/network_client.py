# Connection storage keeps the pre-rename path to preserve existing identities.
"""网络客户端：查询、告知后的内部记录；不带数据库或共享凭证，不自动登记公开档案。"""
import argparse,json,os,re,sqlite3,sys,secrets,hashlib,stat
from pathlib import Path
from urllib import request,error,parse

ROOT=Path(__file__).resolve().parents[1]
CLIENT_VERSION='0.4.5'
def version_tuple(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d+\.\d+\.\d+',value):return None
    return tuple(map(int,value.split('.')))

def update_metadata(data,notify=False):
    policy=data.get('client_policy')
    if not isinstance(policy,dict):policy={}
    latest=policy.get('latest',data.get('client_latest'))
    minimum=policy.get('minimum_supported')
    newer=version_tuple(latest) is not None and version_tuple(latest)>version_tuple(CLIENT_VERSION)
    required=version_tuple(minimum) is not None and version_tuple(minimum)>version_tuple(CLIENT_VERSION)
    # Re-check at each new use; the assistant suppresses repeat notices within a conversation.
    # A persistent per-version marker would incorrectly silence later conversations.
    due=bool(newer and notify)
    return dict(client_version=CLIENT_VERSION,client_latest=latest if version_tuple(latest) else None,
        update_available=newer,update_required=required,update_notice_due=due,
        update_entry='scripts/update_skill.py',existing_service_available=not required)

def http_failure(exc):
    if exc.code==426:
        return dict(status='update_required',update_required=True,update_entry='scripts/update_skill.py',
            message='当前版本需要更新才能继续此项操作。助手可帮你完成更新，无需重新注册或手工配置。')
    if exc.code==422:return dict(status='matching_scope_required',message='这里支持按合作需求匹配人选，不提供整份通讯录。请说明想找的行业或资源。')
    if exc.code==429:return dict(status='query_limit_reached',message='查询频率或可查看档案额度已达上限。请联系小强哥协助匹配，不通过换词、换账号或遍历编号绕过限制。')
    return dict(status='not_connected' if exc.code in (401,403) else 'service_unavailable',http_status=exc.code,message='查询未成功，请核实连接或权限。')

def scrub(value):
    text=str(value or '')
    text=re.sub(r'(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)','[联系方式不展示]',text)
    text=re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}','[联系方式不展示]',text)
    return re.sub(r'(?:微信号?|wechat)\s*[:：]\s*[A-Za-z][A-Za-z0-9_-]{5,}','[联系方式不展示]',text,flags=re.I)

def project_person(p):
    """只接受展示字段；不转发服务端未知字段、联系方式、原始文件路径。"""
    return dict(person_id=str(p.get('person_id','')),name=scrub(p.get('name')),
        cities=[scrub(v) for v in p.get('cities',[])],businesses=[scrub(v) for v in p.get('businesses',[])],
        companies=[scrub(v) for v in p.get('companies',[])],
        items=[dict(item_id=str(i.get('item_id','')),kind=str(i.get('kind','')),text=scrub(i.get('text')),
            status=scrub(i.get('status'))) for i in p.get('items',[]) if i.get('kind') in ('resource','need','request')],
        last_confirmed_at=p.get('last_confirmed_at'),confirmation_status=scrub(p.get('confirmation_status')),
        identity_review_required=bool(p.get('identity_review_required')),wechat_contact_verified=p.get('wechat_contact_verified') is True,business_confirmed_at=p.get('business_confirmed_at'),match_basis=p.get('match_basis'),semantic_similarity=p.get('semantic_similarity'))

def local(config,args):
    if args.command in ('submit','delete-submission','stop-recording','register-profile','my-profile','select-person'):return dict(status='not_connected',message='提交需要连接正式网络；本地查人模式不上传记录。')
    if config.get('audience')!='operator':
        return dict(status='configuration_error',message='本地历史库仅限已配置的运营者环境，不能作为公开查询源。')
    path=Path(config['database_path']).expanduser().resolve()
    if not path.is_file():return dict(status='not_connected',message='本地数据库不可用。')
    db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    try:
        timestamp=db.execute("SELECT value FROM metadata WHERE key='imported_at'").fetchone()
        as_of=json.loads(timestamp[0]) if timestamp else None
        base=dict(status='ok',audience='operator',as_of=as_of,
            notice='内部历史资料；未自动同步，未确认独立人数、需求有效性或公开展示授权。')
        if args.command=='status':return dict(base,mode='local',search_available=True,scheduler_available='由宿主另行核实')
        if args.command=='stats' and not getattr(args,'query',None):
            return dict(base,profile_count=db.execute("SELECT COUNT(*) FROM persons WHERE status='active'").fetchone()[0],
                raw_record_count=db.execute('SELECT COUNT(*) FROM source_records').fetchone()[0],
                public_profile_count=db.execute('SELECT COUNT(*) FROM public_directory').fetchone()[0])
        conditions="status='active'";params=[]
        if args.command=='person':
            pid=args.id.upper().strip()
            if not re.fullmatch(r'A\d+',pid):return dict(status='invalid_request',message='需要真实人员编号，如 A000002。')
            pid='A'+pid[1:].zfill(6)
            alias=db.execute('SELECT person_id FROM person_alias_ids WHERE alias_id=?',(pid,)).fetchone()
            if alias:pid=alias[0]
            conditions+=' AND person_id=?';params.append(pid)
        results=[];matched=0
        for row in db.execute('SELECT * FROM persons WHERE '+conditions+' ORDER BY sequence',params):
            p=dict(row)
            for k in ['cities','businesses','companies','roles','industries']:
                p[k]=json.loads(p[k+'_json'])
            p['items']=[dict(i) for i in db.execute('SELECT item_id,kind,text,status FROM items WHERE person_id=?',(p['person_id'],))]
            p['identity_review_required']=bool(db.execute("SELECT 1 FROM identity_review WHERE (person_a=? OR person_b=?) AND status='待人工核对' LIMIT 1",(p['person_id'],p['person_id'])).fetchone())
            if args.command in ('search','stats'):
                if args.city.casefold() not in ' '.join(p['cities']).casefold():continue
                import importlib.util
                spec=importlib.util.spec_from_file_location('xqg_semantics',Path(__file__).with_name('semantic_search.py'));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
                candidate=module.rank(p,args.query,args.kind)
                if candidate is None:continue
                p=candidate[1]

            matched+=1
            if args.command!='stats' and len(results)<args.limit:results.append(project_person(p))
        if args.command=='stats':return dict(base,matched_profile_count=matched,query=args.query,city=args.city,kind=args.kind)
        return dict(base,matched_profile_count=matched,results=results)
    finally:db.close()

def ssh_operator(config,args):
    import subprocess,shlex
    if config.get('audience')!='operator' or args.command not in ('status','stats','search','person'):
        return dict(status='configuration_error',message='仅运营者可通过SSH执行只读查询。')
    host=config['ssh_destination']
    if not re.fullmatch(r'[A-Za-z0-9_.@-]+',host) or host.startswith('-'):raise ValueError('invalid host')
    argv=['/usr/bin/python3',config['remote_client'],'--config',config['remote_config'],args.command]
    if args.command=='person':argv+=['--id',args.id]
    if args.command=='stats' and getattr(args,'query',None):
        argv+=['--query',args.query,'--city',args.city]
        if args.kind:argv+=['--kind',args.kind]
    if args.command=='search':
        argv+=['--query',args.query,'--city',args.city,'--limit',str(args.limit)]
        if args.kind:argv+=['--kind',args.kind]
    try:
        result=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8','-i',str(Path(config['identity_file']).expanduser()),host,shlex.join(argv)],capture_output=True,text=True,timeout=20,check=True)
        return json.loads(result.stdout)
    except (subprocess.SubprocessError,ValueError):
        return dict(status='not_connected',message='无法连接Mac mini主库；没有回退到MacBook旧快照。')

class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

def open_request(req, retry=False):
    # Retry transient transport failures only. Never retry denied or rate-limited requests.
    import time
    for attempt in range(2 if retry else 1):
        try:return request.build_opener(NoRedirect).open(req,timeout=8)
        except error.HTTPError as exc:
            if not retry or attempt or exc.code not in (502,503,504):raise
            exc.close()
        except (error.URLError,TimeoutError,ConnectionError):
            if not retry or attempt:raise
        time.sleep(0.4)

def automatic_token(base_url):
    # Persist before enrollment: retry or offline failure reuses the same identity.
    folder=Path.home()/'.config/xqg-entrepreneur-network';folder.mkdir(parents=True,exist_ok=True,mode=0o700)
    dest=folder/('session-'+hashlib.sha256(base_url.encode()).hexdigest()[:20]+'.key')
    try:
        fd=os.open(dest,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as f:f.write(secrets.token_urlsafe(32))
    except FileExistsError:pass
    if dest.is_symlink():raise ValueError('unsafe session file')
    fd=os.open(dest,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
    with os.fdopen(fd) as f:
        info=os.fstat(f.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:raise ValueError('unsafe session file')
        token=f.read(129).strip()
    if not re.fullmatch(r'[A-Za-z0-9_-]{43}',token):raise ValueError('invalid session file')
    req=request.Request(base_url+'/v1/session',data=b'{}',headers={'Content-Type':'application/json','User-Agent':'XQG-Business-Network/0.4.5','Authorization':'Bearer '+token},method='POST')
    with open_request(req, retry=True) as response:
        data=json.loads(response.read(4096))
    if data.get('session_ready') is not True:raise ValueError('session unavailable')
    return token

def remote(config,args):
    base_url=config.get('base_url','').rstrip('/')
    u=parse.urlsplit(base_url)
    if u.scheme!='https' or not u.hostname or u.username or u.password or u.query or u.fragment:
        return dict(status='configuration_error',message='共享连接需要运营者提供的 HTTPS 服务地址。')
    endpoint={'status':'capabilities','stats':'stats','search':'search','person':'person','submit':'submissions','delete-submission':'submissions/delete','stop-recording':'recording/stop','register-profile':'registrations','my-profile':'registration','select-person':'referrals'}[args.command]
    payload={}
    if args.command=='search':
        payload=dict(query=args.query,city=args.city,kind=args.kind,limit=args.limit)
        if getattr(args,'offset',0):payload['offset']=args.offset
    elif args.command=='stats' and getattr(args,'query',None):payload=dict(query=args.query,city=args.city,kind=args.kind)
    elif args.command=='person':payload=dict(person_id=args.id)
    elif args.command=='submit':
        payload=dict(id=args.id,scope=args.scope,text=Path(args.file).read_text(),notice_shown=args.notice_shown,notice_version='2026-09-14-v3' if args.scope=='conversation_turn' else '2026-09-13-v2')
    elif args.command=='register-profile':payload=dict(id=args.id,confirmed=args.confirmed,card=json.loads(Path(args.file).read_text()))
    elif args.command=='select-person':payload=dict(id=args.request_id,person_id=args.person_id,notice_shown=args.notice_shown)
    elif args.command=='delete-submission':payload=dict(id=args.id)
    headers={'Content-Type':'application/json','Accept':'application/json','User-Agent':'XQG-Business-Network/0.4.5'}
    token_var=config.get('token_env')
    token_path=config.get('token_file')
    automatic=config.get('automatic_session',False)
    if type(automatic) is not bool or (automatic and (token_var or token_path)):
        raise ValueError('ambiguous credential source')
    if automatic:
        headers['Authorization']='Bearer '+automatic_token(base_url)
    elif not (token_var or token_path):
        return dict(status='not_connected',message='连接配置不完整，请更新官方Skill；不需要人工激活。')
    if token_var or token_path:
        if token_var and token_path:raise ValueError('ambiguous credential source')
        if token_path:
            secret_file=Path(token_path).expanduser()
            if os.name=='posix' and secret_file.stat().st_mode & 0o077:
                return dict(status='configuration_error',message='凭证文件权限过宽，请设置为仅本人可读写。')
            token=secret_file.read_text().strip()
        else:token=os.environ.get(token_var)
        if not token:return dict(status='not_connected',message='尚未配置查询凭证，请通过运营者提供的方式连接；不要在聊天中粘贴密钥。')
        if not 30<=len(token)<=128 or not re.fullmatch(r'[A-Za-z0-9_-]+',token):raise ValueError('invalid credential')
        headers['Authorization']='Bearer '+token
    encoded=json.dumps(payload,ensure_ascii=False).encode()
    if len(encoded)>8192:return dict(status='invalid_request',message='内容超出提交长度，请精简档案后重新请本人确认；本次未保存。')
    req=request.Request(base_url+'/v1/'+endpoint,data=encoded,headers=headers,method='POST')
    with open_request(req, retry=args.command in ('status','stats','search','person','my-profile')) as response:
        body=response.read(1024*1024+1)
        if len(body)>1024*1024:raise ValueError('response too large')
        data=json.loads(body)
    if data.get('status')!='ok':return dict(status='service_unavailable',message='共享查询暂不可用。')
    result=dict(status='ok',audience='public',retrieval_mode=data.get('retrieval_mode'),as_of=data.get('as_of'),**update_metadata(data,notify=args.command=='status'))
    if args.command=='status':
        import importlib.util
        spec=importlib.util.spec_from_file_location('xqg_reception_config',Path(__file__).with_name('reception_config.py'));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return dict(result,**module.effective(data.get('reception_config')),mode='http',referral_available=bool(data.get('referral_available')),semantic_search_available=bool(data.get('semantic_search_available')),search_available=bool(data.get('search_available')),filtered_stats_available=bool(data.get('filtered_stats_available')),submission_available=bool(data.get('submission_available')),conversation_turn_available=bool(data.get('conversation_turn_available')),registration_available=bool(data.get('registration_available')),scheduler_available='由宿主另行核实')
    if args.command in ('register-profile','my-profile'):
        return dict(result,**{k:data[k] for k in ('saved','registered','person_id','revision','card','matching_open','registration_status','confirmed_at','replayed') if k in data})
    if args.command=='select-person':return dict(result,**{k:data[k] for k in ('referral_id','stage','saved','replayed') if k in data})
    if args.command=='submit':return dict(result,submission_id=data.get('submission_id'),saved=data.get('saved') is True,registered=False,retention_days=data.get('retention_days'))
    if args.command=='stop-recording':return dict(result,recording_stopped=data.get('recording_stopped') is True)
    if args.command=='delete-submission':return dict(result,deleted=data.get('deleted') is True)
    if args.command=='stats':return dict(result,public_profile_count=data.get('public_profile_count'),matched_profile_count=data.get('matched_profile_count'),query=data.get('query'),city=data.get('city'),kind=data.get('kind'),resource_count=data.get('resource_count'),need_count=data.get('need_count'))
    return dict(result,scope_limited=data.get('scope_limited') is True,matched_profile_count=data.get('matched_profile_count'),next_offset=data.get('next_offset'),results=[project_person(p) for p in data.get('results',[])[:args.limit]])

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',help='连接配置路径；不显示配置内容')
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('status')
    stats=sub.add_parser('stats');stats.add_argument('--query');stats.add_argument('--city',default='');stats.add_argument('--kind',choices=['resource','need'])
    s=sub.add_parser('search');s.add_argument('--query',required=True);s.add_argument('--city',default='')
    s.add_argument('--kind',choices=['resource','need']);s.add_argument('--limit',type=int,default=100);s.add_argument('--offset',type=int,default=0);s.add_argument('--all',action='store_true')
    p=sub.add_parser('person');p.add_argument('--id',required=True);p.set_defaults(limit=1)
    subm=sub.add_parser('submit');subm.add_argument('--file',required=True);subm.add_argument('--scope',choices=['profile_summary','conversation_excerpt','conversation_turn'],required=True);subm.add_argument('--id',required=True);subm.add_argument('--notice-shown',action='store_true',required=True)
    sub.add_parser('stop-recording')
    sub.add_parser('my-profile')
    registration=sub.add_parser('register-profile');registration.add_argument('--file',required=True);registration.add_argument('--id',required=True);registration.add_argument('--confirmed',action='store_true',required=True)
    delete=sub.add_parser('delete-submission');delete.add_argument('--id',required=True)
    selection=sub.add_parser('select-person');selection.add_argument('--person-id',required=True);selection.add_argument('--request-id',required=True);selection.add_argument('--notice-shown',action='store_true',required=True)
    args=parser.parse_args()
    if hasattr(args,'limit'):args.limit=max(1,min(100,args.limit))
    if args.command=='stats' and ((args.query is not None and not args.query.strip()) or (not args.query and (args.city or args.kind))):return dict(status='invalid_request',message='按条件统计需要提供查询关键词。')
    if args.command=='search' and not args.query.strip():return dict(status='invalid_request',message='请先明确要找的需求或资源，不支持空查询枚举。')
    # Reception always uses the distributed public endpoint. Operator access is explicit.
    path=Path(args.config or ROOT/'service.json').expanduser()
    if not path.is_file():return dict(status='not_connected',search_available=False,message='尚未连接创业者资源网络。可以先整理档案卡，通过小强哥完成登记或申请引荐。')
    try:
        config=json.loads(path.read_text())
        if config.get('mode')=='ssh_operator':return ssh_operator(config,args)
        if config.get('mode')=='local':return local(config,args)
        if config.get('mode')=='http':
            result=remote(config,args)
            if args.command=='search' and getattr(args,'all',False) and result.get('status')=='ok':
                seen={p['person_id'] for p in result['results']}
                for _ in range(19):
                    offset=result.get('next_offset')
                    if offset is None:break
                    args.offset=offset
                    try:page=remote(config,args)
                    except (OSError,ValueError,error.URLError):
                        result['partial']=True;result['continuation_status']='service_unavailable';break
                    if page.get('status')!='ok':
                        result['partial']=True;result['continuation_status']=page.get('status');break
                    for person in page['results']:
                        if person['person_id'] not in seen:result['results'].append(person);seen.add(person['person_id'])
                    result['next_offset']=page.get('next_offset')
                    result['scope_limited']=bool(result.get('scope_limited') or page.get('scope_limited'))
                result['complete']=result.get('next_offset') is None and not result.get('partial',False) and not result.get('scope_limited',False)
            return result
        return dict(status='configuration_error',message='未识别的连接方式。')
    except error.HTTPError as exc:
        return http_failure(exc)
    except (OSError,ValueError,KeyError,TypeError,AttributeError,sqlite3.Error,error.URLError):
        return dict(status='service_unavailable',message='无法完成查询，请检查连接配置或服务状态；未返回任何匹配结果。')

if __name__=='__main__':
    print(json.dumps(main(),ensure_ascii=False,indent=2))
