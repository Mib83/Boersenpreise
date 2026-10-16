// Boundary behavior and rounded chart geometry, without Home Assistant or a browser.
const {readFileSync}=require('node:fs');
const {join}=require('node:path');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const context={HTMLElement:class {},customElements:{get:()=>true,define:()=>{}}};
vm.createContext(context);
vm.runInContext(readFileSync(join(__dirname,'../custom_components/boersenpreise/panel.js'),'utf8'),context);
const levels=[{limit:-2,color:'blue'},{limit:5,color:'green'},{limit:10,color:'yellow'},{limit:20,color:'orange'}];
for(const [price,color] of [[-5,'blue'],[-2,'blue'],[-1,'green'],[5,'green'],[5.01,'yellow'],[10,'yellow'],[15,'orange'],[21,'red']]) {
 assert.equal(context.priceColor(price,levels,'red'),color);
}
assert.equal(context.priceColor(5,[],'red'),'red');
for(const negative of [false,true]) {
 const path=context.roundedBar(1,2,8,30,negative);
 assert.equal((path.match(/Q /g)||[]).length,2);
 assert.ok(!/NaN|Infinity/.test(path));
 assert.ok(!/NaN|Infinity/.test(context.roundedBar(1,2,8,0.1,negative)));
}
console.log('Frontend: Preisgrenzen, zusätzliche Farben, leere Liste und Balkenrundungen OK');

const lower={limit:0,color:'blue'};
for(const [price,color] of [[-0.01,'blue'],[0,'green'],[5,'green'],[5.01,'yellow'],[10,'yellow'],[21,'red']]) {
 assert.equal(context.priceColor(price,[{limit:5,color:'green'},{limit:10,color:'yellow'}],'red',lower),color);
}
assert.equal(context.priceColor(-1,[],'red',lower),'blue');
assert.equal(context.priceColor(0,[],'red',lower),'red');
console.log('Frontend: Unterhalb-Farbe, exakte Grenzwerte und Oberhalb-Farbe OK');
