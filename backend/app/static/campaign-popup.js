(function(){
"use strict";
var modal=document.getElementById("login-promotion-modal");
if(!modal)return;
var panel=modal.querySelector("[role=document]"),title=document.getElementById("login-promotion-title"),summary=document.getElementById("login-promotion-summary"),image=document.getElementById("login-promotion-image"),primary=document.getElementById("login-promotion-primary"),details=document.getElementById("login-promotion-details"),closeButtons=modal.querySelectorAll("[data-popup-close]");
var promotion=null,previousFocus=null;
function endpoint(name){return "/api/portal/promotions/"+promotion.id+"/"+name}
async function post(name){try{await fetch(endpoint(name),{method:"POST",credentials:"include"})}catch(_error){}}
function hide(){modal.classList.add("hidden");document.body.style.overflow="";if(previousFocus)previousFocus.focus()}
async function dismiss(){if(promotion)await post("dismiss");hide()}
function focusable(){return Array.from(panel.querySelectorAll('button:not([disabled]),a[href]')).filter(function(node){return node.offsetParent!==null})}
function keydown(event){
  if(event.key==="Escape"){event.preventDefault();dismiss();return}
  if(event.key!=="Tab")return;
  var nodes=focusable();if(!nodes.length)return;
  var first=nodes[0],last=nodes[nodes.length-1];
  if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus()}
  else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus()}
}
async function show(){
  var response=await fetch("/api/portal/promotions/login-popup",{credentials:"include"});
  if(!response.ok)return;
  var data=await response.json();if(!data.promotion)return;
  promotion=data.promotion;title.textContent=promotion.title;summary.textContent=promotion.summary||"";
  if(promotion.image_url){image.src=promotion.image_url;image.alt="";image.classList.remove("hidden")}else{image.removeAttribute("src");image.classList.add("hidden")}
  if(promotion.call_to_action_label&&promotion.call_to_action_url){primary.textContent=promotion.call_to_action_label;primary.classList.remove("hidden")}else{primary.classList.add("hidden")}
  previousFocus=document.activeElement;modal.classList.remove("hidden");document.body.style.overflow="hidden";panel.focus();await post("displayed")
}
closeButtons.forEach(function(button){button.addEventListener("click",dismiss)});
details.addEventListener("click",async function(){await post("opened");window.location.assign(promotion.details_url)});
primary.addEventListener("click",async function(){await post("action-clicked");window.location.assign(promotion.call_to_action_url)});
modal.addEventListener("click",function(event){if(event.target===modal)dismiss()});
modal.addEventListener("keydown",keydown);
window.addEventListener("load",function(){window.addEventListener("onboarding:ready",function(event){if(!event.detail.active)show().catch(function(){})},{once:true})},{once:true});
})();
