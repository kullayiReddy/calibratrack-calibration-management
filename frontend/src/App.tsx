import { useEffect, useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import { Activity, AlertTriangle, ArrowDownRight, ArrowUpRight, Bell, CheckCircle2, ChevronDown, CircleGauge, ClipboardCheck, Clock3, Download, Gauge, LayoutDashboard, Search, Settings2, ShieldCheck, Wrench } from 'lucide-react';
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

const API = (import.meta as any).env.VITE_API_URL || 'http://localhost:8000/api/v1';
type Summary = { active_instruments:number; due_soon:number; overdue:number; compliance_rate:number; failed_calibrations:number; missing_or_invalid_certificates:number; prohibited_uses:number; open_corrective_actions:number; downtime_minutes:number; critical_alerts:number };
type Rows = Record<string, any[]>;
const emptySummary:Summary={active_instruments:0,due_soon:0,overdue:0,compliance_rate:0,failed_calibrations:0,missing_or_invalid_certificates:0,prohibited_uses:0,open_corrective_actions:0,downtime_minutes:0,critical_alerts:0};
const nav=[['Overview',LayoutDashboard],['Instrument inventory',Gauge],['Calibration schedule',Clock3],['Certificates',ClipboardCheck],['Production usage',Activity],['Work orders',Wrench],['Alerts & exceptions',Bell]] as const;
const siteAreas:Record<string,string>={'North Plant':'Plant A','South Plant':'Plant B','Quality Lab':'Lab 1','All sites':''};

function pageData(page:string, rows:Rows, assets:any[]) {
  const latest = new Map<string,any>();
  for (const c of [...(rows.calibrations||[])].sort((a,b)=>String(a.calibration_date).localeCompare(String(b.calibration_date)))) latest.set(c.asset_id,c);
  const inventory=(rows.assets||[]).map(a=>{
    const c=latest.get(a.asset_id); const due=c?.next_due_date; const today=new Date().toISOString().slice(0,10);
    return {id:a.asset_id,name:a.asset_name,location:a.location,criticality:a.criticality,next_due:due||'—',status:a.lifecycle_status==='RETIRED'?'Retired':!c?'No calibration':c.result!=='PASS'?'Failed':due<today?'Overdue':due<=new Date(Date.now()+30*86400000).toISOString().slice(0,10)?'Due soon':'Compliant'};
  });
  const definitions:Record<string,{description:string;columns:[string,string][];items:any[]}>= {
    'Instrument inventory':{description:`${inventory.length} instruments at the selected site`,columns:[['id','Asset ID'],['name','Instrument'],['location','Location'],['criticality','Criticality'],['next_due','Next calibration'],['status','Status']],items:inventory},
    'Calibration schedule':{description:'Calibration events, derived outcomes, and next due dates',columns:[['calibration_id','Calibration ID'],['asset_id','Asset'],['calibration_date','Calibration date'],['result','Result'],['next_due_date','Next due date'],['performed_by','Performed by']],items:rows.calibrations||[]},
    'Certificates':{description:'Certificate records and quality verification status',columns:[['certificate_number','Certificate number'],['asset_id','Asset'],['calibration_id','Calibration'],['issue_date','Issue date'],['valid_until','Valid until'],['verification_status','Verification']],items:rows.certificates||[]},
    'Production usage':{description:'Recorded use decisions with their historical compliance reasons',columns:[['used_at','Used at'],['use_id','Use ID'],['asset_id','Asset'],['production_batch_id','Batch'],['decision','Decision'],['decision_reason','Decision reason']],items:rows.uses||[]},
    'Work orders':{description:'Maintenance work orders and corrective action follow-up',columns:[['work_order_id','Work order'],['asset_id','Asset'],['work_order_type','Type'],['priority','Priority'],['status','Status'],['assigned_to','Assigned to'],['downtime_minutes','Downtime (min)']],items:rows.work_orders||[]},
    'Alerts & exceptions':{description:'Compliance alerts requiring acknowledgement or resolution',columns:[['alert_type','Alert'],['asset_id','Asset'],['severity','Severity'],['description','Description'],['status','Status'],['created_at','Created']],items:rows.alerts||[]},
  };
  return definitions[page];
}

function App(){
  const [page,setPage]=useState('Overview');
  const [data,setData]=useState<Summary>(emptySummary);
  const [trend,setTrend]=useState<any[]>([]);
  const [rows,setRows]=useState<Rows>({});
  const [query,setQuery]=useState('');
  const [error,setError]=useState('');
  const [authenticated,setAuthenticated]=useState(Boolean(localStorage.getItem('calibra_token')));
  const [username,setUsername]=useState('quality');
  const [password,setPassword]=useState('CalibraTrack-Demo-2026!');
  const [loginError,setLoginError]=useState('');
  const [site,setSite]=useState(localStorage.getItem('calibra_site')||'North Plant');
  const [siteOpen,setSiteOpen]=useState(false);

  useEffect(()=>{
    if(!authenticated)return;
    const token=localStorage.getItem('calibra_token');
    const headers:Record<string,string>=token?{Authorization:`Bearer ${token}`} : {};
    const load=async()=>{
      try {
        const [summary,trends,...collections]=await Promise.all([
          fetch(`${API}/dashboard/summary`,{headers}).then(r=>r.ok?r.json():Promise.reject(new Error('Dashboard request failed'))),
          fetch(`${API}/dashboard/trends`,{headers}).then(r=>r.ok?r.json():Promise.reject(new Error('Trend request failed'))),
          ...[
            ['assets',`${API}/assets?page_size=200`],['calibrations',`${API}/calibrations?page_size=200`],
            ['certificates',`${API}/certificates`],['uses',`${API}/production-uses?page_size=200`],
            ['work_orders',`${API}/work-orders`],['alerts',`${API}/alerts`],
            ['actions',`${API}/corrective-actions`],['assessments',`${API}/impact-assessments`],
          ].map(async([key,url])=>[key,await fetch(url,{headers}).then(r=>r.ok?r.json():Promise.reject(new Error(`${key} request failed`)))])
        ]);
        setData(summary);setTrend(trends.calibration_results||[]);setRows(Object.fromEntries(collections as [string,any[]][]));setError('');
      } catch(e) { setError(e instanceof Error?e.message:'Could not load operational data'); }
    };
    void load();
  },[authenticated]);

  const signIn=async(e:FormEvent)=>{
    e.preventDefault();setLoginError('');
    try {const r=await fetch(`${API}/auth/login`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username,password})});if(!r.ok)throw new Error('Sign-in failed. Check the account and API status.');const body=await r.json();localStorage.setItem('calibra_token',body.access_token);setAuthenticated(true);}
    catch(err){setLoginError(err instanceof Error?err.message:'Could not reach the API');}
  };
  const signOut=()=>{localStorage.removeItem('calibra_token');setAuthenticated(false);};
  const chooseSite=(name:string)=>{setSite(name);localStorage.setItem('calibra_site',name);setSiteOpen(false);};
  const area=siteAreas[site]??'';
  const siteAssets=(rows.assets||[]).filter(a=>!area||String(a.location).startsWith(area));
  const siteAssetIds=new Set(siteAssets.map(a=>a.asset_id));
  const siteRows:Rows={...rows,assets:siteAssets};
  for(const key of ['calibrations','certificates','uses','work_orders','alerts','actions','assessments']) siteRows[key]=(rows[key]||[]).filter(r=>!r.asset_id||siteAssetIds.has(r.asset_id));
  const filteredAssets=useMemo(()=>siteAssets.filter(a=>`${a.asset_id} ${a.asset_name} ${a.location} ${a.serial_number}`.toLowerCase().includes(query.toLowerCase())),[siteAssets,query]);
  const cards=[
    {label:'Active instruments',value:data.active_instruments.toLocaleString(),change:'Across all locations',icon:Gauge,color:'blue'},
    {label:'Calibration compliance',value:`${data.compliance_rate}%`,change:'Within valid calibration window',icon:ShieldCheck,color:'green'},
    {label:'Overdue instruments',value:data.overdue,change:'Requires immediate attention',icon:AlertTriangle,color:'red'},
    {label:'Due in next 30 days',value:data.due_soon,change:'Upcoming calibration workload',icon:Clock3,color:'amber'},
  ];
  const config=pageData(page,siteRows,siteAssets);
  const shown=config?config.items.filter(item=>JSON.stringify(item).toLowerCase().includes(query.toLowerCase())).slice(0,200):[];
  const exportReport=async()=>{const token=localStorage.getItem('calibra_token');const r=await fetch(`${API}/reports/compliance`,{headers:token?{Authorization:`Bearer ${token}`}:{}});if(!r.ok){setError('Could not export report');return;}const file=URL.createObjectURL(await r.blob());const link=document.createElement('a');link.href=file;link.download='calibratrack-compliance-report.json';link.click();URL.revokeObjectURL(file);};

  if(!authenticated)return <div className="login-page"><form className="login-card" onSubmit={signIn}><div className="brand-mark"><CircleGauge size={20}/></div><h1>CalibraTrack</h1><p>Sign in to quality operations</p><label>Username<input value={username} onChange={e=>setUsername(e.target.value)} autoComplete="username"/></label><label>Password<input value={password} onChange={e=>setPassword(e.target.value)} type="password" autoComplete="current-password"/></label>{loginError&&<div className="login-error">{loginError}</div>}<button type="submit">Sign in</button><small>Local demo account: quality / CalibraTrack-Demo-2026!</small></form></div>;

  return <div className="shell"><aside className="sidebar">
    <div className="brand"><div className="brand-mark"><CircleGauge size={20}/></div><div><strong>calibra<span>track</span></strong><small>QUALITY OPERATIONS</small></div></div>
    <div className="site-picker"><button className="plant" aria-expanded={siteOpen} onClick={()=>setSiteOpen(!siteOpen)}><div className="plant-dot"/><div><b>{site}</b><small>Production site</small></div><ChevronDown size={15}/></button>{siteOpen&&<div className="site-menu" role="menu">{Object.keys(siteAreas).map(name=><button role="menuitem" className={site===name?'active':''} key={name} onClick={()=>chooseSite(name)}><span className="plant-dot"/>{name}{site===name&&<CheckCircle2 size={14}/>}</button>)}</div>}</div>
    <div className="nav-label">WORKSPACE</div><nav>{nav.map(([label,Icon])=><button className={page===label?'selected':''} key={label} onClick={()=>{setPage(label);setQuery('');}}><Icon size={17}/><span>{label}</span>{label==='Alerts & exceptions'&&<em>{data.critical_alerts}</em>}</button>)}</nav>
    <div className="sidebar-bottom"><button onClick={()=>setPage('Settings')}><Settings2 size={17}/>Settings</button><div className="user"><div className="avatar">JD</div><div><b>Jordan Davis</b><small>Quality Engineer</small></div><button className="logout" onClick={signOut}>Sign out</button></div></div>
  </aside><main className="main"><header className="topbar"><div className="crumb">Operations <span>/</span> {page}</div><div className="top-actions"><div className="live"><i/> System operational</div><button className="icon-btn" onClick={()=>setPage('Alerts & exceptions')} aria-label="Open alerts"><Bell size={18}/><i/></button><div className="avatar top-avatar">JD</div></div></header>
    <div className="content"><div className="headline"><div><div className="eyebrow">TUESDAY, OCTOBER 28, 2026 <span>·</span> {site.toUpperCase()}</div><h1>{page==='Overview'?'Good morning, Jordan':page}</h1><p>{page==='Overview'?'Here’s your calibration and compliance overview.':config?.description||'Manage your site and account preferences.'}</p></div><button className="export" onClick={()=>void exportReport()}><Download size={16}/> Export report</button></div>
      {error&&<div className="notice">{error}</div>}
      {page==='Overview'?<>
        <div className="kpis">{cards.map(c=><div className="kpi" key={c.label}><div className="kpi-top"><span>{c.label}</span><i className={`kpi-icon ${c.color}`}><c.icon size={17}/></i></div><strong>{c.value}</strong><small>{c.change}</small></div>)}</div>
        <div className="middle"><section className="panel trend-panel"><div className="panel-head"><div><h2>Calibration performance</h2><p>Completed calibration events over time</p></div><span className="select static-select">By month</span></div><div className="legend"><span><i className="green-dot"/>Passed</span><span><i className="red-dot"/>Failed</span><span><i className="gray-dot"/>Indeterminate</span></div><div className="chart"><ResponsiveContainer width="100%" height="100%"><AreaChart data={trend} margin={{top:8,right:8,left:-20,bottom:0}}><defs><linearGradient id="pass" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#14a67a" stopOpacity={.2}/><stop offset="100%" stopColor="#14a67a" stopOpacity={0}/></linearGradient></defs><CartesianGrid stroke="#edf0f3" vertical={false}/><XAxis dataKey="month" axisLine={false} tickLine={false} tick={{fill:'#87919e',fontSize:11}} dy={8}/><YAxis axisLine={false} tickLine={false} tick={{fill:'#87919e',fontSize:11}}/><Tooltip/><Area type="monotone" dataKey="PASS" stroke="#139876" strokeWidth={2.5} fill="url(#pass)"/><Area type="monotone" dataKey="FAIL" stroke="#dc6a63" strokeWidth={2} fill="none"/><Area type="monotone" dataKey="INDETERMINATE" stroke="#9ca6b2" strokeWidth={1.5} fill="none"/></AreaChart></ResponsiveContainer></div></section>
          <section className="panel alerts-panel"><div className="panel-head"><div><h2>Needs attention</h2><p>Priority items for your review</p></div></div><div className="attention"><div className="attention-icon red-bg"><AlertTriangle size={17}/></div><div><b>{data.overdue} instruments overdue</b><p>Calibration date has passed</p></div><ArrowUpRight size={15}/></div><div className="attention"><div className="attention-icon amber-bg"><ClipboardCheck size={17}/></div><div><b>{data.missing_or_invalid_certificates} certificates to review</b><p>Verification is required</p></div><ArrowDownRight size={15}/></div><div className="attention"><div className="attention-icon blue-bg"><Wrench size={17}/></div><div><b>{data.open_corrective_actions} corrective actions open</b><p>Review action owners and due dates</p></div><ArrowUpRight size={15}/></div><button className="all-alerts" onClick={()=>setPage('Alerts & exceptions')}>View all alerts <span>→</span></button></section></div>
        <section className="panel inventory"><div className="panel-head"><div><h2>Instrument inventory</h2><p>Instruments at {site}</p></div><div className="inventory-tools"><label><Search size={15}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search instruments"/></label><button className="view-all" onClick={()=>setPage('Instrument inventory')}>View inventory <span>→</span></button></div></div><AssetTable items={filteredAssets.slice(0,4)} rows={siteRows}/><div className="table-foot"><span>Showing {Math.min(4,filteredAssets.length)} of {filteredAssets.length} instruments at {site}</span><button className="view-all" onClick={()=>setPage('Instrument inventory')}>Open inventory →</button></div></section>
      </>:config?<section className="panel record-panel"><div className="panel-head"><div><h2>{page}</h2><p>{config.description} · {shown.length} shown</p></div><label className="record-search"><Search size={15}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder={`Search ${page.toLowerCase()}`}/></label></div><div className="table-wrap"><table><thead><tr>{config.columns.map(([key,label])=><th key={key}>{label.toUpperCase()}</th>)}</tr></thead><tbody>{shown.map((item,i)=><tr key={item.id||item.use_id||item.calibration_id||item.certificate_id||item.work_order_id||item.alert_id||i}>{config.columns.map(([key])=><td key={key}>{key==='decision'||key==='result'||key==='status'||key==='verification_status'||key==='severity'?<span className={`status ${String(item[key]||'').toLowerCase().replace(/_/g,'-')}`}>{String(item[key]||'—').replace(/_/g,' ')}</span>:key==='decision_reason'||key==='description'?<span className="reason-cell" title={item[key]}>{item[key]||'—'}</span>:item[key]??'—'}</td>)}</tr>)}</tbody></table>{shown.length===0&&<div className="empty-state">No records match this site and search.</div>}</div><div className="table-foot"><span>Filtered to {site}</span><span>Records are loaded from the CalibraTrack API</span></div></section>:<section className="panel record-panel"><h2>Settings</h2><p>Current production site: {site}</p><button className="export" onClick={signOut}>Sign out</button></section>}
      <footer><span><CheckCircle2 size={14}/> Data loaded from the API</span><span>CalibraTrack <b>v1.0.0</b> · Monitoring & decision support</span></footer>
    </div></main></div>;
}

