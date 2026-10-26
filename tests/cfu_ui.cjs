const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');

// These coefficients and readings are synthetic software fixtures, not bacterial reference data.
const profile={id:'calibration-a',name:'合成测试方案',species:'软件测试',coefficient:2e8,od_min:0.1,od_max:0.5,notes:'仅软件测试'};
const result={id:'result-a',direction:'od_to_cfu',display:{cfu_ml:'5e8',measured_od:'0.25',stock_od:'2.5'},warnings:['未填写校准适用范围'],headers:['项目','数值'],rows:[['估算原液 CFU/mL','5e8'],['测前稀释倍数','10']]};

function fixture({profiles=[],storageError=null}={}){
  const nodes=new Map(),documentHandlers=new Map(),calls=[];
  class Node {
    constructor(){this.value='';this.textContent='';this.hidden=false;this.disabled=false;this.open=false;this.children=[];this.handlers=new Map();}
    addEventListener(type,handler){if(!this.handlers.has(type))this.handlers.set(type,[]);this.handlers.get(type).push(handler);}
    replaceChildren(...children){this.children=children;}
    append(...children){this.children.push(...children);}
    showModal(){this.open=true;}
    close(){this.open=false;}
    focus(){} select(){} setAttribute(){}
  }
  function element(id){if(!nodes.has(id))nodes.set(id,new Node());return nodes.get(id);}
  const document={getElementById:element,querySelectorAll:()=>[],createElement:()=>new Node(),addEventListener(type,handler){if(!documentHandlers.has(type))documentHandlers.set(type,[]);documentHandlers.get(type).push(handler);}};
  const window={addEventListener(){}};
  const context=vm.createContext({document,window,console});
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../glass_ui/app.js'),'utf8'),context);
  element('cfuDirection').value='od_to_cfu';element('cfuDilution').value='1';
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../glass_ui/cfu.js'),'utf8'),context);
  const handlers={cfu_bootstrap:async()=>({profiles,storage_error:storageError}),cfu_convert:async()=>structuredClone(result),
    cfu_load_profile:async id=>({profile:profiles.find(p=>p.id===id),profiles}),cfu_save_profile:async(data,id)=>({profile:{...data,id:id||'saved-profile'},profiles:[{...data,id:id||'saved-profile'}]})};
  window.pywebview={api:new Proxy({}, {get(_target,name){return async(...args)=>{calls.push({name,args});try{return {ok:true,data:await handlers[name](...args)};}catch(error){return {ok:false,error:error.message};}};}})};
  const run=code=>vm.runInContext(code,context);
  const fire=(id,type,event={})=>(element(id).handlers.get(type)||[]).forEach(handler=>handler(event));
  const key=async(key,targetId=null,modifiers={})=>{const event={ctrlKey:true,key,preventDefault(){},...modifiers};if(targetId)fire(targetId,'keydown',event);(documentHandlers.get('keydown')||[]).forEach(handler=>handler(event));await new Promise(resolve=>setImmediate(resolve));};
  function fill(){element('cfuName').value='合成测试方案';element('cfuCoefficient').value='2e8';element('cfuValue').value='0.25';element('cfuDilution').value='10';}
  return {run,element,fire,key,fill,calls,handlers};
}

test('An empty library never supplies a biological conversion coefficient',async()=>{
  const f=fixture();await f.run('cfuOpen()');
  assert.equal(f.element('cfuDialog').open,true);
  assert.equal(f.element('cfuCoefficient').value,'');
  assert.equal(f.element('cfuDilution').value,'1');
  assert.equal(f.element('cfuCopy').disabled,true);
  assert.deepEqual(f.calls.map(c=>c.name),['cfu_bootstrap']);
});

test('Editing a coefficient invalidates CFU output while preserving the mixing result',async()=>{
  const f=fixture();await f.run('cfuOpen()');f.fill();
  f.run("state.result={id:'mix-kept'}");await f.run('cfuConvert()');
  assert.equal(f.element('cfuMetricValue').textContent,'5e8');
  assert.equal(f.element('cfuWarnings').children[0].textContent,'未填写校准适用范围');
  assert.equal(f.element('cfuCopy').disabled,false);
  f.element('cfuCoefficient').value='3e8';f.fire('cfuCoefficient','input');
  assert.equal(f.run('cfuState.result'),null);
  assert.equal(f.element('cfuCopy').disabled,true);assert.equal(f.element('cfuExport').disabled,true);
  assert.equal(f.element('cfuMetricValue').textContent,'—');assert.equal(f.run('state.result.id'),'mix-kept');
});

