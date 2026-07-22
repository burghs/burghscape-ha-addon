(function(){
"use strict";
var POLL_MS=120000,modal=document.getElementById("login-promotion-modal");
if(!modal)return;
var panel=modal.querySelector("[role=document]"),title=document.getElementById("login-promotion-title"),summary=document.getElementById("login-promotion-summary"),image=document.getElementById("login-promotion-image"),primary=document.getElementById("login-promotion-primary"),details=document.getElementById("login-promotion-details"),closeButtons=modal.querySelectorAll("[data-popup-close]");
var promotion=null,previousFocus=null,checking=false,visible=false,onboardingActive=true;
function endpoint(name){return "/api/portal/promotions/"+promotion.id+"/"+name}
async function post(name){try{await fetch(endpoint(name),{method:"POST",credentials:"include"})}catch(_error){}}
function hide(){modal.classList.add("hidden");document.body.classList.remove("campaign-popup-open");visible=false;promotion=null;if(previousFocus)previousFocus.focus()}
async function dismiss(){if(promotion)await post("dismiss");hide()}
function focusable(){return Array.from(panel.querySelectorAll("button:not([disabled]),a[href]")).filter(function(node){return node.offsetParent!==null})}
function keydown(event){
 if(event.key==="Escape"){event.preventDefault();dismiss();return}
 if(event.key!=="Tab")return;
 var nodes=focusable();if(!nodes.length)return;
 var first=nodes[0],last=nodes[nodes.length-1];
 if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus()}
 else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus()}
}
async function check(){
 if(checking||visible||onboardingActive||document.hidden)return;
 checking=true;
 try{
  var response=await fetch("/api/portal/promotions/login-popup",{credentials:"include",cache:"no-store"});
  if(!response.ok)return;
  var data=await response.json();if(data.suppressed_by_onboarding){onboardingActive=true;return}if(!data.promotion)return;
  promotion=data.promotion;title.textContent=promotion.title;summary.textContent=promotion.summary||"";
  if(promotion.image_url){image.src=promotion.image_url;image.alt="";image.classList.remove("hidden")}else{image.removeAttribute("src");image.classList.add("hidden")}
  if(promotion.call_to_action_label&&promotion.call_to_action_url){primary.textContent=promotion.call_to_action_label;primary.classList.remove("hidden")}else{primary.classList.add("hidden")}
  previousFocus=document.activeElement;visible=true;modal.classList.remove("hidden");document.body.classList.add("campaign-popup-open");panel.focus();await post("displayed")
 }finally{checking=false}
}
closeButtons.forEach(function(button){button.addEventListener("click",dismiss)});
details.addEventListener("click",async function(){await post("opened");window.location.assign(promotion.details_url)});
primary.addEventListener("click",async function(){await post("action-clicked");window.location.assign(promotion.call_to_action_url)});
modal.addEventListener("click",function(event){if(event.target===modal)dismiss()});
modal.addEventListener("keydown",keydown);
window.addEventListener("onboarding:ready",function(event){onboardingActive=!!event.detail.active;if(!onboardingActive)check().catch(function(){})});
window.addEventListener("load",function(){setInterval(function(){check().catch(function(){})},POLL_MS)},{once:true});
document.addEventListener("visibilitychange",function(){if(!document.hidden)check().catch(function(){})});
})();
