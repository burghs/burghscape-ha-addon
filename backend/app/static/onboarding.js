(function(){"use strict";
const steps=[
{title:"Welcome to MyBeacon",text:"A quick tour will show you your Home Assistant status, backup protection, support, announcements, appearance controls, and Getting Started.",target:null},
{title:"Home Assistant status",text:"See whether your system is online and review key Home Assistant details here.",target:"instance"},
{title:"Backup protection",text:"Review managed and Home Assistant backup history and protection status.",target:"backups"},
{title:"Support and help",text:"Open support tickets, contact support, and download a diagnostic report.",target:"support"},
{title:"Announcements",text:"What’s New contains service announcements and offers intended for your account.",target:"campaigns"},
{title:"Account and appearance",text:"Use Account to change your password or choose System, Light, or Dark appearance.",target:"account"},
{title:"Getting Started",text:"Return to Getting Started for setup guidance, terminology, your checklist, or to replay this tour.",target:"getting-started"},
{title:"You are ready",text:"Your portal is ready. Promotions resume under their normal eligibility rules after you finish or skip.",target:null}
];
const modal=document.getElementById("onboarding-modal");if(!modal){window.dispatchEvent(new CustomEvent("onboarding:ready",{detail:{active:false}}));return}
const panel=modal.querySelector("[role=document]"),title=document.getElementById("onboarding-title"),text=document.getElementById("onboarding-text"),progress=document.getElementById("onboarding-progress"),back=document.getElementById("onboarding-back"),next=document.getElementById("onboarding-next"),skip=document.getElementById("onboarding-skip");let current=0,active=false,previousFocus=null,target=null;
async function api(path,method="POST",body){const r=await fetch("/api/portal/onboarding"+path,{method,credentials:"include",headers:body?{"Content-Type":"application/json"}:{},body:body?JSON.stringify(body):undefined});if(!r.ok)throw new Error("Onboarding request failed");return r.json()}
function focusables(){return [...panel.querySelectorAll("button:not([disabled]),a[href]")].filter(x=>x.offsetParent!==null)}
function clearTarget(){if(target)target.classList.remove("onboarding-spotlight");target=null}
function render(){clearTarget();const step=steps[current];target=step.target?document.querySelector(`[data-onboarding-target="${step.target}"]`):null;if(target){target.classList.add("onboarding-spotlight");target.scrollIntoView({behavior:matchMedia("(prefers-reduced-motion: reduce)").matches?"auto":"smooth",block:"center"})}title.textContent=step.title;text.textContent=step.text+(step.target&&!target?" This item is not available in the current layout; you can continue safely.":"");progress.textContent=`Step ${current+1} of ${steps.length}`;back.disabled=current===0;next.textContent=current===steps.length-1?"Finish":"Next";panel.focus()}
async function end(action){await api("/"+action);active=false;clearTarget();modal.classList.add("hidden");document.body.classList.remove("onboarding-active");if(previousFocus)previousFocus.focus();window.dispatchEvent(new CustomEvent("onboarding:ready",{detail:{active:false}}))}
async function start(state){active=true;window.dispatchEvent(new CustomEvent("onboarding:ready",{detail:{active:true}}));current=Math.min(steps.length-1,state.current_step||0);previousFocus=document.activeElement;modal.classList.remove("hidden");document.body.classList.add("onboarding-active");if(state.status==="not_started")await api("/start");render()}
back.addEventListener("click",async()=>{if(current){current--;await api("/step","PATCH",{current_step:current});render()}});next.addEventListener("click",async()=>{if(current===steps.length-1){await end("complete");return}current++;await api("/step","PATCH",{current_step:current});render()});skip.addEventListener("click",()=>end("skip"));
modal.addEventListener("keydown",e=>{if(e.key==="Escape"){e.preventDefault();skip.focus();return}if(e.key!=="Tab")return;const n=focusables();if(!n.length)return;const f=n[0],l=n[n.length-1];if(e.shiftKey&&document.activeElement===f){e.preventDefault();l.focus()}else if(!e.shiftKey&&document.activeElement===l){e.preventDefault();f.focus()}});
window.MyBeaconOnboarding={replay:async()=>start(await api("/replay"))};
window.addEventListener("load",async()=>{try{const r=await fetch("/api/portal/onboarding",{credentials:"include"});if(!r.ok)throw 0;const state=await r.json();if(state.should_start)await start(state);else window.dispatchEvent(new CustomEvent("onboarding:ready",{detail:{active:false}}))}catch(_){window.dispatchEvent(new CustomEvent("onboarding:ready",{detail:{active:true}}))}},{once:true});
})();