test('A response from before an input edit cannot resurrect the old result',async()=>{
  const f=fixture();await f.run('cfuOpen()');f.fill();let finish;
  f.handlers.cfu_convert=()=>new Promise(resolve=>{finish=resolve;});
  const pending=f.run('cfuConvert()');f.element('cfuValue').value='0.5';f.fire('cfuValue','input');
  finish(structuredClone(result));await pending;
  assert.equal(f.run('cfuState.result'),null);assert.equal(f.element('cfuExport').disabled,true);
});

test('CFU shortcuts never calculate or save a mixing recipe, and nested confirmation blocks them',async()=>{
  const f=fixture();await f.run('cfuOpen()');f.fill();
  f.run('globalThis.mixCalculations=0;globalThis.mixSaves=0;calculate=()=>mixCalculations++;saveTemplate=()=>mixSaves++;state.ready=true;');
  await f.key('Enter');assert.equal(f.calls.filter(c=>c.name==='cfu_convert').length,1);
  await f.key('s');assert.equal(f.calls.filter(c=>c.name==='cfu_save_profile').length,1);
  assert.equal(f.run('mixCalculations'),0);assert.equal(f.run('mixSaves'),0);
  f.element('modal').open=true;await f.key('Enter');assert.equal(f.calls.filter(c=>c.name==='cfu_convert').length,1);
  f.element('modal').open=false;f.element('cfuDialog').open=false;await f.key('Enter');await f.key('s');
  assert.equal(f.run('mixCalculations'),1);assert.equal(f.run('mixSaves'),1);
});

test('Loading another calibration clears only CFU results and retains the current reading for review',async()=>{
  const second={...profile,id:'calibration-b',name:'另一个合成测试',coefficient:4e8};
  const f=fixture({profiles:[profile,second]});await f.run('cfuOpen()');f.fill();await f.run('cfuConvert()');
  f.run("state.result={id:'mix-kept'}");f.element('cfuProfiles').value=second.id;await f.run('cfuLoadProfile()');
  assert.equal(f.element('cfuCoefficient').value,'400000000');assert.equal(f.element('cfuValue').value,'0.25');
  assert.equal(f.run('cfuState.result'),null);assert.equal(f.element('cfuCopy').disabled,true);assert.equal(f.run('state.result.id'),'mix-kept');
});

test('Enter on the profile selector loads a profile, but Ctrl+Enter only converts',async()=>{
  const f=fixture({profiles:[profile]});await f.run('cfuOpen()');f.fill();
  await f.key('Enter','cfuProfiles');
  assert.equal(f.calls.filter(c=>c.name==='cfu_load_profile').length,0);
  assert.equal(f.calls.filter(c=>c.name==='cfu_convert').length,1);
  await f.key('Enter','cfuProfiles',{ctrlKey:false});
  assert.equal(f.calls.filter(c=>c.name==='cfu_load_profile').length,1);
  assert.equal(f.calls.filter(c=>c.name==='cfu_convert').length,1);
  await f.key('Enter','cfuProfiles',{ctrlKey:false,altKey:true});
  await f.key('Enter','cfuProfiles',{ctrlKey:false,metaKey:true});
  assert.equal(f.calls.filter(c=>c.name==='cfu_load_profile').length,1);
});

test('A corrupted library disables writes but still allows a manually supplied coefficient',async()=>{
  const f=fixture({storageError:'校准文件损坏，原文件已保留'});await f.run('cfuOpen()');f.fill();
  assert.equal(f.element('cfuSaveAs').disabled,true);assert.equal(f.element('cfuCoefficient').disabled,false);
  await f.run('cfuSaveProfile(false)');assert.equal(f.calls.filter(c=>c.name==='cfu_save_profile').length,0);
  await f.run('cfuConvert()');assert.equal(f.element('cfuMetricValue').textContent,'5e8');
});

test('Failed saves keep the stored selection and edited coefficient',async()=>{
  const f=fixture({profiles:[profile]});await f.run('cfuOpen()');
  f.element('cfuCoefficient').value='9e8';f.fire('cfuCoefficient','input');
  f.handlers.cfu_save_profile=async()=>{throw new Error('保存失败，原文件已保留');};await f.run('cfuSaveProfile(true)');
  assert.equal(f.element('cfuCoefficient').value,'9e8');assert.equal(f.run('cfuState.current.id'),profile.id);
  assert.equal(f.run('cfuState.profiles[0].coefficient'),2e8);assert.match(f.element('cfuError').textContent,/保存失败/);
});

test('Closing and reopening preserves the local draft without loading OD from a profile',async()=>{
  const f=fixture();await f.run('cfuOpen()');f.fill();f.element('cfuDialog').close();await f.run('cfuOpen()');
  assert.equal(f.element('cfuValue').value,'0.25');assert.equal(f.element('cfuCoefficient').value,'2e8');
  assert.equal(f.calls.filter(c=>c.name==='cfu_bootstrap').length,1);
});