function AssetTable({items,rows}:{items:any[];rows:Rows}){
  const latest=new Map<string,any>();for(const c of [...(rows.calibrations||[])].sort((a,b)=>String(a.calibration_date).localeCompare(String(b.calibration_date))))latest.set(c.asset_id,c);
  const today=new Date().toISOString().slice(0,10);
  return <div className="table-wrap"><table><thead><tr><th>INSTRUMENT</th><th>LOCATION</th><th>CRITICALITY</th><th>NEXT CALIBRATION</th><th>STATUS</th></tr></thead><tbody>{items.map((a,i)=>{const c=latest.get(a.asset_id);const due=c?.next_due_date;const status=!c?'No calibration':c.result!=='PASS'?'Failed':due<today?'Overdue':due<=new Date(Date.now()+30*86400000).toISOString().slice(0,10)?'Due soon':'Compliant';return <tr key={a.asset_id}><td><div className="asset-cell"><div className="asset-icon">{i%2?<Activity size={16}/>:<Gauge size={16}/>}</div><div><b>{a.asset_name}</b><small>{a.asset_id}</small></div></div></td><td>{a.location}</td><td><span className={`critical ${String(a.criticality).toLowerCase()}`}><i/>{a.criticality}</span></td><td>{due||'—'}</td><td><span className={`status ${status.toLowerCase().replace(' ','-')}`}><i/>{status}</span></td></tr>})}</tbody></table>{items.length===0&&<div className="empty-state">No instruments found for this site.</div>}</div>;
}

export default App;
