"""Creates a documented-API script for execution inside authenticated Packet Tracer."""
from pathlib import Path
import json
R=Path(__file__).resolve().parents[1];d=json.loads((R/'docs/project-data.json').read_text());nodes=[];links=[]
for name,x,y in [('R-C1',300,500),('R-C2',300,950),('R-EDGE',800,250),('R-B1',1350,500),('R-B2',1350,950),('R-ISP',1100,100)]:nodes.append(dict(name=name,type=0,model='2911',x=x,y=y))
for name,x,y in [('SW-C1A',200,600),('SW-C1B',600,600),('SW-C2A',200,1050),('SW-C2B',600,1050),('SW-B1',1450,600),('SW-B2',1450,1050),('SW-PROVIDER',1100,250)]:nodes.append(dict(name=name,type=1,model='2960-24TT',x=x,y=y))
for floor,ox,oy in [('C1',70,710),('C2',70,1160),('B1',1150,710),('B2',1150,1160)]:
 ends=[e for e in d['endpoints'] if e['floor']==floor]
 for j,e in enumerate(ends):
  typ,model={'pc':(8,'PC-PT'),'printer':(10,'Printer-PT'),'ap':(7,'AccessPoint-PT'),'server':(9,'Server-PT')}[e['type']]
  nodes.append(dict(name=e['id'],type=typ,model=model,x=ox+j%10*88,y=oy+j//10*85,endpoint=e))
for p in d['ports']:links.append([p['device'],p['port'],p['endpoint'],'@ETH'])
links.extend([['R-C1','GigabitEthernet0/0','SW-C1A','GigabitEthernet0/1'],['SW-C1A','GigabitEthernet0/2','SW-C1B','GigabitEthernet0/1'],['R-C2','GigabitEthernet0/0','SW-C2A','GigabitEthernet0/1'],['SW-C2A','GigabitEthernet0/2','SW-C2B','GigabitEthernet0/1'],['R-C1','GigabitEthernet0/1','R-C2','GigabitEthernet0/1'],['R-C1','GigabitEthernet0/2','R-EDGE','GigabitEthernet0/0'],['R-EDGE','GigabitEthernet0/1','SW-PROVIDER','GigabitEthernet0/1'],['R-B1','GigabitEthernet0/1','SW-PROVIDER','FastEthernet0/1'],['R-B2','GigabitEthernet0/1','SW-PROVIDER','FastEthernet0/2'],['R-ISP','GigabitEthernet0/0','SW-PROVIDER','GigabitEthernet0/2'],['R-B1','GigabitEthernet0/0','SW-B1','GigabitEthernet0/1'],['R-B2','GigabitEthernet0/0','SW-B2','GigabitEthernet0/1'],['R-ISP','GigabitEthernet0/1','PUBLIC-WEB','@ETH']])
nodes.append(dict(name='PUBLIC-WEB',type=9,model='Server-PT',x=1450,y=100))
configs={p.stem:p.read_text().splitlines() for p in (R/'packet-tracer/configs').glob('*.txt')}
js='''// Packet Tracer 8.2.2 Script Engine, ECMAScript 5.\n// Execute only in a NEW EMPTY file, after normal Cisco authentication.\n// Prepared against the official IPC API supplied with 8.2.2; not runtime-verified.\n'''
js+='var NODES = '+json.dumps(nodes,ensure_ascii=False)+';\nvar LINKS = '+json.dumps(links)+';\nvar CONFIGS = '+json.dumps(configs)+';\n'
js+='''
function device(name) { return ipc.network().getDevice(name); }
function etherPort(name) {
    var p=device(name).getPorts();
    for(var i=0;i<p.length;i++) {
        var q=device(name).getPort(p[i]);
        if(q.isEthernetPort()) return p[i];
    }
    throw new Error("No Ethernet port: "+name);
}
function main() {
    if(ipc.network().getDeviceCount()!==0)
        throw new Error("Open a NEW EMPTY file first. Existing devices are preserved.");
    var ws=ipc.appWindow().getActiveWorkspace().getLogicalWorkspace();
    for(var i=0;i<NODES.length;i++) {
        var n=NODES[i],generated=ws.addDevice(n.type,n.model,n.x,n.y);
        if(!generated) throw new Error("Could not create "+n.name+" model "+n.model);
        device(generated).setName(n.name);
    }
    for(var j=0;j<LINKS.length;j++) {
        var l=LINKS[j],p1=l[1],p2=l[3];
        if(p1==="@ETH") p1=etherPort(l[0]);
        if(p2==="@ETH") p2=etherPort(l[2]);
        if(!ws.createLink(l[0],p1,l[2],p2,8107))
            throw new Error("Failed link: "+l.join(" / "));
    }
    ws.addNote(80,430,1,"Центральный корпус: C1 — регистратура, терапия, диагностика");
    ws.addNote(80,980,1,"C2 — врачи-специалисты, администрация, ИТ");
    ws.addNote(1170,430,1,"Филиал 1: регистратура, терапия, сестринская");
    ws.addNote(1170,980,1,"Филиал 2: регистратура, терапия, сестринская");
    ws.addNote(770,20,1,"Сеть оператора и внешний учебный ресурс");
    for(var k=0;k<NODES.length;k++) {
        var z=NODES[k];
        if(z.endpoint) ws.addNote(z.x-35,z.y+48,1,z.endpoint.department);
    }
    if(ipc.network().getDeviceCount()!==113)
        throw new Error("Unexpected device count after build; expected 113.");
    // Configure after construction; API exposes synchronous command status.
    for(var name in CONFIGS) if(CONFIGS.hasOwnProperty(name)) {
        var c=device(name);c.skipBoot();
        for(var t=0;t<CONFIGS[name].length;t++) {
            var line=CONFIGS[name][t];if(!line) continue;
            var result=c.enterCommand(line,"");
            // Inspect these statuses in Script Engine Debug on target PT.
            var state=result.first;
            if(typeof state === "number" && state!==0)
                throw new Error("IOS rejected "+name+": "+line+"; status "+state);
        }
    }
    for(var a=0;a<NODES.length;a++) {
        var e=NODES[a].endpoint;if(!e) continue;
        if(e.type==="pc") device(e.id).setDhcpFlag(true);
        if(e.type==="printer" || e.type==="server") {
            var site={C1:1,C2:2,B1:11,B2:12}[e.floor];
            var tail=e.type==="printer" ? (e.id.slice(-1)==="1"?20:21) :
                ({"SRV-MIS":10,"SRV-MAIL":11,"SRV-FILE":12}[e.id]);
            var port=device(e.id).getPort(etherPort(e.id));
            port.setIpSubnetMask("10."+site+"."+e.vlan+"."+tail,"255.255.255.0");
            port.setDefaultGateway("10."+site+"."+e.vlan+".1");
            port.setDnsServerIp("10.1.30.11");
        }
    }
    var publicPort=device("PUBLIC-WEB").getPort(etherPort("PUBLIC-WEB"));
    publicPort.setIpSubnetMask("203.0.113.10","255.255.255.0");
    publicPort.setDefaultGateway("203.0.113.1");
    publicPort.setDnsServerIp("203.0.113.10");
    ws.addNote(750,1450,1,"Сборка закончена. Требуются настройки HTTP/DNS/EMAIL/Wi-Fi и проверки по ASSEMBLY.md.");
}
function cleanUp() { /* Keep created network intact. */ }
'''
(R/'packet-tracer/build-clinic8.js').write_text(js)
print('Prepared script:',len(nodes),'devices,',len(links),'Ethernet links')
