'use strict';

const cfuState={ready:false,opening:false,profiles:[],current:null,dirty:false,result:null,revision:0,calculating:false,libraryBusy:false,storageError:null};
function cfuStatus(message){$('cfuStatus').textContent=message;}
function cfuError(message){$('cfuError').textContent=message||'';$('cfuError').hidden=!message;}
function cfuCalibration(){
  return {name:$('cfuName').value,species:$('cfuSpecies').value,coefficient:$('cfuCoefficient').value,
    od_min:$('cfuOdMin').value,od_max:$('cfuOdMax').value,notes:$('cfuNotes').value};
}
function cfuRequest(){return {direction:$('cfuDirection').value,value:$('cfuValue').value,dilution:$('cfuDilution').value,calibration:cfuCalibration()};}
function cfuControls(){
  const blocked=!!cfuState.storageError||!cfuState.ready||cfuState.libraryBusy;
  ['cfuName','cfuSpecies','cfuCoefficient','cfuOdMin','cfuOdMax','cfuNotes','cfuDirection','cfuValue','cfuDilution','cfuNew','cfuProfiles'].forEach(id=>{$(id).disabled=!cfuState.ready;});
  $('cfuSaveAs').disabled=blocked;$('cfuUpdate').disabled=blocked||!cfuState.current;
  $('cfuDelete').disabled=$('cfuLoad').disabled=blocked||!$('cfuProfiles').value;
  $('cfuCalculate').disabled=!cfuState.ready||cfuState.calculating;
}
function cfuCurrentLabel(){
  const label=cfuState.current?`当前方案：${cfuState.current.name}${cfuState.dirty?'（有未保存更改）':''}`:'当前方案：未保存';
  $('cfuCurrent').textContent=label;$('cfuCurrent').title=label;
}
function cfuProfiles(items,selected=null){
  cfuState.profiles=clone(items);
  $('cfuProfiles').replaceChildren(...items.map(item=>{const option=document.createElement('option');option.value=item.id;option.textContent=item.name;return option;}));
  if(items.length)$('cfuProfiles').value=items.some(item=>item.id===selected)?selected:items[0].id;
  else{const option=document.createElement('option');option.value='';option.textContent='暂无已保存方案';$('cfuProfiles').append(option);}
  $('cfuProfileCount').textContent=`${items.length} 个方案`;cfuCurrentLabel();cfuControls();
}
function cfuDirectionLabels(){
  const forward=$('cfuDirection').value==='od_to_cfu';
  $('cfuValueLabel').textContent=forward?'实测 OD600（已扣空白）':'原液 CFU/mL';
  $('cfuValueHint').textContent=forward?'填写 OD600 的实际读数，不自动使用配液页面中的 OD。':'填写原液的 CFU/mL；换算结果为该系数下的等效 OD600。';
  $('cfuMetricLabel').textContent=forward?'估算原液 CFU/mL':'原液等效 OD600';
  $('cfuMeasuredLabel').textContent=forward?'实测 OD600':'预计实测 OD600';
  $('cfuSecondaryLabel').textContent=forward?'原液等效 OD600':'输入原液 CFU/mL';
  $('cfuFormula').textContent=forward?'估算原液 CFU/mL = k × 实测 OD600 × 测前稀释倍数':'原液等效 OD600 = CFU/mL ÷ k；预计实测 OD600 再除以测前稀释倍数。';
}
function cfuInvalidate(message='输入已修改，请重新换算。'){
  const stale=!!cfuState.result||$('cfuResultBadge').textContent==='需重新换算';
  cfuState.result=null;cfuState.revision++;
  $('cfuCopy').disabled=$('cfuExport').disabled=true;
  ['cfuMetricValue','cfuMeasuredValue','cfuSecondaryValue'].forEach(id=>{$(id).textContent='—';});
  $('cfuResultRows').replaceChildren();$('cfuResultHeaders').replaceChildren();
  $('cfuRecord').hidden=true;$('cfuRecord').open=false;
  $('cfuWarnings').replaceChildren();$('cfuWarnings').hidden=true;$('cfuEmpty').hidden=false;
  $('cfuEmpty').textContent=stale?'输入已更改，请重新换算。':'先填写或调用左侧校准系数，再填写本次读数并换算。';
  $('cfuResultBadge').textContent=stale?'需重新换算':'待换算';$('cfuResultBadge').className='badge';
  cfuDirectionLabels();cfuError(null);cfuStatus(message);
}
function cfuApplyProfile(profile,clearValue=false){
  const data=profile||{};
  cfuState.current=profile?.id?clone(profile):null;cfuState.dirty=false;
  const fields={cfuName:'name',cfuSpecies:'species',cfuCoefficient:'coefficient',cfuOdMin:'od_min',cfuOdMax:'od_max',cfuNotes:'notes'};
  Object.entries(fields).forEach(([id,key])=>{$(id).value=numberText(data[key]);});
  if(clearValue){$('cfuValue').value='';$('cfuDilution').value='1';}
  cfuCurrentLabel();cfuInvalidate(profile?'已调用校准方案，请核对本次输入后换算。':'已新建空白方案，请填写校准系数。');cfuControls();
}
async function cfuOpen(){
  if(!$('cfuDialog').open)$('cfuDialog').showModal();
  if(cfuState.ready||cfuState.opening)return;
  cfuState.opening=true;cfuControls();cfuStatus('正在读取本地校准系数…');
  try{
    const data=await call('cfu_bootstrap');cfuState.storageError=data.storage_error||null;
    $('cfuStorageNotice').textContent=cfuState.storageError||'';$('cfuStorageNotice').hidden=!cfuState.storageError;
    cfuState.ready=true;cfuProfiles(data.profiles||[]);
    cfuApplyProfile(cfuState.profiles[0]||null,true);
    if(cfuState.storageError)cfuStatus('校准库读取失败；仍可手动填写系数换算，原文件已保留。');
  }catch(error){cfuError(`校准界面初始化失败：${error.message}`);cfuStatus('请关闭后重新打开换算功能。');}
  finally{cfuState.opening=false;cfuControls();}
}
async function cfuConvert(){
  if(!cfuState.ready||cfuState.calculating)return;
  cfuState.calculating=true;const revision=cfuState.revision,data=cfuRequest();cfuControls();cfuError(null);
  try{
    const result=await call('cfu_convert',data);if(cfuState.revision!==revision)return;
    const forward=result.direction==='od_to_cfu';
    cfuState.result=result;cfuDirectionLabels();
    $('cfuMetricValue').textContent=forward?result.display.cfu_ml:result.display.stock_od;
    $('cfuMeasuredValue').textContent=result.display.measured_od;
    $('cfuSecondaryValue').textContent=forward?result.display.stock_od:result.display.cfu_ml;
    $('cfuEmpty').hidden=true;$('cfuResultBadge').textContent='模型估算';$('cfuResultBadge').className='badge ready';
    $('cfuWarnings').replaceChildren(...result.warnings.map(message=>{const p=document.createElement('p');p.textContent=message;return p;}));
    $('cfuWarnings').hidden=!result.warnings.length;
    $('cfuResultHeaders').replaceChildren(...result.headers.map(value=>{const th=document.createElement('th');th.scope='col';th.textContent=value;return th;}));
    $('cfuResultRows').replaceChildren(...result.rows.map(row=>{const tr=document.createElement('tr');row.forEach(value=>{const td=document.createElement('td');td.textContent=value;tr.append(td);});return tr;}));
    $('cfuRecord').hidden=false;$('cfuCopy').disabled=$('cfuExport').disabled=false;
    cfuStatus('换算完成。复制和导出包含校准系数、稀释倍数及范围提示。');
  }catch(error){if(cfuState.revision!==revision)return;cfuInvalidate('换算未完成，请按提示修改输入。');cfuError(error.message);$('cfuResultBadge').textContent='检查输入';$('cfuResultBadge').className='badge error';}
  finally{cfuState.calculating=false;cfuControls();}
}
async function cfuLoadProfile(){
  const id=$('cfuProfiles').value;if(!id||cfuState.libraryBusy)return;
  const revision=cfuState.revision;cfuState.libraryBusy=true;cfuControls();
  try{const data=await call('cfu_load_profile',id);cfuProfiles(data.profiles,id);if(revision===cfuState.revision)cfuApplyProfile(data.profile);}
  catch(error){cfuError(error.message);}finally{cfuState.libraryBusy=false;cfuControls();}
}
async function cfuSaveProfile(update=false){
  if(!cfuState.ready||cfuState.storageError||cfuState.libraryBusy)return;
  const id=update?cfuState.current?.id:null;if(update&&!id)return;
  const revision=cfuState.revision,data=cfuCalibration();cfuState.libraryBusy=true;cfuControls();cfuError(null);
  try{
    const saved=await call('cfu_save_profile',data,id);cfuProfiles(saved.profiles,saved.profile.id);
    if(revision===cfuState.revision){cfuApplyProfile(saved.profile);cfuStatus('校准系数已保存在本机，本次读数未保存。');}
    else{cfuState.current=clone(saved.profile);cfuState.dirty=true;cfuCurrentLabel();cfuStatus('校准系数已保存；之后的输入更改尚未保存。');}
  }catch(error){cfuError(error.message);cfuStatus('保存未完成，已有方案和当前输入保留。');}
  finally{cfuState.libraryBusy=false;cfuControls();}
}
async function cfuDeleteProfile(){
  const id=$('cfuProfiles').value,profile=cfuState.profiles.find(item=>item.id===id);
  if(!profile||cfuState.libraryBusy||cfuState.storageError)return;
  const confirmed=await modal('删除校准方案',`删除“${profile.name}”？当前填写的校准系数会保留。`,{confirm:'删除'});
  if(!confirmed)return;
  cfuState.libraryBusy=true;cfuControls();
  try{
    const data=await call('cfu_delete_profile',id);
    if(cfuState.current?.id===id){cfuState.current=null;cfuState.dirty=false;}
    cfuProfiles(data.profiles);cfuInvalidate('校准方案已删除，当前填写的系数保留。');
  }catch(error){cfuError(error.message);}finally{cfuState.libraryBusy=false;cfuControls();}
}
async function cfuUseResult(method){
  if(!cfuState.result)return;
  try{const message=await call(method,cfuState.result.id,cfuRequest());if(message)cfuStatus(message);}
  catch(error){cfuError(error.message);}
}
$('openCFU').addEventListener('click',cfuOpen);$('cfuClose').addEventListener('click',()=>$('cfuDialog').close());
$('cfuNew').addEventListener('click',()=>cfuApplyProfile(null,true));
$('cfuLoad').addEventListener('click',cfuLoadProfile);$('cfuProfiles').addEventListener('change',cfuControls);
$('cfuProfiles').addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.ctrlKey&&!event.altKey&&!event.metaKey){event.preventDefault();cfuLoadProfile();}});
['cfuName','cfuSpecies','cfuCoefficient','cfuOdMin','cfuOdMax','cfuNotes'].forEach(id=>$(id).addEventListener('input',()=>{cfuState.dirty=true;cfuCurrentLabel();cfuInvalidate();}));
['cfuValue','cfuDilution'].forEach(id=>$(id).addEventListener('input',()=>cfuInvalidate()));
$('cfuDirection').addEventListener('change',()=>{cfuInvalidate('换算方向已改变，请填写对应的本次读数。');$('cfuValue').value='';});
$('cfuSaveAs').addEventListener('click',()=>cfuSaveProfile(false));$('cfuUpdate').addEventListener('click',()=>cfuSaveProfile(true));$('cfuDelete').addEventListener('click',cfuDeleteProfile);
$('cfuCalculate').addEventListener('click',cfuConvert);$('cfuCopy').addEventListener('click',()=>cfuUseResult('cfu_copy_result'));$('cfuExport').addEventListener('click',()=>cfuUseResult('cfu_export_result'));
document.addEventListener('keydown',event=>{
  if(!$('cfuDialog').open||$('modal').open)return;
  if(event.ctrlKey&&event.key==='Enter'){event.preventDefault();cfuConvert();}
  if(event.ctrlKey&&event.key.toLowerCase()==='s'){event.preventDefault();cfuSaveProfile(!!cfuState.current);}
});
cfuDirectionLabels();cfuControls();
