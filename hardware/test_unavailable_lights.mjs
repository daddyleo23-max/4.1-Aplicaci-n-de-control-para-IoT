import test from 'node:test';
import assert from 'node:assert/strict';
const light=Object.assign(new EventTarget(),{dataset:{},setAttribute(k,v){this[k]=v;}});
const count={};
globalThis.document=Object.assign(new EventTarget(),{querySelector:s=>s==='#key-light-sound'?light:s==='#command-count'?count:null,querySelectorAll:()=>[]});
globalThis.window=new EventTarget();
const {renderCommands}=await import('../js/ui.js');
test('luces y sonido permanecen deshabilitados aunque el catálogo los habilite',()=>{
 const sent=[];
 for(let i=0;i<2;i++){
  renderCommands(['LUCES','MUSICA','SONIDO'].map((nombre,id_comando)=>({nombre,id_comando,activo:true})),{onCommand:c=>sent.push(c),onDemo:()=>{},onUnavailable:()=>{}});
  assert.equal(light.disabled,true);assert.equal(light.dataset.available,'false');
  for(const type of ['pointerdown','pointerup','click','keydown','keyup'])light.dispatchEvent(new Event(type));
 }
 assert.deepEqual(sent,[]);
});
