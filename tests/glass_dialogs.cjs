const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function fixture() {
  const elements = new Map();
  function element(id) {
    if (!elements.has(id)) elements.set(id, {
      returnValue: '', handlers: [], value: '',
      addEventListener(type, callback, options) { this.handlers.push({type, callback, once:options?.once}); },
      showModal() { this.open=true; }, focus() {}, select() {},
      close(value) {
        if (value !== undefined) this.returnValue=value;
        this.open=false;
        const handlers=this.handlers.filter(h=>h.type==='close');
        this.handlers=this.handlers.filter(h=>!(h.type==='close'&&h.once));
        handlers.forEach(h=>h.callback());
      }
    });
    return elements.get(id);
  }
  const context=vm.createContext({document:{getElementById:element,querySelectorAll:()=>[],addEventListener(){}},
                                  window:{addEventListener(){}},console});
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../glass_ui/app.js'),'utf8'),context);
  return {context,element};
}

test('Escape after a previous confirmation cannot confirm a destructive dialog', async()=>{
  const {context,element}=fixture();
  element('modal').returnValue='ok';
  const result=vm.runInContext("modal('删除模板','删除选中模板？')",context);
  element('modal').close(); // Escape closes without replacing returnValue.
  assert.equal(await result,null);
});

test('Explicit confirmation and cancellation resolve differently on repeated dialogs', async()=>{
  const {context,element}=fixture();
  const first=vm.runInContext("modal('重命名','',{input:'配方A'})",context);
  element('modalInput').value='配方B';element('modal').close('ok');
  assert.equal(await first,'配方B');
  const second=vm.runInContext("modal('删除模板','')",context);
  element('modal').close('cancel');
  assert.equal(await second,null);
});
