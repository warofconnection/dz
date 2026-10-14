// Regression checks for control flow and IPC boundary handling, not a Cisco simulation.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(__dirname+'/../packet-tracer/clinic8-all-in-one.js','utf8');
function fixture(options={}) {
 const devices=new Map(),links=new Map(),queue=[],notes=new Map(),output=[],saved=[],commands=[];
 let clock=0,id=0,stopped=false;
 const realBool=b=>options.scalarStrings?String(b):b;
 const realNumber=n=>options.scalarStrings?String(n):n;
 const mailStore={},clientMailStore={};let ctx;
 function createDevice(type,model,name) {
  const ports=[],vars={},pages={},dnsRecords={},processes={};let dhcp=false;
  function addPort(full,ether,wireless=false) {
   const match=full.match(/^([^0-9]+)(.*)$/),family=match[1],number=match[2];
   let ip='0.0.0.0',link=null;
   const p={getName:()=>options.splitPortNames?family:full,getPortNameNumber:()=>number,getTerminalTypeShortString:()=>family,
    isEthernetPort:()=>realBool(ether),isWirelessPort:()=>realBool(wireless),getLink:()=>link,
    setDhcpClientFlag(enabled){if(enabled)assignDhcp(p)},setIpSubnetMask(addr){ip=addr},getIpAddress:()=>options.numericIps?ip.split('.').reduce((n,v)=>n*256+Number(v),0):ip,
    setDefaultGateway(){},setDnsServerIp(){},getObjectUuid:()=>name+'/'+full,
    setLink(l){link=l},get canonical(){return full}};
   ports.push(p);return p;
  }
  if(type===0){for(let i=0;i<3;i++)addPort('GigabitEthernet0/'+i,true)}
  else if(type===1){for(let i=1;i<=24;i++)addPort('FastEthernet0/'+i,true);for(let i=1;i<=2;i++)addPort('GigabitEthernet0/'+i,true)}
  else if(type===7){addPort('FastEthernet0',true);addPort('Wireless0',false,true)}
  else if(type===19)addPort('Wireless0',false,true);
  else addPort('FastEthernet0',true);
  function assignDhcp(p) {
   if(options.missingDhcp)return;
   const n=ctx.NODES.find(n=>n.name===name);if(!n)return;
   const e=n.endpoint,site={C1:1,C2:2,B1:11,B2:12}[n.guest_floor||(e&&e.floor)];
   if(!site)return;const vlan=n.guest_floor?90:e.vlan;p.setIpSubnetMask('10.'+site+'.'+vlan+'.50');
  }
  const user=(key,client=false)=>({setName(){},setUser(v){this.user=v},setMailId(){},setPassword(){},setSmtpServer(){},setPop3Server(){},getMailBox:()=>({getMails:()=>client?(clientMailStore[key]||[]):(mailStore[key]||[])})});
  const emailUser={user:"",setName(){},setUser(v){this.user=v},setMailId(){},setPassword(){},setSmtpServer(){},setPop3Server(){},getMailBox(){return {getMails:()=>clientMailStore[this.user]||[]}}};
  const wireless={setSsid(v){this.ssid=v},getSsid(){return this.ssid},setNetworkType(){},setAuthenType(){},setEncryptType(){},getWpaProcess:()=>({setKey(){}})};
  let lastPage='';
  const httpClient={cancel(){},setHttps(){},go(url){
    if(options.failHttp)return realBool(false);
    let target=url.includes('mis.clinic8.test')?'SRV-MIS':url.includes('www.example.test')?'PUBLIC-WEB':url.includes('10.1.30.10')?'SRV-MIS':'';
    if(type===19 && target==='SRV-MIS' && !options.leakGuest)return realBool(true);
    if(target)lastPage=devices.get(target).getProcess('HttpServer').getPage('index.html');return realBool(true);
   },getLastPageContent:()=>lastPage};
  processes.HttpServer={setEnable(v){this.enabled=v},isEnabled(){return realBool(!!this.enabled)},setPageContents(u,b){pages[u]=b},getPage:u=>pages[u]||''};
  processes.DnsServer={setEnable(){},removeIpAddress(n){delete dnsRecords[n]},addIpAddress(n,ip){dnsRecords[n]=ip},getIpAddOfDomain:n=>dnsRecords[n]};
  processes.SmtpServer={setEnable(v){this.enabled=v},isEnabled(){return realBool(!!this.enabled)},setServerDomainName(){}};
  processes.Pop3Server={setEnable(v){this.enabled=v},isEnabled(){return realBool(!!this.enabled)}};
  processes.EmailServer={addUser(u){if(!mailStore[u])mailStore[u]=[];return true},changePassword(){},getEmailUser:u=>user(u)};
  processes.EmailClient={getEmailUser:()=>emailUser};
  processes.SmtpClient={sendMail(from,to,subject,content){if(!options.missingMail)mailStore[to.split('@')[0]].push({subject,content});return realBool(true)}};
  processes.Pop3Client={getMailIpc(){const key=name.slice(0,2).toLowerCase();clientMailStore[key]=[...(mailStore[key]||[])];return realBool(true)}};
  processes.HttpClient=httpClient;processes.WirelessServer=wireless;processes.WirelessClient=wireless;
  const d={getName:()=>name,getType:()=>realNumber(type),getModel:()=>model,getPortCount:()=>realNumber(ports.length),getPortAt:i=>ports[i],
    setName(n){devices.delete(name);name=n;devices.set(n,d)},getProcess:n=>{assert(processes[n],n);return processes[n]},
    skipBoot(){},hasCustomVar:k=>realBool(k in vars),getCustomVarStr:k=>vars[k],addCustomVar(k,v){vars[k]=v},
    enterCommand(line,mode){commands.push([name,line,mode]);if(options.badIos && line===options.badIos)return {first:realNumber(2),second:'% Invalid input'};
      return {first:realNumber(0),second:line.includes('show access-lists')?'deny ip any 10.0.0.0 0.255.255.255 (4 matches)':''}},
    setDhcpFlag(v){dhcp=v;if(v)for(const p of ports)assignDhcp(p)},get _ports(){return ports}};
  devices.set(name,d);return d;
 }
 const ws={addDevice(type,model){const n='generated'+id++;createDevice(type,model,n);return n},
  createLink(a,p1,b,p2,cable){assert([8100,8101].includes(cable));const x=devices.get(a)._ports.find(p=>p.canonical===p1),y=devices.get(b)._ports.find(p=>p.canonical===p2);assert(x&&y,'canonical port names must be resolved');if(options.failCable)return false;
    assert(!x.getLink()&&!y.getLink());const uuid='wire-'+links.size,link={getObjectUuid:()=>uuid};x.setLink(link);y.setLink(link);links.set(uuid,[a,p1,b,p2,cable]);return realBool(true)},
  addNote(x,y,z,text){const n='note'+id++;notes.set(n,text);return n},changeNoteText(n,s){notes.set(n,s)},getCanvasNoteIds:()=>[...notes.keys()],getCanvasNoteText:n=>notes.get(n),removeCanvasItem(n){return notes.delete(n)}};
 const app={getActiveWorkspace:()=>({getLogicalWorkspace:()=>ws}),getDefaultFileSaveLocation:()=>options.winPath?'C:\\Users\\Student\\Documents':'/tmp',getUserFolder:()=>'/tmp',fileSaveAs(path){saved.push(path);return realBool(!options.failSave)}};
 const ipc={network:()=>({getDeviceCount:()=>realNumber(devices.size),getDeviceAt:i=>[...devices.values()][i],getDevice:n=>devices.get(n)}),appWindow:()=>app,ipcManager:()=>({thisInstance:()=>({stop(){stopped=true;ctx.cleanUp();return true}})})};
 ctx=vm.createContext({ipc,dprint:s=>output.push(s),setTimeout(f,ms){const t={f,at:clock+ms,cancel:false};queue.push(t);return t},clearTimeout(t){t.cancel=true}});
 vm.runInContext(source,ctx);
 function drain(){let iterations=0;while(queue.length){assert(++iterations<5000,'timers must terminate');queue.sort((a,b)=>a.at-b.at);const t=queue.shift();clock=t.at;if(!t.cancel)t.f()}}
 return {ctx,devices,links,notes,output,saved,commands,createDevice,wire(a,p1,b,p2){return ws.createLink(a,p1,b,p2,8100)},run(){ctx.main();drain()},get stopped(){return stopped}};
}
function done(f){const priorSaves=f.saved.length;f.run();assert.equal(f.ctx.BUILD_STATE,'DONE',f.ctx.BUILD_ERRORS.join('\n'));assert.equal(f.links.size,112);assert(f.ctx.BUILD_COMPLETE);assert.equal(f.saved.length,priorSaves+1);assert(f.stopped)}
let fresh=fixture();done(fresh);assert.equal(fresh.devices.size,117);assert.equal(fresh.ctx.CREATED,117);
const commandCount=fresh.commands.length;done(fresh);assert.equal(fresh.devices.size,117);assert.equal(fresh.ctx.CREATED,0);assert.equal(fresh.links.size,112);assert(fresh.commands.length<commandCount*1.2,'already applied IOS must be skipped');
let stringValues=fixture({scalarStrings:true,splitPortNames:true,winPath:true});done(stringValues);assert(stringValues.saved[0].startsWith('C:\\Users\\Student\\Documents\\clinic8-v3-'));
let numericIps=fixture({numericIps:true});done(numericIps);
let partial=fixture();partial.createDevice(8,'PC-PT','C1-PC01');partial.createDevice(0,'2911','R-C1');partial.createDevice(8,'PC-PT','Unrelated-PC');done(partial);assert.equal(partial.devices.size,118);assert(partial.devices.has('Unrelated-PC'));
let partiallyWired=fixture();partiallyWired.createDevice(1,'2960-24TT','SW-C1A');partiallyWired.createDevice(8,'PC-PT','C1-PC01');partiallyWired.wire('SW-C1A','FastEthernet0/1','C1-PC01','FastEthernet0');done(partiallyWired);assert.equal(partiallyWired.links.size,112);
let occupied=fixture();occupied.createDevice(1,'2960-24TT','SW-C1A');occupied.createDevice(8,'PC-PT','Other-PC');occupied.wire('SW-C1A','FastEthernet0/1','Other-PC','FastEthernet0');occupied.run();assert.equal(occupied.ctx.BUILD_STATE,'ERROR');assert.equal(occupied.links.size,1);assert(occupied.devices.has('Other-PC'));
let wrong=fixture();wrong.createDevice(8,'PC-PT','R-C1');wrong.run();assert.equal(wrong.ctx.BUILD_STATE,'ERROR');assert.equal(wrong.links.size,0);assert.equal(wrong.devices.get('R-C1').getType(),8);
for(const options of [{failCable:true},{badIos:'hostname R-B1'},{missingDhcp:true},{failHttp:true},{missingMail:true},{leakGuest:true},{failSave:true}]) {
 let f=fixture(options);f.run();assert.equal(f.ctx.BUILD_STATE,'ERROR',JSON.stringify(options));assert(!f.ctx.BUILD_COMPLETE);assert(f.ctx.BUILD_ERRORS.length>0);
}
console.log('PASS: empty build, repeat run, partial network, preserved unrelated device, string scalars, split port names, Windows path, cable/IOS/DHCP/HTTP/mail/guest/save failure detection. IPC mocks only; Packet Tracer runtime not verified.');
