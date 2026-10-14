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
# Four guest tablets represent the Wi-Fi segment and are excluded from the clinic purchase count.
for floor in ['C1','C2','B1','B2']:
 ap=next(n for n in nodes if n['name']==f'{floor}-AP1')
 nodes.append(dict(name=f'{floor}-GUEST',type=19,model='TabletPC-PT',x=ap['x']+60,y=ap['y']+70,guest_floor=floor))
header='// Clinic8 v3. Run inside authenticated Packet Tracer 8.2.2.\n'
header+='// Uses documented IPC API; never deletes existing devices or cables.\n'
header+='var NODES = '+json.dumps(nodes,ensure_ascii=False)+';\n'
header+='var LINKS = '+json.dumps(links)+';\n'
header+='var CONFIGS = '+json.dumps(configs)+';\n'
body=(R/'tools/cisco_runtime.js').read_text()
for name in ['clinic8-all-in-one.js','build-clinic8.js','finish-clinic8.js']:
 (R/'packet-tracer'/name).write_text(header+body)
print('Unified v3 script:',len(nodes),'devices;',len(links),'wired links; 4 wireless guests')
