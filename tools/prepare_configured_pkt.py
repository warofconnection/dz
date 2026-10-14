"""Prepare next-stage settings in the user-opened native wiring document.
No Script Modules; changes only selected DEVICE records, preserving CDATA and
all cable/global records. Simulator behavior still requires user verification.
"""
from pathlib import Path
import json,re,xml.etree.ElementTree as ET
from xml.dom import minidom
from pkt_document_codec import decode_document,encode_document
ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'packet-tracer/native/clinic8-wired-preserved.pkt'
raw=source.read_bytes();xml=decode_document(raw)
project=json.loads((ROOT/'docs/project-data.json').read_text())
endpoints={e['id']:e for e in project['endpoints']}
configs={p.stem:p.read_text().splitlines() for p in (ROOT/'packet-tracer/configs').glob('*.txt')}
site={'C1':1,'C2':2,'B1':11,'B2':12}
server_ips={'SRV-MIS':'10.1.30.10','SRV-MAIL':'10.1.30.11','SRV-FILE':'10.1.30.12','PUBLIC-WEB':'203.0.113.10'}
dns_records={'mis.clinic8.test':'10.1.30.10','mail.clinic8.test':'10.1.30.11','files.clinic8.test':'10.1.30.12','www.example.test':'203.0.113.10'}
lab_password='Clinic8Lab2026' # Synthetic password used ONLY by simulated email accounts.
changed=[];dhcp=[];static=[];clients=[]
def child(node,tag):
 matches=[n for n in node.childNodes if n.nodeType==n.ELEMENT_NODE and n.tagName==tag]
 assert len(matches)==1,(node.tagName,tag,len(matches))
 return matches[0]
def empty(node):
 for n in list(node.childNodes):node.removeChild(n)
def text(node,value):empty(node);node.appendChild(node.ownerDocument.createTextNode(str(value)))
def leaf(node,tag,value):text(child(node,tag),value)
def add(node,tag,value=None):
 n=node.ownerDocument.createElement(tag);node.appendChild(n)
 if value is not None:text(n,value)
 return n
