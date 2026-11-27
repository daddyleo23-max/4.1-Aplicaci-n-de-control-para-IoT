import test from 'node:test';
import assert from 'node:assert/strict';
globalThis.document = Object.assign(new EventTarget(), {querySelector:()=>null, querySelectorAll:()=>[], hidden:false});
globalThis.window = new EventTarget();
const {elements} = await import('../js/ui.js');
const {bindJoystick} = await import('../js/joystick.js');
class Stick extends EventTarget {
 constructor(axis){super();this.dataset={stickAxis:axis};this.knob={style:{}};}
 querySelector(){return this.knob;}
 getBoundingClientRect(){return {left:0,top:0,width:100,height:100};}
 setPointerCapture(){} releasePointerCapture(){}
}
function fire(target,type,fields={}){const e=new Event(type,{cancelable:true});Object.assign(e,{pointerId:1,button:0,clientX:50,clientY:0,...fields});target.dispatchEvent(e);}
function setup(){const v=new Stick('vertical'),h=new Stick('horizontal'),log=[];elements.sticks=[v,h];bindJoystick(['ADELANTE','ATRAS','GIRAR_IZQUIERDA','GIRAR_DERECHA'].map((nombre,id_comando)=>({nombre,id_comando:id_comando+1,activo:true})),c=>log.push(c.nombre),()=>log.push('STOP'),(a,b)=>log.push(a.nombre+'+'+b.nombre));return {v,h,log};}
test('dos dedos combinan ejes y soltar giro conserva avance',()=>{const {v,h,log}=setup();fire(v,'pointerdown');fire(v,'blur');fire(h,'pointerdown',{pointerId:2,clientX:0,clientY:50});fire(h,'pointerup',{pointerId:2});fire(v,'pointerup');assert.deepEqual(log,['ADELANTE','ADELANTE+GIRAR_IZQUIERDA','ADELANTE','STOP']);});
test('soltar avance conserva giro y cancelar último detiene',()=>{const {v,h,log}=setup();fire(v,'pointerdown',{clientY:100});fire(h,'pointerdown',{pointerId:2,clientX:100,clientY:50});fire(v,'pointerup');fire(h,'pointercancel',{pointerId:2});assert.deepEqual(log,['ATRAS','ATRAS+GIRAR_DERECHA','GIRAR_DERECHA','STOP']);});
test('perder ventana o pestaña detiene ambos sin reanudación',()=>{for(const hidden of [false,true]){const {v,h,log}=setup();fire(v,'pointerdown');fire(h,'pointerdown',{pointerId:2,clientX:0});if(hidden){document.hidden=true;fire(document,'visibilitychange');document.hidden=false;}else fire(window,'blur');fire(v,'pointermove');assert.equal(log.at(-1),'STOP');assert.equal(log.length,3);}});
test('otro dedo en el mismo eje no sustituye al primero',()=>{const {v,log}=setup();fire(v,'pointerdown');fire(v,'pointerdown',{pointerId:3,clientY:100});fire(v,'pointerup',{pointerId:3});assert.deepEqual(log,['ADELANTE']);fire(v,'pointerup');assert.equal(log.at(-1),'STOP');});
