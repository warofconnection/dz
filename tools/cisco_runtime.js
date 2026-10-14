// ECMAScript 5 / QtScript. Intended to run as a single persistent Script Module.
var BUILD_VERSION="clinic8-v3.1";
// Withdrawn after a real Packet Tracer crash. Never start automatically.
var BUILDER_ENABLED=false;
var LAB_PASSWORD="Clinic8-Lab-2026"; // Only synthetic lab accounts and lab Wi-Fi.
var BUILD_COMPLETE=false, BUILD_STATE="NOT_STARTED", BUILD_REPORT=[], BUILD_ERRORS=[];
var DEVICES={}, PORTS={}, WORKSPACE=null, STATUS_NOTE=null, TIMERS=[], RUNNING=false;
var CREATED=0, REUSED=0, WIRED=0, DHCP_ATTEMPTS=0, HTTP_TESTS=[];
var MAIL_TESTS=[], RUN_TAG="", SAVED_FILE="";
var NODE_LABELS={};

function text(x) {return String(x===null || typeof x==="undefined" ? "" : x);}
function number(x,description) {
    var n=Number(x);
    if(!isFinite(n)) throw new Error("Invalid numeric API value for "+description+": "+text(x));
    return n;
}
function flag(x) {return x===true || x===1 || x==="true" || x==="1";}
function ipv4(value) {
    var s=text(value);
    if(/^[0-9]+$/.test(s)) {
        var n=Number(s);
        if(n>=0 && n<=4294967295)return [(n>>>24)&255,(n>>>16)&255,(n>>>8)&255,n&255].join(".");
    }
    if(value && typeof value.length==="number" && value.length===4)return [value[0],value[1],value[2],value[3]].join(".");
    return s;
}
function report(s) {
    BUILD_REPORT.push(s);
    if(typeof dprint==="function") dprint(s);
    if(WORKSPACE && STATUS_NOTE) WORKSPACE.changeNoteText(STATUS_NOTE,"Clinic8 v3 — "+s);
}
function fail(e) {
    RUNNING=false;BUILD_COMPLETE=false;BUILD_STATE="ERROR";
    var message=text(e && e.message ? e.message : e);
    BUILD_ERRORS.push(message);report("ERROR: "+message+". Partial network preserved.");
    // Self-stop removed: destroying an executing Script Module is unsafe to assume.
}
function later(f,ms) {
    var t=setTimeout(function(){if(!RUNNING)return;try{f();}catch(e){fail(e);}},ms);
    TIMERS.push(t);
}
function dev(name) {
    if(!DEVICES[name])throw new Error("Missing project device: "+name);
    return DEVICES[name];
}
function norm(s) {
    return text(s).replace(/\s+/g,"").toLowerCase()
        .replace(/^fastethernet/,"fa").replace(/^gigabitethernet/,"gi").replace(/^ethernet/,"eth");
}
function uuid(o) {
    if(!o)return "";
    var u;
    if(typeof o.getObjectUuid==="function")u=text(o.getObjectUuid());
    else if(typeof o.getObjectUUID==="function")u=text(o.getObjectUUID());
    else if(typeof o.objectUuid!=="undefined")u=text(o.objectUuid);
    else throw new Error("Link object has no supported UUID accessor");
    if(!u || /^\{?0{8}-0{4}-0{4}-0{4}-0{12}\}?$/.test(u)) return "";
    return u;
}
function inventoryPorts(name) {
    var d=dev(name),count=number(d.getPortCount(),name+" port count"),out=[];
    for(var i=0;i<count;i++) {
        var p=d.getPortAt(i),raw=text(p.getName()),num=text(p.getPortNameNumber());
        // Some port objects return the family name separately from its number.
        var canonical=raw;
        if(num && !/[0-9]/.test(raw))canonical=raw+num;
        var shortName=text(p.getTerminalTypeShortString())+num;
        out.push({object:p,name:canonical,aliases:[canonical,raw,shortName],ethernet:flag(p.isEthernetPort()),wireless:flag(p.isWirelessPort())});
    }
    PORTS[name]=out;return out;
}
function port(name,wanted) {
    var all=PORTS[name] || inventoryPorts(name),found=null;
    for(var i=0;i<all.length;i++) {
        if(wanted==="@ETH" && all[i].ethernet){found=all[i];break;}
        if(wanted==="@WIFI" && all[i].wireless){found=all[i];break;}
        for(var k=0;k<all[i].aliases.length;k++) {
            if(norm(all[i].aliases[k])===norm(wanted)){found=all[i];break;}
        }
        if(found)break;
    }
    if(!found) {
        var names=[];for(var j=0;j<all.length;j++)names.push(all[j].name);
        throw new Error(name+" ["+text(dev(name).getModel())+"]: missing "+wanted+"; actual ports: "+names.join(", "));
    }
    return found;
}
function scanDevices() {
    DEVICES={};PORTS={};
    var network=ipc.network(),count=number(network.getDeviceCount(),"network device count");
    report("Existing devices reported by API: "+count);
    for(var i=0;i<count;i++) {
        var d=network.getDeviceAt(i),n=text(d.getName());
        if(DEVICES[n])throw new Error("Duplicate device name in current network: "+n);
        DEVICES[n]=d;
    }
}
function validateType(n,d) {
    var got=number(d.getType(),n.name+" device type");
    if(got!==n.type)throw new Error(n.name+" already exists with wrong type "+got+" (expected "+n.type+"). Preserved unchanged.");
}
function ensureDevices() {
    scanDevices();
    for(var i=0;i<NODES.length;i++) {
        var n=NODES[i],d=DEVICES[n.name];
        if(d){validateType(n,d);REUSED++;}
        else {
            var generated=text(WORKSPACE.addDevice(n.type,n.model,n.x,n.y));
            if(!generated)throw new Error("Cannot create "+n.name+" model "+n.model);
            d=ipc.network().getDevice(generated);
            d.setName(n.name);
            if(text(d.getName())!==n.name)throw new Error("Rename failed for "+n.name);
            validateType(n,d);DEVICES[n.name]=d;CREATED++;
        }
        inventoryPorts(n.name);
    }
    // Resolve EVERY port before creating any cable, so a bad model cannot leave
    // another partially wired network. The global device count is not a gate.
    for(var j=0;j<LINKS.length;j++){port(LINKS[j][0],LINKS[j][1]);port(LINKS[j][2],LINKS[j][3]);}
    for(var q=0;q<NODES.length;q++)if(NODES[q].guest_floor)port(NODES[q].name,"@WIFI");
    report("Devices resolved: "+NODES.length+"; created "+CREATED+", reused "+REUSED+". All required ports found.");
    later(connectAll,100);
}
function addProjectLabels() {
    var existing=WORKSPACE.getCanvasNoteIds(),seen={};
    for(var k=0;k<existing.length;k++)seen[text(WORKSPACE.getCanvasNoteText(existing[k]))]=true;
    var labels=[[70,420,"C1 — Центральный корпус, этаж 1: регистратура, терапия, диагностика"],
        [70,1000,"C2 — Центральный корпус, этаж 2: специалисты, администрация, ИТ"],
        [1150,420,"B1 — Филиал 1: регистратура, терапия, сестринская"],
        [1150,1000,"B2 — Филиал 2: регистратура, терапия, сестринская"],
        [750,20,"Каналы оператора: филиалы — 100 Мбит/с; Интернет — 200 Мбит/с"]];
    for(var i=0;i<labels.length;i++)if(!seen[labels[i][2]])WORKSPACE.addNote(labels[i][0],labels[i][1],1,labels[i][2]);
    // Device IDs on the canvas match port descriptions and ports.csv.
}
function connectAll() {
    BUILD_STATE="CABLING";
    for(var i=0;i<LINKS.length;i++) {
        var l=LINKS[i],a=port(l[0],l[1]),b=port(l[2],l[3]);
        var la=uuid(a.object.getLink()),lb=uuid(b.object.getLink());
        if(la || lb) {
            if(la && la===lb){WIRED++;continue;}
            throw new Error("Occupied port on "+l[0]+"/"+a.name+" or "+l[2]+"/"+b.name+". Existing cable preserved.");
        }
        var type1=number(dev(l[0]).getType(),"link endpoint type"),type2=number(dev(l[2]).getType(),"link endpoint type");
        var cable=((type1===0 && type2===0)||(type1===1 && type2===1))?8101:8100;
        var ok=WORKSPACE.createLink(l[0],a.name,l[2],b.name,cable);
        // Verify the actual port links, rather than trusting only a return value.
        la=uuid(a.object.getLink());lb=uuid(b.object.getLink());
        if(!la || la!==lb)throw new Error("Cable not created: "+l[0]+"/"+a.name+" -> "+l[2]+"/"+b.name+"; type="+cable+"; API returned "+text(ok));
        WIRED++;
    }
    addProjectLabels();
    report("Cables verified by both endpoint UUIDs: "+WIRED+" / "+LINKS.length);
    var names=[];for(var name in CONFIGS)if(CONFIGS.hasOwnProperty(name))names.push(name);
    names.sort();later(function(){configureNext(names,0);},1500);
}
function statusOf(result) {
    if(result===null || typeof result==="undefined")throw new Error("CiscoDevice.enterCommand returned no status");
    var v;
    if(typeof result==="number")return result;
    if(typeof result==="string") {
        try{return statusOf(JSON.parse(result));}catch(e){}
    }
    if(typeof result.first!=="undefined")v=result.first;
    else if(typeof result.status!=="undefined")v=result.status;
    else if(typeof result[0]!=="undefined")v=result[0];
    else throw new Error("Unknown IOS command status format: "+JSON.stringify(result));
    return number(v,"IOS command status");
}
function command(d,name,line,mode) {
    var result=d.enterCommand(line,mode || "");
    var status=statusOf(result);
    if(status!==0)throw new Error("IOS "+name+": "+line+"; status="+status+"; response="+JSON.stringify(result));
    return result;
}
function configureNext(names,index) {
    BUILD_STATE="IOS_CONFIG";
    if(index>=names.length){later(configureHosts,100);return;}
    var name=names[index],d=dev(name);
    if(flag(d.hasCustomVar("clinic8_config")) && text(d.getCustomVarStr("clinic8_config"))===BUILD_VERSION) {
        report("IOS configuration already applied: "+name);later(function(){configureNext(names,index+1);},10);return;
    }
    d.skipBoot();
    command(d,name,"configure terminal","enable");
    if(name!=="R-ISP" && name.slice(0,2)==="R-")command(d,name,"no ip access-list extended GUEST-IN","");
    var lines=CONFIGS[name];
    for(var i=0;i<lines.length;i++) {
        var line=lines[i];
        if(!line || line==="enable" || line==="configure terminal" || line==="end" || line==="write memory")continue;
        command(d,name,line,"");
    }
    command(d,name,"end","");command(d,name,"write memory","enable");
    d.addCustomVar("clinic8_config",BUILD_VERSION);
    report("IOS applied and saved: "+name+" ("+(index+1)+"/"+names.length+")");
    later(function(){configureNext(names,index+1);},100);
}
function staticAddress(name,ip,gateway,dns,wanted) {
    var p=port(name,wanted || "@ETH").object;
    p.setDhcpClientFlag(false);p.setIpSubnetMask(ip,"255.255.255.0");
    p.setDefaultGateway(gateway);p.setDnsServerIp(dns);
    if(ipv4(p.getIpAddress())!==ip)throw new Error("Static IP not applied: "+name+" expected "+ip+", got "+ipv4(p.getIpAddress()));
}
function process(name,type) {
    var p=dev(name).getProcess(type);
    if(!p)throw new Error(name+": unsupported process "+type);
    return p;
}
function wireless(name,ssid) {
    var p=process(name,"WirelessServer");
    p.setSsid(ssid);p.setNetworkType(3);p.setAuthenType(4);p.setEncryptType(4);
    p.getWpaProcess().setKey(LAB_PASSWORD);
    if(text(p.getSsid())!==ssid)throw new Error("SSID not applied: "+name);
}
function guest(name,floor) {
    var p=process(name,"WirelessClient");
    p.setSsid("Clinic8-"+floor+"-Guest");p.setNetworkType(3);p.setAuthenType(4);p.setEncryptType(4);
    p.getWpaProcess().setKey(LAB_PASSWORD);
    port(name,"@WIFI").object.setDhcpClientFlag(true);
    dev(name).setDhcpFlag(true);
}
function configureHosts() {
    BUILD_STATE="HOSTS";
    for(var i=0;i<NODES.length;i++) {
        var n=NODES[i],e=n.endpoint;
        if(n.guest_floor){guest(n.name,n.guest_floor);continue;}
        if(!e)continue;
        var site={C1:1,C2:2,B1:11,B2:12}[e.floor];
        if(e.type==="pc") {dev(n.name).setDhcpFlag(true);port(n.name,"@ETH").object.setDhcpClientFlag(true);}
        else if(e.type==="printer")staticAddress(n.name,"10."+site+".10."+(n.name.slice(-1)==="1"?20:21),"10."+site+".10.1","10.1.30.11");
        else if(e.type==="server")staticAddress(n.name,"10.1.30."+({"SRV-MIS":10,"SRV-MAIL":11,"SRV-FILE":12}[n.name]),"10.1.30.1","10.1.30.11");
        else if(e.type==="ap")wireless(n.name,"Clinic8-"+e.floor+"-Guest");
    }
    staticAddress("PUBLIC-WEB","203.0.113.10","203.0.113.1","203.0.113.10");
    report("Host addresses and four WPA2 guest wireless segments configured.");
    later(configureServices,100);
}
function page(name,title,marker) {
    var h=process(name,"HttpServer");h.setEnable(true);
    h.setPageContents("index.html","<html><head><meta charset='UTF-8'></head><body><h1>"+title+"</h1><p>"+marker+"</p></body></html>");
    if(!flag(h.isEnabled()) || text(h.getPage("index.html")).indexOf(marker)<0)throw new Error("HTTP page not applied: "+name);
}
function dnsRecord(p,name,ip) {
    // Keep re-execution idempotent without removing unrelated records.
    p.removeIpAddress(name);p.addIpAddress(name,ip);
    if(ipv4(p.getIpAddOfDomain(name))!==ip)throw new Error("DNS record not applied: "+name);
}
function configureServices() {
    BUILD_STATE="SERVICES";
    page("SRV-MIS","Учебная МИС поликлиники № 8","CLINIC8_MIS_OK_"+RUN_TAG);
    page("SRV-FILE","Учебный архив исследований","CLINIC8_FILES_OK_"+RUN_TAG);
    page("PUBLIC-WEB","Внешний учебный ресурс","CLINIC8_PUBLIC_OK_"+RUN_TAG);
    var dns=process("SRV-MAIL","DnsServer");dns.setEnable(true);
    dnsRecord(dns,"mis.clinic8.test","10.1.30.10");dnsRecord(dns,"mail.clinic8.test","10.1.30.11");
    dnsRecord(dns,"files.clinic8.test","10.1.30.12");dnsRecord(dns,"www.example.test","203.0.113.10");
    var ext=process("PUBLIC-WEB","DnsServer");ext.setEnable(true);dnsRecord(ext,"www.example.test","203.0.113.10");
    var smtp=process("SRV-MAIL","SmtpServer"),pop=process("SRV-MAIL","Pop3Server"),accounts=process("SRV-MAIL","EmailServer");
    smtp.setServerDomainName("clinic8.test");smtp.setEnable(true);pop.setEnable(true);
    var ids=["c1","c2","b1","b2"];
    for(var a=0;a<ids.length;a++) {
        // addUser returns false for an existing account; changePassword is valid for both runs.
        accounts.addUser(ids[a],LAB_PASSWORD);accounts.changePassword(ids[a],LAB_PASSWORD);
        var pc=ids[a].toUpperCase()+"-PC01",user=process(pc,"EmailClient").getEmailUser();
        user.setName(ids[a]);user.setUser(ids[a]);user.setMailId(ids[a]+"@clinic8.test");
        user.setPassword(LAB_PASSWORD);user.setSmtpServer("10.1.30.11");user.setPop3Server("10.1.30.11");
    }
    if(!flag(smtp.isEnabled()) || !flag(pop.isEnabled()))throw new Error("Email services not enabled");
    report("HTTP, internal/external DNS, SMTP/POP3 and four mail clients configured.");
    later(waitDhcp,2000);
}
function pendingAddresses() {
    var out=[];
    for(var i=0;i<NODES.length;i++) {
        var n=NODES[i],wanted=n.guest_floor?"@WIFI":"@ETH";
        if(!n.guest_floor && (!n.endpoint || n.endpoint.type!=="pc"))continue;
        var site={C1:1,C2:2,B1:11,B2:12}[n.guest_floor || n.endpoint.floor];
        var vlan=n.guest_floor?90:n.endpoint.vlan;
        var ip=ipv4(port(n.name,wanted).object.getIpAddress());
        if(ip.indexOf("10."+site+"."+vlan+".")!==0)out.push(n.name+"="+ip);
    }
    return out;
}
function waitDhcp() {
    BUILD_STATE="DHCP_WAIT";var missing=pendingAddresses();
    if(missing.length===0){report("DHCP verified: all 84 workstations and four guest tablets have expected VLAN addresses.");startHttpTests();return;}
    DHCP_ATTEMPTS++;
    if(DHCP_ATTEMPTS>=30)throw new Error("DHCP not ready after 60 seconds: "+missing.slice(0,10).join(", "));
    report("Waiting for DHCP/STP/Wi-Fi: "+missing.length+" clients remain");later(waitDhcp,2000);
}
function startHttpTests() {
    BUILD_STATE="HTTP_TESTS";HTTP_TESTS=[];
    var sites=["C1","C2","B1","B2"];
    for(var i=0;i<sites.length;i++) {
        var s=sites[i];
        HTTP_TESTS.push({name:s+"-PC01",url:"http://mis.clinic8.test",marker:"CLINIC8_MIS_OK_"+RUN_TAG});
        HTTP_TESTS.push({name:s+"-GUEST",url:"http://www.example.test",marker:"CLINIC8_PUBLIC_OK_"+RUN_TAG});
    }
    runHttpTest(0);
}
function runHttpTest(index) {
    if(index>=HTTP_TESTS.length){startMailTests();return;}
    var t=HTTP_TESTS[index],http=process(t.name,"HttpClient");http.cancel();http.setHttps(false);http.go(t.url);
    later(function(){readHttpTest(index,0);},1000);
}
function readHttpTest(index,attempt) {
    var t=HTTP_TESTS[index],body=text(process(t.name,"HttpClient").getLastPageContent());
    if(body.indexOf(t.marker)>=0){report("PASS HTTP: "+t.name+" -> "+t.url);later(function(){runHttpTest(index+1);},10);return;}
    if(attempt>=14)throw new Error("HTTP response missing: "+t.name+" -> "+t.url+"; expected "+t.marker);
    later(function(){readHttpTest(index,attempt+1);},1000);
}
function startMailTests() {
    BUILD_STATE="EMAIL_TESTS";
    MAIL_TESTS=[{from:"b1",to:"c1",pc:"B1-PC01"},{from:"c2",to:"b2",pc:"C2-PC01"}];
    for(var i=0;i<MAIL_TESTS.length;i++) {
        var t=MAIL_TESTS[i];t.subject="CLINIC8_"+RUN_TAG+"_"+t.from;
        var ok=process(t.pc,"SmtpClient").sendMail(t.from+"@clinic8.test",t.to+"@clinic8.test",t.subject,"Учебное письмо поликлиники № 8",LAB_PASSWORD,"10.1.30.11");
        if(!flag(ok))throw new Error("SMTP request rejected: "+t.pc);
    }
    later(function(){readMailTests(0);},1000);
}
function readMailTests(attempt) {
    var server=process("SRV-MAIL","EmailServer"),pending=[];
    for(var i=0;i<MAIL_TESTS.length;i++) {
        var t=MAIL_TESTS[i],mails=server.getEmailUser(t.to).getMailBox().getMails(),found=false;
        for(var j=0;j<mails.length;j++) {
            var subject=typeof mails[j].getSubject==="function" ? mails[j].getSubject() : mails[j].subject;
            var content=typeof mails[j].getContent==="function" ? mails[j].getContent() : mails[j].content;
            if(text(subject)===t.subject && text(content).indexOf("поликлиники")>=0){found=true;break;}
        }
        if(!found)pending.push(t.from+" -> "+t.to);
    }
    if(pending.length) {
        if(attempt>=14)throw new Error("Email not delivered: "+pending.join(", "));
        later(function(){readMailTests(attempt+1);},1000);return;
    }
    report("PASS SMTP delivery: b1 -> c1 and c2 -> b2, current-run subjects present in recipient mailboxes.");
    for(var k=0;k<MAIL_TESTS.length;k++)process(MAIL_TESTS[k].to.toUpperCase()+"-PC01","Pop3Client").getMailIpc();
    later(function(){readPopTests(0);},1000);
}
function readPopTests(attempt) {
    var pending=[];
    for(var i=0;i<MAIL_TESTS.length;i++) {
        var t=MAIL_TESTS[i],user=process(t.to.toUpperCase()+"-PC01","EmailClient").getEmailUser();
        var mails=user.getMailBox().getMails(),found=false;
        for(var j=0;j<mails.length;j++) {
            var subject=typeof mails[j].getSubject==="function" ? mails[j].getSubject() : mails[j].subject;
            if(text(subject)===t.subject){found=true;break;}
        }
        if(!found)pending.push(t.to);
    }
    if(pending.length) {
        if(attempt>=14)throw new Error("POP3 receive not confirmed: "+pending.join(", "));
        later(function(){readPopTests(attempt+1);},1000);return;
    }
    report("PASS POP3: test messages present in receiving clients.");testGuestBlock(0);
}
function testGuestBlock(index) {
    BUILD_STATE="GUEST_ISOLATION";
    var sites=["C1","C2","B1","B2"];
    if(index>=sites.length){complete();return;}
    var s=sites[index],http=process(s+"-GUEST","HttpClient");http.cancel();http.go("http://10.1.30.10");
    later(function(){
        var body=text(http.getLastPageContent());http.cancel();
        if(body.indexOf("CLINIC8_MIS_OK_"+RUN_TAG)>=0)throw new Error("Guest isolation FAILED: "+s+" guest received internal MIS page");
        var result=command(dev("R-"+s),"R-"+s,"show access-lists GUEST-IN","enable");
        var output=text(typeof result.second!=="undefined" ? result.second : result[1]);
        if(output.toLowerCase().indexOf("deny ip any 10.0.0.0")<0)
            throw new Error("Guest deny ACL not present in running router configuration: "+s);
        report("PASS guest check: "+s+" external HTTP worked; internal HTTP had no MIS response within 15 s; deny ACL present.");
        testGuestBlock(index+1);
    },15000);
}
function complete() {
    BUILD_STATE="SAVING";
    var app=ipc.appWindow(),base=text(app.getDefaultFileSaveLocation());
    if(!base)base=text(app.getUserFolder());
    if(!base)throw new Error("Cannot determine a save folder. Network preserved; save manually as clinic8.pkt.");
    var sep=base.indexOf("\\")>=0 ? "\\" : "/";
    if(base.slice(-1)!=="/" && base.slice(-1)!=="\\")base+=sep;
    // A new timestamped filename avoids overwriting any pre-existing user file.
    SAVED_FILE=base+"clinic8-v3-"+RUN_TAG+".pkt";
    report("DONE: "+NODES.length+" project devices, "+WIRED+" cables. DHCP, HTTP, SMTP/POP3 and guest HTTP checks passed. Saving: "+SAVED_FILE);
    if(STATUS_NOTE){WORKSPACE.removeCanvasItem(STATUS_NOTE);STATUS_NOTE=null;}
    if(!flag(app.fileSaveAs(SAVED_FILE)))throw new Error("Packet Tracer did not confirm saving "+SAVED_FILE+". Network preserved.");
    BUILD_COMPLETE=true;BUILD_STATE="DONE";RUNNING=false;
    report("SAVED: "+SAVED_FILE);
    // Self-stop removed: destroying an executing Script Module is unsafe to assume.
}
function main() {
    if(!BUILDER_ENABLED){
        BUILD_STATE="WITHDRAWN";
        if(typeof dprint==="function")dprint("WITHDRAWN after a Packet Tracer crash. Do not run this builder; preserve your saved project for diagnosis.");
        return;
    }
    if(RUNNING)throw new Error("Builder already running");
    BUILD_COMPLETE=false;BUILD_STATE="STARTING";BUILD_REPORT=[];BUILD_ERRORS=[];
    CREATED=0;REUSED=0;WIRED=0;DHCP_ATTEMPTS=0;RUNNING=true;
    RUN_TAG=text(new Date().getTime());SAVED_FILE="";
    try {
        WORKSPACE=ipc.appWindow().getActiveWorkspace().getLogicalWorkspace();
        STATUS_NOTE=WORKSPACE.addNote(60,30,10,"Clinic8 v3: starting");
        report("Starting repeatable clinic network build");later(ensureDevices,10);
    }catch(e){fail(e);}
}
function cleanUp() {
    RUNNING=false;
    for(var i=0;i<TIMERS.length;i++)clearTimeout(TIMERS[i]);
    TIMERS=[]; // Existing devices, cables and configuration remain intact.
}
