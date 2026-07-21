import { useCallback, useEffect, useState } from "react";
import { Card, EmptyState, ErrorState, LiveStatus, LoadingState, PageHeader, ProgressBar, StatusBadge, StatusDot } from "../components/ui";
const date = value => value ? new Intl.DateTimeFormat(undefined,{dateStyle:"medium",timeStyle:"short",timeZone:"Africa/Johannesburg"}).format(new Date(value)) : "Unavailable";
const metric = value => value == null ? "Unavailable" : `${Number(value).toFixed(1)}%`;

export default function Instances() {
  const [instances,setInstances]=useState([]),[loading,setLoading]=useState(true),[error,setError]=useState(null),[lastUpdated,setLastUpdated]=useState(null);
  const fetchInstances=useCallback(async()=>{try{const res=await fetch("/api/instances",{credentials:"include"});if(!res.ok)throw new Error("Unable to load instances");setInstances(await res.json());setLastUpdated(new Date())}catch(err){setError(err.message)}finally{setLoading(false)}},[]);
  useEffect(()=>{fetchInstances();const id=setInterval(fetchInstances,30000);return()=>clearInterval(id)},[fetchInstances]);
  if(loading)return <LoadingState/>; if(error)return <ErrorState error={error}/>;
  return <div><PageHeader title="HA Instances" meta={<LiveStatus lastUpdated={lastUpdated}/>}/>
    {instances.length===0?<EmptyState>No instances found.</EmptyState>:<div className="space-y-4">{instances.map(item=><Card key={item.id} compact>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_280px]">
        <div className="min-w-0"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-sm text-purple-300">{item.client_name||"Client unavailable"}</p>
          <h2 className="mt-1 break-words text-xl font-semibold text-white">{item.name||"Unnamed instance"}</h2></div>
          <span className="inline-flex items-center gap-2 text-sm text-white"><StatusDot active={item.is_online} pulse={item.is_online}/>{item.is_online?"Online":"Offline"}</span></div>
          <dl className="mt-5 grid grid-cols-2 gap-3 text-sm sm:grid-cols-3 xl:grid-cols-4">
            <div><dt className="text-gray-500">Last report</dt><dd className="text-white">{date(item.last_seen)}</dd></div>
            <div><dt className="text-gray-500">Home Assistant</dt><dd className="text-white">{item.ha_version||"Unavailable"}</dd></div>
            <div><dt className="text-gray-500">Agent</dt><dd className="text-white">{item.agent_version||"Unavailable"}</dd></div>
            <div><dt className="text-gray-500">Local IP</dt><dd className="break-all text-white">{item.ip_address||"Local IP unavailable"}</dd></div>
            <div><dt className="text-gray-500">Tunnel</dt><dd className="text-white">{item.tunnel_status||"Unavailable"}</dd></div>
            <div><dt className="text-gray-500">Entities / automations</dt><dd className="text-white">{item.entities_count} / {item.automations_count}</dd></div>
            <div><dt className="text-gray-500">Database</dt><dd className="text-white">{item.database_size||"Unavailable"}</dd></div>
            <div><dt className="text-gray-500">Managed backup</dt><dd className="text-white">{item.managed_backup_status||"No operation"}</dd></div>
          </dl>
          <div className="mt-5 grid gap-3 sm:grid-cols-3">{[["CPU",item.cpu_usage_percent],["Memory",item.memory_usage_percent],["Disk",item.disk_usage_percent]].map(([label,value])=><div key={label}><div className="flex justify-between text-sm"><span className="text-gray-500">{label}</span><span className="text-white">{metric(value)}</span></div><ProgressBar value={value||0} className="mt-1 h-1.5"/></div>)}</div>
          <p className="mt-5 text-sm text-gray-400">Last successful managed backup: <span className="text-white">{item.last_successful_managed_backup?date(item.last_successful_managed_backup):"No successful managed backup"}</span></p>
        </div>
        <aside className="border-t border-white/10 pt-5 lg:border-l lg:border-t-0 lg:pl-6 lg:pt-0"><h3 className="font-semibold text-white">Updates</h3>
          {item.updates_available?.length?<ul className="mt-3 space-y-2">{item.updates_available.map((update,index)=><li key={index} className="flex items-start gap-2 text-sm text-amber-200"><StatusBadge status="warning">Available</StatusBadge><span className="break-words">{typeof update==="string"?update:(update.name||update.title||"Update")}</span></li>)}</ul>:<p className="mt-2 text-sm text-gray-500">No updates reported.</p>}
          <div className="mt-6 rounded-lg border border-white/10 p-3 text-sm text-gray-400">Managed backup operations remain available through the existing backup workflow.</div>
        </aside>
      </div></Card>)}</div>}
  </div>;
}