def edit(match):
 block=match.group();doc=minidom.parseString(block);device=doc.documentElement;e=child(device,'ENGINE');name=child(e,'NAME').firstChild.data
 if name in configs:
  prev=child(e,'RUNNINGCONFIG');version=next((n.firstChild.data for n in prev.childNodes if n.nodeType==n.ELEMENT_NODE and n.firstChild and n.firstChild.data.startswith('version ')),None)
  lines=[l for l in configs[name] if l and l not in ['enable','configure terminal','end','write memory']]
  lines=['!']+([version] if version else [])+lines+['!','end']
  for tag in ['RUNNINGCONFIG','STARTUPCONFIG']:
   node=child(e,tag);empty(node)
   for line in lines:add(node,'LINE',line)
 elif name in endpoints or name=='PUBLIC-WEB':
  ep=endpoints.get(name)
  if ep and ep['type']=='ap':
   wc=child(child(e,'WIRELESS_SERVER'),'WIRELESS_COMMON');leaf(wc,'SSID','Clinic8-'+ep['floor']+'-Guest')
  else:
   ports=[p for p in e.getElementsByTagName('PORT') if any(n.nodeType==n.ELEMENT_NODE and n.tagName=='IP' for n in p.childNodes)]
   ports=[p for p in ports if child(p,'TYPE').firstChild.data=='eCopperFastEthernet']
   assert len(ports)==1,(name,len(ports));p=ports[0]
   if ep and ep['type']=='pc':
    leaf(p,'PORT_DHCP_ENABLE','true')
    for tag in ['IP','SUBNET','PORT_GATEWAY','PORT_DNS']:leaf(p,tag,'')
    entries=child(child(e,'DHCP_CLIENT'),'PORT_DATA_MAP');empty(entries);add(add(entries,'PORT_DATA_ENTRY'),'PORT','FastEthernet0');dhcp.append(name)
   else:
    if name in server_ips:
     ip=server_ips[name];gateway='203.0.113.1' if name=='PUBLIC-WEB' else '10.1.30.1';dns='203.0.113.10' if name=='PUBLIC-WEB' else '10.1.30.11'
    else:
     assert ep['type']=='printer',ep
     floor=ep['floor'];number=int(re.search(r'(\d+)$',name).group(1));ip=f'10.{site[floor]}.10.{19+number}';gateway=f'10.{site[floor]}.10.1';dns='10.1.30.11'
    for tag,val in [('IP',ip),('SUBNET','255.255.255.0'),('PORT_GATEWAY',gateway),('PORT_DNS',dns),('PORT_DHCP_ENABLE','false')]:leaf(p,tag,val)
    leaf(e,'GATEWAY',gateway);leaf(child(e,'DNS_CLIENT'),'SERVER_IP',dns);static.append({'name':name,'ip':ip})
   if name in ['SRV-MAIL','PUBLIC-WEB']:
    server=child(e,'DNS_SERVER');leaf(server,'ENABLED',1);db=child(server,'NAMESERVER-DATABASE');empty(db)
    records=dns_records if name=='SRV-MAIL' else {'www.example.test':'203.0.113.10'}
    for host,ip in records.items():
     entry=add(db,'RESOURCE-RECORD')
     for tag,val in [('TYPE','A-REC'),('NAME',host),('TTL',86400),('IPADDRESS',ip)]:add(entry,tag,val)
   if name=='SRV-MAIL':
    server=child(e,'EMAIL_SERVER');leaf(server,'SMTP_ENABLED',1);leaf(server,'POP3_ENABLED',1);leaf(server,'SMTP_DOMAIN','clinic8.test');leaf(server,'NO_OF_USERS',4)
    for i,user in enumerate(['c1','c2','b1','b2']):
     add(server,'USER'+str(i),user);add(server,'PASSWORD'+str(i),lab_password);add(server,'NO_OF_MAILS'+str(i),0)
   if name in ['SRV-MIS','SRV-FILE','PUBLIC-WEB']:
    title={'SRV-MIS':'Clinic 8: Medical Information System','SRV-FILE':'Clinic 8: Research Archive','PUBLIC-WEB':'External educational website'}[name]
    html='<html><head><title>'+title+'</title></head><body><h1>'+title+'</h1><p>Educational network, variant 8.</p></body></html>'
    # Both filesystem landing page and index.html retain their original types.
    for f in e.getElementsByTagName('FILE'):
     ns=[n for n in f.childNodes if n.nodeType==n.ELEMENT_NODE and n.tagName=='NAME']
     if ns and ns[0].firstChild and ns[0].firstChild.data in ['http:','index.html']:
      content=child(f,'FILE_CONTENT');assert content.getAttribute('class')=='CHttpPage';leaf(content,'TEXT',html)
   if name in ['C1-PC01','C2-PC01','B1-PC01','B2-PC01']:
    user=name[:2].lower();client=child(e,'EMAIL_CLIENT')
    for tag,val in [('ENABLED',1),('NAME',user),('MAIL_ID',user+'@clinic8.test'),('POP3_SERVER','10.1.30.11'),('SMTP_SERVER','10.1.30.11'),('USER',user),('PASSWORD',lab_password)]:leaf(client,tag,val)
    clients.append(name)
 else:return block
 changed.append(name);return device.toxml(encoding='utf-8')
pattern=rb'<DEVICE>.*?</DEVICE>'
assert len(list(re.finditer(pattern,xml,re.S)))==116
updated=re.sub(pattern,edit,xml,flags=re.S)
a=ET.fromstring(xml);b=ET.fromstring(updated)
for tag in ['LINKS']:
 assert ET.tostring(a.find('NETWORK/'+tag))==ET.tostring(b.find('NETWORK/'+tag))
# All bytes before/after the NETWORK/DEVICES region are preserved, including built-in modules.
for payload in [xml,updated]:assert payload.count(b'<![CDATA[')==6
prefix,suffix=xml.split(b'<DEVICES>',1)[0],xml.split(b'</DEVICES>',1)[1]
assert updated.startswith(prefix+b'<DEVICES>') and updated.endswith(b'</DEVICES>'+suffix)
assert len(dhcp)==84 and len(static)==12 and len(configs)==13 and len(clients)==4
assert len({x['ip'] for x in static})==12
packed=encode_document(updated);out=ROOT/'packet-tracer/native/clinic8-configured.pkt';out.write_bytes(packed)
report={'source_opening':'PASS_USER','cable_count':112,'ios_devices':sorted(configs),'dhcp_pcs':len(dhcp),'static_hosts':static,'email_clients':clients,'dns_records':dns_records,'file_opening':'NOT_RUN','functional_tests':'NOT_RUN','pending':['Cisco must apply saved IOS config and DHCP at load; verify in CLI','Wi-Fi security and guest test tablets still require setup','End-to-end connectivity, HTTP, mail, NAT and guest ACL require real tests']}
(ROOT/'packet-tracer/native/configured-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
assert source.read_bytes()==raw
print('Prepared',out.name,'bytes',len(packed),'devices changed',len(changed),'DHCP PCs',len(dhcp),'static hosts',len(static))
