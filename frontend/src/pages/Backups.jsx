import { useCallback, useEffect, useMemo, useState } from "react";
import { Button, Card, EmptyState, ErrorState, LiveStatus, LoadingState, PageHeader, StatusBadge } from "../components/ui";
const size=bytes=>!bytes?"Unknown":bytes>=1073741824?`${(bytes/1073741824).toFixed(1)} GB`:`${(bytes/1048576).toFixed(1)} MB`;
const date=value=>value?new Intl.DateTimeFormat(undefined,{dateStyle:"medium",timeStyle:"short",timeZone:"Africa/Johannesburg"}).format(new Date(value)):"Unknown";

export default function Backups(){
 const [server,setServer]=useState([]),[states,setStates]=useState([]),[managed,setManaged]=useState([]),[expanded,setExpanded]=useState({}),[loading,setLoading]=useState(true),[error,setError]=useState(null),[lastUpdated,setLastUpdated]=useState(null);
 const load=useCallback(async()=>{try{const [a,b]=await Promise.all([fetch("/api/admin/backups",{credentials:"include"}),fetch("/api/admin/managed-backup-state",{credentials:"include"})]);if(!a.ok||!b.ok)throw new Error("Unable to load backups");const ad=await a.json(),bd=await b.json();setServer(ad.backups||[]);setStates(bd.clients||[]);setManaged(bd.backups||[]);setLastUpdated(new Date())}catch(err){setError(err.message)}finally{setLoading(false)}},[]);
 useEffect(()=>{load();const id=setInterval(load,30000);return()=>clearInterval(id)},[load]);
 const groups=useMemo(()=>{const result={};for(const backup of managed){const key=`${backup.client_name}::${backup.instance_name}`;if(!result[key])result[key]={client:backup.client_name,instance:backup.instance_name,items:[]};result[key].items.push(backup)}return Object.entries(result)},[managed]);
 if(loading)return <LoadingState/>;if(error)return <ErrorState error={error}/>;
 return <div><PageHeader title="Backups" subtitle="Home Assistant customer archives and platform server backups are kept separate." meta={<LiveStatus lastUpdated={lastUpdated}/>}/>
  <section aria-labelledby="ha-backups"><h2 id="ha-backups" className="mb-3 text-lg font-semibold text-white">Home Assistant Backups</h2>
   <div className="space-y-3">{groups.length===0?<EmptyState>No completed managed backups stored.</EmptyState>:groups.map(([key,group])=>{const state=states.find(x=>x.client_name===group.client);const total=group.items.reduce((sum,item)=>sum+(item.size_bytes||0),0);const open=!!expanded[key];return <Card key={key} compact>
    <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between"><div><p className="font-semibold text-white">{group.client}</p><p className="text-purple-300">{group.instance}</p>
     <div className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 text-sm"><span className="text-gray-500">Last successful backup</span><span className="text-white">{date(group.items[0]?.completed_at)}</span><span className="text-gray-500">Stored backups</span><span className="text-white">{group.items.length}</span><span className="text-gray-500">Storage used</span><span className="text-white">{size(total)}</span><span className="text-gray-500">Status</span><StatusBadge status={state?.current_operation?.state||"completed"}>{state?.current_operation?.state||"Protected"}</StatusBadge></div></div>
     <Button variant="secondary" onClick={()=>setExpanded({...expanded,[key]:!open})}>{open?"Hide backups":"View backups"}</Button></div>
    {open&&<div className="mt-5 space-y-2 border-t border-white/10 pt-4">{group.items.map((backup,index)=><div key={backup.download_url} className="flex flex-col gap-3 rounded-lg bg-black/20 p-3 sm:flex-row sm:items-center sm:justify-between"><div className="min-w-0"><p className="break-words font-medium text-white">{group.instance} — {date(backup.completed_at)}</p><p className="mt-1 text-sm text-gray-500">Successful · {size(backup.size_bytes)} · {backup.backup_type}</p></div><Button as="a" href={backup.download_url} download>Download</Button></div>)}</div>}
   </Card>})}</div>
  </section>
  <section aria-labelledby="server-backups" className="mt-8"><h2 id="server-backups" className="mb-3 text-lg font-semibold text-white">Platform Server Backups</h2>
   <div className="space-y-3">{server.length===0?<EmptyState>No platform server backups recorded.</EmptyState>:server.map((backup,index)=><Card key={backup.download_url||index} compact>
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div className="min-w-0"><p className="break-words font-semibold text-white">{backup.name||backup.type||"Platform backup"}</p><p className="mt-1 text-sm text-gray-500">{backup.type||"Platform server backup"} · {size(backup.size_bytes)} · {date(backup.created_at||backup.date)}</p></div><div className="flex items-center gap-3"><StatusBadge status={backup.status||"available"}>{backup.status||"Available"}</StatusBadge>{backup.download_url&&<Button as="a" href={backup.download_url} download>Download</Button>}</div></div>
   </Card>)}</div>
  </section>
  <Card muted className="mt-8"><p className="text-sm text-gray-400">Deletion, restore, retention, and automatic managed scheduling are not available in RC1.2.</p></Card>
 </div>;
}
