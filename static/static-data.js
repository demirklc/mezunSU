'use strict';
window.MezunStatic=(()=>{
 const pending=new Map();
 function read(path){if(!pending.has(path))pending.set(path,fetch(new URL('data/'+path,document.baseURI)).then(async r=>{if(!r.ok)throw Error('Bu müfredatın verisi henüz hazırlanamadı. Daha sonra tekrar deneyin.');return r.json()}).catch(e=>{pending.delete(path);throw e}));return pending.get(path)}
 const decorate=value=>({...value,_snapshot:true,_cache:{fresh:true,fetched_at:value.updated_at||0,retry_after:Number.MAX_SAFE_INTEGER}});
 async function request(path,opt={}){
  if(path==='/programs')return read('programs.json');
  if(path.startsWith('/terms/'))return read('terms/'+path.split('/')[2]+'.json');
  if(path.startsWith('/curriculum/')){const [, ,program,term]=path.split('/');return read('curriculum/'+program+'/'+term+'.json')}
  if(path==='/course-credit-cache'){const credits=await read('credits.json'),codes=JSON.parse(opt.body).codes;return {credits:Object.fromEntries(codes.filter(c=>credits[c]).map(c=>[c,decorate(credits[c])]))}}
  if(path.startsWith('/course-credit/')){const code=decodeURIComponent(path.slice('/course-credit/'.length)),credits=await read('credits.json');return decorate(credits[code]||{code,engineering:null,basic:null,prerequisites:null,_unavailable:true})}
  throw Error('İşlem desteklenmiyor.');
 }
 return {request};
})();
