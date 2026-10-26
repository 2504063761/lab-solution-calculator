'use strict';
const $ = id => document.getElementById(id);
const state = {recipe:null,current:null,templates:[],result:null,revision:0,empty:null,ready:false,storageError:null,calculating:false};
const clone = value => JSON.parse(JSON.stringify(value));
const numberText = value => value == null ? '' : String(value);
function status(message){$('status').textContent=message;}
function notice(message){$('notice').textContent=message||'';$('notice').hidden=!message;}
async function call(method,...args){
  const reply=await window.pywebview.api[method](...args);
  if(!reply.ok)throw new Error(reply.error||'操作未完成，请重试。');
  return reply.data;
}
function recipe(){
  return {cultures:state.recipe.cultures.map(row=>({...row})),target_od:$('targetOD').value,volume:$('volume').value,
    unit:$('unit').value,mode:document.querySelector('input[name=mode]:checked').value};
}
function headers(){
  const separate=document.querySelector('input[name=mode]:checked').value==='separate';
  const names=['菌种 / 样品','原液 OD','比例','取原液 (µL)','补液 (µL)',separate?'配成 (µL)':'入管 (µL)',separate?'调整后 OD':'OD 贡献'];
  $('resultHeaders').replaceChildren(...names.map(name=>{const th=document.createElement('th');th.scope='col';th.textContent=name;return th;}));
  $('modeHint').textContent=separate?'每种菌分别配成等体积，再将所有调整液全部合并。':'各菌原液取入同一管，再统一补液至最终体积。';
}
function invalidate(){
  const stale=state.result!==null||$('resultBadge').textContent==='需重新计算';
  state.result=null;state.revision++;$('resultRows').replaceChildren();$('copyResult').disabled=$('exportCSV').disabled=true;
  $('emptyResult').hidden=false;$('emptyResult').querySelector('strong').textContent=stale?'输入已更改，请重新计算':'等待本次配液数据';
  $('resultBadge').textContent=stale?'需重新计算':'待计算';$('resultBadge').className='badge';
  $('summary').textContent='体积统一以 µL 显示，保留三位小数。比例表示 OD 贡献，不换算活菌数量。';
  status('输入已修改，等待重新计算。');headers();notice(state.storageError);
}
function renderRows(){
  const keys=['name','od','dilution','ratio'];
  $('cultures').replaceChildren(...state.recipe.cultures.map((row,index)=>{
    const line=document.createElement('div');line.className='culture-columns culture-row';
    keys.forEach((key,column)=>{const input=document.createElement('input');input.value=numberText(row[key]);input.autocomplete='off';
      input.setAttribute('aria-label',`第${index+1}行 ${['菌种名称','测得初始 OD','测定稀释倍数','OD 贡献比例'][column]}`);
      if(key!=='name')input.inputMode='decimal';
      input.addEventListener('input',()=>{row[key]=input.value;invalidate();});
      input.addEventListener('focus',()=>line.scrollIntoView({block:'nearest',behavior:'instant'}));line.append(input);
    });
    const remove=document.createElement('button');remove.type='button';remove.textContent='×';remove.className='remove';
    remove.setAttribute('aria-label',`删除第${index+1}行菌种`);remove.disabled=state.recipe.cultures.length===1;
    remove.addEventListener('click',()=>{state.recipe.cultures.splice(index,1);renderRows();invalidate();});line.append(remove);return line;
  }));
  $('cultureCount').value=state.recipe.cultures.length;
}
function currentLabel(){
  $('currentTemplate').textContent=state.current?`当前配方：${state.current.name}`:'当前配方：未保存';
  $('currentTemplate').title=$('currentTemplate').textContent;$('updateTemplate').disabled=!state.current||!!state.storageError;
}
function templates(items,selected){
  state.templates=items;
  $('templateList').replaceChildren(...items.map(item=>{const option=document.createElement('option');option.value=item.id;option.textContent=item.name;return option;}));
  if(items.length)$('templateList').value=items.some(item=>item.id===selected)?selected:items[0].id;
  $('templateCount').textContent=`${items.length} 个模板`;
  ['loadTemplate','renameTemplate','deleteTemplate'].forEach(id=>{$(id).disabled=!items.length||!!state.storageError;});
  $('saveAs').disabled=!!state.storageError;currentLabel();
}
function applyRecipe(data,current=null){
  state.recipe=clone(data);state.current=current?clone(current):null;
  $('targetOD').value=numberText(data.target_od);$('volume').value=numberText(data.volume);$('unit').value=data.unit;
  document.querySelector(`input[name=mode][value="${data.mode}"]`).checked=true;
  $('templateName').value=current?current.name:'';$('includeOD').checked=current?current.include_od:false;
  renderRows();$('cultures').scrollTop=0;currentLabel();invalidate();
}
function addRows(count){
  while(state.recipe.cultures.length<count){let n=state.recipe.cultures.length+1;
    const names=new Set(state.recipe.cultures.map(r=>r.name.trim().toLocaleLowerCase()));
    while(names.has(`菌种${n}`.toLocaleLowerCase()))n++;
    state.recipe.cultures.push({name:`菌种${n}`,od:'',dilution:1,ratio:1});
  }
  state.recipe.cultures.length=count;renderRows();invalidate();
}
function applyCount(){
  const raw=$('cultureCount').value.trim(),count=Number(raw);
  if(!/^\d+$/.test(raw)||!Number.isSafeInteger(count)||count<=0){notice('菌种数量必须是正整数。');$('cultureCount').value=state.recipe.cultures.length;return;}
  addRows(count);
}
async function calculate(){
  if(!state.ready||state.calculating)return;
  state.calculating=true;const revision=state.revision;const data=recipe();$('calculate').disabled=true;notice(null);
  try{
    const result=await call('calculate',data);if(state.revision!==revision)return;
    state.result=result;$('resultHeaders').replaceChildren(...result.headers.map(value=>{const th=document.createElement('th');th.scope='col';th.textContent=value;return th;}));
    $('resultRows').replaceChildren(...result.rows.map(row=>{const tr=document.createElement('tr');row.forEach(value=>{const td=document.createElement('td');td.textContent=value;tr.append(td);});return tr;}));
    $('emptyResult').hidden=true;$('copyResult').disabled=$('exportCSV').disabled=false;$('resultBadge').textContent='已计算';$('resultBadge').className='badge ready';
    $('summary').textContent=`最终体积 ${result.total_display} µL · 理论总 OD ${result.od_display} · 按所选流程配液`;status('计算完成。可复制配液表或导出 CSV。');
  }catch(error){if(state.revision!==revision)return;state.result=null;$('resultRows').replaceChildren();$('copyResult').disabled=$('exportCSV').disabled=true;
    $('resultBadge').textContent='检查输入';$('resultBadge').className='badge error';$('emptyResult').hidden=false;
    $('emptyResult').querySelector('strong').textContent='请检查本次输入';notice(error.message);status('计算未完成，请按提示修改输入。');
  }finally{state.calculating=false;$('calculate').disabled=false;}
}
async function loadTemplate(){
  const id=$('templateList').value;if(!id)return;
  try{const data=await call('load_template',id);templates(data.templates,id);applyRecipe(data.current.recipe,data.current);status('已调用模板，请核对本次 OD 后计算。');}catch(error){notice(error.message);}
}
async function saveTemplate(update){
  try{const data=await call('save_template',$('templateName').value,recipe(),$('includeOD').checked,update?state.current?.id:null);
    state.current=data.current;templates(data.templates,data.current.id);$('templateName').value=data.current.name;status('模板已保存在本机。');notice(null);
  }catch(error){notice(error.message);}
}
function modal(title,body,{input=null,confirm='确认',cancel=true}={}){
  $('modal').returnValue='';
  $('modalTitle').textContent=title;$('modalBody').textContent=body;$('modalInputLabel').hidden=input===null;
  $('modalInput').value=input||'';$('modalOK').textContent=confirm;$('modalCancel').hidden=!cancel;
  return new Promise(resolve=>{$('modal').addEventListener('close',()=>resolve($('modal').returnValue==='ok'?(input===null?true:$('modalInput').value):null),{once:true});
    $('modal').showModal();if(input!==null){$('modalInput').focus();$('modalInput').select();}});
}
async function renameTemplate(){
  const id=$('templateList').value,item=state.templates.find(t=>t.id===id);if(!item)return;
  const name=await modal('重命名模板','模板名称必须唯一。',{input:item.name});if(name===null)return;
  try{const data=await call('rename_template',id,name);if(state.current?.id===id){state.current=data.current;$('templateName').value=data.current.name;}templates(data.templates,id);notice(null);status('模板已重命名。');}catch(error){notice(error.message);}
}
async function deleteTemplate(){
  const id=$('templateList').value,item=state.templates.find(t=>t.id===id);if(!item)return;
  if(!await modal('删除模板',`删除“${item.name}”？当前填写的数据和配液结果会保留。`,{confirm:'删除'}))return;
  try{const data=await call('delete_template',id);if(state.current?.id===id)state.current=null;templates(data.templates);notice(null);status('模板已删除，当前输入保留。');}catch(error){notice(error.message);}
}
async function useResult(method){if(!state.result)return;try{const message=await call(method,state.result.id,recipe());if(message)status(message);}catch(error){notice(error.message);}}
const helpText='一、填写本次数据\n初始 OD 使用同一波长且已扣除空白的读数。原液直测倍数填 1，测前稀释 10 倍填 10；若输入的是已乘倍数的原液 OD，倍数填 1，避免重复换算。比例表示 OD 贡献，不等同活菌数量比。\n\n二、选择流程\n分别稀释后混合：每种菌分别配成等体积，再将全部调整液合并。原液直接混合：把各菌原液取入同一管，统一补液。程序分别判断是否可行；零补液允许，需负补液时提示最高可实现总 OD。\n\n三、保存模板\n保存、更新、另存为、重命名和删除均在左侧操作。默认不包含初始 OD，调用后须重新填写；勾选则保存本次读数。OD、目标和体积可以留空保存模板，但计算前必须补齐。模板仍保存在 %LOCALAPPDATA%\\菌液配比计算器\\templates.json。\n\n四、使用结果\nCtrl + Enter 计算，Ctrl + S 更新当前模板，未关联模板时保存为新模板。修改输入或调用模板后结果立即失效。CSV 使用 UTF-8 BOM，可用 Excel 打开。\n\n界面在本机 WebView2 中离线运行，不加载外部字体、图片或脚本。玻璃卡片模糊的是应用内背景，不是桌面内容。系统减少透明度或不支持模糊时使用清晰的实色卡片。\n\n单菌计算模块来自 MichaelJLewis98/sub-culturing-volume-calculator，MIT 许可。';
async function initialize(){
  try{
    const data=await call('bootstrap');state.empty=data.empty_recipe;state.storageError=data.storage_error;
    const preferences=data.preferences;
    const reduced=preferences.reduce_transparency||preferences.high_contrast||matchMedia('(prefers-reduced-transparency: reduce)').matches||matchMedia('(forced-colors: active)').matches;
    const unsupported=!CSS.supports('backdrop-filter','blur(1px)');
    document.body.classList.toggle('reduce-transparency',reduced);
    document.body.classList.toggle('reduce-motion',preferences.reduce_motion);
    document.body.classList.toggle('no-blur',unsupported);
    $('version').textContent=`版本 ${data.version}`;
    $('version').title=reduced?'系统减少透明度或高对比度偏好已启用，当前使用实色外观。':unsupported?'当前环境不支持背景模糊，使用实色外观。':'本地离线运行。';
    templates(data.templates,data.current?.id);applyRecipe(data.recipe,data.current);
    state.ready=true;status('准备就绪：填写本次 OD、目标总 OD 和最终体积。');notice(state.storageError);
  }catch(error){notice(`本地界面初始化失败：${error.message}`);status('请重新启动程序。');}
}
$('applyCount').addEventListener('click',applyCount);$('cultureCount').addEventListener('keydown',event=>{if(event.key==='Enter')applyCount();});
$('addRow').addEventListener('click',()=>{addRows(state.recipe.cultures.length+1);$('cultures').lastElementChild.scrollIntoView({block:'nearest',behavior:'instant'});});
['targetOD','volume'].forEach(id=>$(id).addEventListener('input',invalidate));$('unit').addEventListener('change',invalidate);
document.querySelectorAll('input[name=mode]').forEach(input=>input.addEventListener('change',invalidate));
$('newRecipe').addEventListener('click',()=>{applyRecipe(state.empty);status('已新建空白配方。');});
$('loadTemplate').addEventListener('click',loadTemplate);$('templateList').addEventListener('dblclick',loadTemplate);
$('templateList').addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.ctrlKey&&!event.metaKey&&!event.altKey){event.preventDefault();loadTemplate();}});
$('saveAs').addEventListener('click',()=>saveTemplate(false));$('updateTemplate').addEventListener('click',()=>saveTemplate(true));
$('renameTemplate').addEventListener('click',renameTemplate);$('deleteTemplate').addEventListener('click',deleteTemplate);
$('calculate').addEventListener('click',calculate);$('copyResult').addEventListener('click',()=>useResult('copy_result'));$('exportCSV').addEventListener('click',()=>useResult('export_result'));
$('help').addEventListener('click',()=>document.body.dataset.module==='materials'?materialHelp():modal('使用说明',helpText,{confirm:'关闭',cancel:false}));
$('modalCancel').addEventListener('click',()=>$('modal').close('cancel'));
document.addEventListener('keydown',event=>{if(document.body?.dataset?.module==='materials'||$('modal').open||$('cfuDialog')?.open)return;if(event.ctrlKey&&event.key==='Enter'){event.preventDefault();calculate();}
  if(event.ctrlKey&&event.key.toLowerCase()==='s'){event.preventDefault();if(state.ready)saveTemplate(!!state.current);}});
if(window.pywebview?.api)initialize();else window.addEventListener('pywebviewready',initialize,{once:true});
