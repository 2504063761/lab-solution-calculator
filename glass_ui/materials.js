'use strict';

const materialState={recipe:null,current:null,profiles:[],result:null,revision:0,ready:false,
  initializing:false,storageError:null,calculating:false,libraryBusy:false,dirty:false};
const materialBasis={
  ww:{name:'w/w',total:'最终总质量',units:['g','mg','kg'],hint:'w/w：每 100 g 最终配方中含多少 g 组分；溶剂按剩余质量补足。'},
  wv:{name:'w/v',total:'最终总体积',units:['mL','µL','L'],hint:'w/v：每 100 mL 最终配方中含多少 g 组分；加入适量溶剂，定容至最终体积。'},
  vv:{name:'v/v',total:'最终总体积',units:['mL','µL','L'],hint:'v/v：每 100 mL 最终配方中含多少 mL 液体组分；混合后定容，补液体积不能直接相减。'},
  molar:{name:'摩尔浓度',total:'最终总体积',units:['mL','µL','L'],hint:'M = mol/L。分别填写各材料的目标浓度和摩尔质量，计算称取质量，再定容至最终体积。'}
};
function materialBlank(){return {basis:'ww',total:'',unit:'g',solvent:'',mass_unit:'mg',components:[{name:'',percent:''}]};}
function materialStatus(message){$('materialStatus').textContent=message;}
function materialNotice(message){$('materialNotice').textContent=message||'';$('materialNotice').hidden=!message;}
function materialRequest(){
  const molar=$('materialBasis').value==='molar';
  const request={basis:$('materialBasis').value,total:$('materialTotal').value,unit:$('materialUnit').value,
    solvent:$('materialSolvent').value,components:materialState.recipe.components.map(row=>molar?
      {name:row.name,concentration:numberText(row.concentration),concentration_unit:row.concentration_unit||'μM',
        molar_mass:numberText(row.molar_mass),molar_mass_unit:row.molar_mass_unit||'g/mol'}:
      {name:row.name,percent:numberText(row.percent)})};
  if(molar)request.mass_unit=$('materialMassUnit').value;
  return request;
}
function materialCurrentLabel(){
  $('materialCurrent').textContent=materialState.current?`当前配方：${materialState.current.name}${materialState.dirty?'（已修改）':''}`:'当前配方：未保存';
  $('materialCurrent').title=$('materialCurrent').textContent;
}
function materialControls(){
  const locked=!materialState.ready||materialState.libraryBusy||!!materialState.storageError;
  $('materialCalculate').disabled=!materialState.ready||materialState.calculating;
  $('materialSaveAs').disabled=locked;
  $('materialUpdate').disabled=locked||!materialState.current;
  $('materialLoad').disabled=$('materialDelete').disabled=locked||!$('materialTemplates').value;
  $('materialCopy').disabled=$('materialExport').disabled=!materialState.result;
}
function materialHeaders(){
  const molar=$('materialBasis').value==='molar';
  const names=molar?['材料 / 组分','目标浓度','摩尔质量','用量','单位','配制操作']:
    ['材料 / 组分',`目标浓度（% ${materialBasis[$('materialBasis').value].name}）`,'用量','单位','配制操作'];
  $('materialResultHeaders').replaceChildren(...names.map(value=>{const th=document.createElement('th');th.scope='col';th.textContent=value;return th;}));
}
function materialInvalidate(message='输入已修改，等待重新计算。',markDirty=true){
  const stale=materialState.result!==null||$('materialResultBadge').textContent==='需重新计算';
  materialState.result=null;materialState.revision++;
  if(markDirty)materialState.dirty=true;
  $('materialResultRows').replaceChildren();$('materialEmpty').hidden=false;
  $('materialEmpty').querySelector('strong').textContent=stale?'输入已更改，请重新计算':'等待材料配方';
  $('materialResultBadge').textContent=stale?'需重新计算':'待计算';$('materialResultBadge').className='badge';
  $('materialSummary').textContent='按纯组分计算；请按实际材料的溶解性和配制要求操作。';
  $('materialNotes').replaceChildren();$('materialNotesDetails').hidden=true;$('materialNotesDetails').open=false;
  materialHeaders();materialControls();materialCurrentLabel();materialNotice(materialState.storageError);materialStatus(message);
}
function materialBasisLabels(preferredUnit=$('materialUnit').value){
  const basis=materialBasis[$('materialBasis').value],molar=$('materialBasis').value==='molar';
  document.querySelector('.material-worksheet').classList.toggle('molar-mode',molar);
  $('materialTotalLabel').textContent=basis.total;$('materialBasisHint').textContent=basis.hint;
  $('materialPercentLabel').textContent=molar?'目标浓度':`目标浓度（% ${basis.name}）`;
  $('materialMolarMassLabel').hidden=!molar;$('materialMassUnitLabel').hidden=!molar;
  $('materialInputHint').textContent=molar?'g/mol、mg/mol 为摩尔质量单位，须按实际原料填写；支持科学计数法。':'浓度为百分数：20% 填 20。支持科学计数法。';
  $('materialEmpty').querySelector('p').textContent=molar?'填写最终体积、目标浓度及各材料摩尔质量，再计算用量。':'填写最终总量、材料名称和目标浓度，再计算用量。';
  $('materialUnit').replaceChildren(...basis.units.map(unit=>{const option=document.createElement('option');option.value=option.textContent=unit;return option;}));
  $('materialUnit').value=basis.units.includes(preferredUnit)?preferredUnit:basis.units[0];
}
function materialRenderRows(){
  const molar=$('materialBasis').value==='molar';
  $('materialComponents').replaceChildren(...materialState.recipe.components.map((row,index)=>{
    const line=document.createElement('div');line.className='material-columns material-row';
    function inputField(key,label){
      const input=document.createElement('input');input.value=numberText(row[key]);input.autocomplete='off';
      input.dataset.field=key;input.setAttribute('aria-label',`第${index+1}组分 ${label}`);
      if(key!=='name')input.inputMode='decimal';else input.maxLength=120;
      input.addEventListener('input',()=>{row[key]=input.value;materialInvalidate();});
      input.addEventListener('focus',()=>line.scrollIntoView({block:'nearest',behavior:'instant'}));return input;
    }
    function unitField(key,label,options,initial){
      const select=document.createElement('select');select.dataset.field=key;
      select.setAttribute('aria-label',`第${index+1}组分 ${label}`);
      select.replaceChildren(...options.map(value=>{const option=document.createElement('option');option.value=option.textContent=value;return option;}));
      const aliases={'µM':'μM',uM:'μM','mol/L':'M','mmol/L':'mM','μmol/L':'μM','µmol/L':'μM','nmol/L':'nM'};
      const value=aliases[row[key]]||row[key];select.value=options.includes(value)?value:initial;row[key]=select.value;
      select.addEventListener('change',()=>{row[key]=select.value;materialInvalidate();});
      select.addEventListener('focus',()=>line.scrollIntoView({block:'nearest',behavior:'instant'}));return select;
    }
    line.append(inputField('name','材料名称'));
    if(molar){
      const concentration=document.createElement('div');concentration.className='material-field-pair';
      concentration.append(inputField('concentration','目标摩尔浓度'),unitField('concentration_unit','摩尔浓度单位',['M','mM','μM','nM'],'μM'));
      const mass=document.createElement('div');mass.className='material-field-pair material-molar-mass';
      mass.append(inputField('molar_mass','摩尔质量'),unitField('molar_mass_unit','摩尔质量单位',['g/mol','mg/mol'],'g/mol'));
      line.append(concentration,mass);
    }else line.append(inputField('percent','目标百分浓度'));
    const remove=document.createElement('button');remove.type='button';remove.className='remove';remove.textContent='×';
    remove.setAttribute('aria-label',`删除第${index+1}组分`);remove.disabled=materialState.recipe.components.length===1;
    remove.addEventListener('click',()=>{materialState.recipe.components.splice(index,1);materialRenderRows();materialInvalidate();});
    line.append(remove);return line;
  }));
}
function materialApplyRecipe(data,profile=null){
  materialState.recipe=clone(data);materialState.current=profile?clone(profile):null;materialState.dirty=false;
  $('materialBasis').value=data.basis;materialBasisLabels(data.unit);
  $('materialTotal').value=numberText(data.total);$('materialSolvent').value=data.solvent||'';
  $('materialMassUnit').value=({'µg':'μg',ug:'μg'}[data.mass_unit]||data.mass_unit||'mg');
  $('materialTemplateName').value=profile?profile.name:'';
  materialRenderRows();$('materialComponents').scrollTop=0;materialInvalidate('请核对本次材料配方后计算。',false);
}
function materialProfiles(profiles,selected){
  materialState.profiles=profiles;
  $('materialTemplates').replaceChildren(...profiles.map(profile=>{const option=document.createElement('option');option.value=profile.id;option.textContent=profile.name;return option;}));
  if(profiles.length)$('materialTemplates').value=profiles.some(profile=>profile.id===selected)?selected:profiles[0].id;
  $('materialTemplateCount').textContent=`${profiles.length} 个模板`;materialControls();materialCurrentLabel();
}
async function materialInitialize(){
  if(materialState.ready||materialState.initializing)return;
  materialState.initializing=true;
  try{
    const data=await call('materials_bootstrap');materialState.storageError=data.storage_error;
    materialState.ready=true;materialProfiles(data.profiles);materialNotice(materialState.storageError);
    materialStatus(materialState.storageError?'材料模板库读取失败，仍可填写配方并计算。':'准备就绪：选择浓度口径，填写本次材料配方。');
  }catch(error){materialNotice(`材料模块初始化失败：${error.message}`);materialStatus('请重新启动程序后重试。');}
  finally{materialState.initializing=false;materialControls();}
}
async function materialCalculate(){
  if(!materialState.ready||materialState.calculating)return;
  const revision=materialState.revision,data=materialRequest();materialState.calculating=true;materialControls();materialNotice(materialState.storageError);
  try{
    const result=await call('materials_calculate',data);if(materialState.revision!==revision)return;
    materialState.result=result;
    $('materialResultHeaders').replaceChildren(...result.headers.map(value=>{const th=document.createElement('th');th.scope='col';th.textContent=value;return th;}));
    $('materialResultRows').replaceChildren(...result.rows.map(row=>{const tr=document.createElement('tr');row.forEach(value=>{const td=document.createElement('td');td.textContent=value;tr.append(td);});return tr;}));
    $('materialNotes').replaceChildren(...result.notes.map(note=>{const p=document.createElement('p');p.textContent=note;return p;}));
    $('materialNotesDetails').hidden=!result.notes.length;$('materialNotesDetails').open=false;$('materialSummary').textContent=result.summary;
    $('materialEmpty').hidden=true;$('materialResultBadge').textContent='已计算';$('materialResultBadge').className='badge ready';
    $('materialResultHeading').closest('section').scrollIntoView({block:'nearest',behavior:'instant'});
    materialStatus('计算完成。可复制配制表或导出 CSV。');
  }catch(error){
    if(materialState.revision!==revision)return;
    materialInvalidate('计算未完成，请按提示修改输入。',false);materialNotice(error.message);
    $('materialResultBadge').textContent='检查输入';$('materialResultBadge').className='badge error';
    $('materialEmpty').querySelector('strong').textContent='请检查本次材料配方';
  }finally{materialState.calculating=false;materialControls();}
}
async function materialSaveTemplate(update=false){
  if(!materialState.ready||materialState.libraryBusy||materialState.storageError)return;
  const id=update?materialState.current?.id:null;if(update&&!id)return;
  const revision=materialState.revision,data=materialRequest(),name=$('materialTemplateName').value;materialState.libraryBusy=true;materialControls();materialNotice(null);
  try{
    const saved=await call('materials_save_template',name,data,id);
    materialState.current=clone(saved.profile);materialState.dirty=revision!==materialState.revision||$('materialTemplateName').value!==name;
    if(!materialState.dirty)$('materialTemplateName').value=saved.profile.name;
    materialProfiles(saved.profiles,saved.profile.id);
    materialStatus(materialState.dirty?'材料模板已保存；之后的输入更改尚未保存。':'材料模板已保存在本机。');
  }catch(error){materialNotice(error.message);materialStatus('保存未完成，已有模板和当前输入保留。');}
  finally{materialState.libraryBusy=false;materialControls();}
}
async function materialLoadTemplate(){
  const id=$('materialTemplates').value;if(!id||materialState.libraryBusy||materialState.storageError)return;
  const revision=materialState.revision;materialState.libraryBusy=true;materialControls();
  try{
    const data=await call('materials_load_template',id);materialProfiles(data.profiles,id);
    if(materialState.revision===revision){materialApplyRecipe(data.profile.recipe,data.profile);materialStatus('已调用材料模板，请核对配方后计算。');}
    else materialStatus('模板已读取；当前输入已更改，本次未替换。');
  }catch(error){materialNotice(error.message);}
  finally{materialState.libraryBusy=false;materialControls();}
}
async function materialDeleteTemplate(){
  const id=$('materialTemplates').value,profile=materialState.profiles.find(item=>item.id===id);
  if(!profile||materialState.libraryBusy||materialState.storageError)return;
  if(!await modal('删除材料模板',`删除“${profile.name}”？当前填写的材料配方和计算结果会保留。`,{confirm:'删除'}))return;
  materialState.libraryBusy=true;materialControls();
  try{
    const data=await call('materials_delete_template',id);
    if(materialState.current?.id===id){materialState.current=null;materialState.dirty=false;}
    materialProfiles(data.profiles);materialNotice(null);materialStatus('材料模板已删除，当前配方保留。');
  }catch(error){materialNotice(error.message);}
  finally{materialState.libraryBusy=false;materialControls();}
}
async function materialUseResult(method){
  if(!materialState.result)return;
  try{const message=await call(method,materialState.result.id,materialRequest());if(message)materialStatus(message);}
  catch(error){materialNotice(error.message);}
}
function materialHelp(){
  return modal('材料配制使用说明','一、选择浓度口径\nw/w：组分质量占最终配方总质量的百分比。w/v：每 100 mL 最终配方中的组分质量，以 g 表示。v/v：液体组分体积占最终配方体积的百分比。摩尔浓度：M = mol/L，支持 M、mM、μM、nM。切换口径不会进行浓度的物理换算；跨口径换算需要相应密度等信息。\n\n二、填写最终总量与组分\n百分浓度 20% 填 20。摩尔浓度模式须为每种材料填写目标浓度、浓度单位、摩尔质量及其单位（g/mol 或 mg/mol），再选择 g、mg 或 μg 作为称量单位。摩尔质量应与实际使用的原料形式一致，例如盐或水合物，程序不代填。\n可添加多个组分，所有组分均以同一最终总量为分母。材料名称须填写；最终总量、目标浓度及摩尔质量可留空保存模板，计算前须补齐。溶剂 / 基质名称可留空，结果中统一显示为“溶剂 / 基质”。\n\n三、按结果配制\nw/w 按剩余质量补足溶剂或基质。w/v、v/v 与摩尔浓度模式均加入适量溶剂后定容至最终体积，不将固体质量当成体积，也不假设混合体积可直接相加。摩尔浓度模式按质量(g) = 浓度(mol/L) × 最终体积(L) × 摩尔质量(g/mol) 计算；mg/mol 转为 g/mol 时除以 1000。程序只按纯组分计算用量，不判断溶解性、相容性、成胶性、纯度或母液稀释。\n\n四、独立模板与结果\n材料模板和菌液模板分别存储。两模块切换保留各自输入和结果；修改当前模块输入会使其旧结果失效。Ctrl + Enter 计算当前模块，Ctrl + S 保存当前模块模板。复制和 CSV 会附带浓度口径及配制说明。',{confirm:'关闭',cancel:false});
}
function switchModule(module){
  if(!['mix','materials'].includes(module)||$('modal').open||$('cfuDialog').open)return;
  const materials=module==='materials';document.body.dataset.module=module;
  $('mixPanel').hidden=materials;$('materialsPanel').hidden=!materials;$('openCFU').hidden=materials;
  $('mixTab').setAttribute('aria-selected',String(!materials));$('materialsTab').setAttribute('aria-selected',String(materials));
  $('mixTab').tabIndex=materials?-1:0;$('materialsTab').tabIndex=materials?0:-1;
  if(materials&&!materialState.ready)void materialInitialize();
}
$('mixTab').addEventListener('click',()=>switchModule('mix'));
$('materialsTab').addEventListener('click',()=>switchModule('materials'));
document.querySelector('.module-tabs').addEventListener('keydown',event=>{
  if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
  event.preventDefault();const module=event.key==='Home'?'mix':event.key==='End'?'materials':document.body.dataset.module==='mix'?'materials':'mix';
  switchModule(module);$(module==='mix'?'mixTab':'materialsTab').focus();
});
$('materialBasis').addEventListener('change',()=>{materialBasisLabels();materialRenderRows();materialInvalidate('浓度口径已切换；数值未换算，请核对总量、浓度和对应单位。');});
$('materialUnit').addEventListener('change',()=>materialInvalidate());
$('materialMassUnit').addEventListener('change',()=>materialInvalidate());
['materialTotal','materialSolvent'].forEach(id=>$(id).addEventListener('input',()=>materialInvalidate()));
$('materialTemplateName').addEventListener('input',()=>{materialState.dirty=true;materialCurrentLabel();});
$('materialAdd').addEventListener('click',()=>{materialState.recipe.components.push({name:'',percent:''});materialRenderRows();materialInvalidate();$('materialComponents').lastElementChild.querySelector('input').focus();});
$('materialNew').addEventListener('click',()=>{materialApplyRecipe(materialBlank());materialStatus('已新建空白材料配方。');});
$('materialCalculate').addEventListener('click',materialCalculate);
$('materialCopy').addEventListener('click',()=>materialUseResult('materials_copy_result'));
$('materialExport').addEventListener('click',()=>materialUseResult('materials_export_result'));
$('materialLoad').addEventListener('click',materialLoadTemplate);$('materialTemplates').addEventListener('dblclick',materialLoadTemplate);
$('materialTemplates').addEventListener('change',materialControls);
$('materialTemplates').addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.ctrlKey&&!event.metaKey&&!event.altKey){event.preventDefault();materialLoadTemplate();}});
$('materialSaveAs').addEventListener('click',()=>materialSaveTemplate(false));$('materialUpdate').addEventListener('click',()=>materialSaveTemplate(true));
$('materialDelete').addEventListener('click',materialDeleteTemplate);
document.addEventListener('keydown',event=>{
  if(document.body.dataset.module!=='materials'||$('modal').open||$('cfuDialog').open)return;
  if(event.ctrlKey&&event.key==='Enter'){event.preventDefault();materialCalculate();}
  if(event.ctrlKey&&event.key.toLowerCase()==='s'){event.preventDefault();materialSaveTemplate(!!materialState.current);}
});
materialApplyRecipe(materialBlank());
if(window.pywebview?.api)void materialInitialize();else window.addEventListener('pywebviewready',materialInitialize,{once:true});
