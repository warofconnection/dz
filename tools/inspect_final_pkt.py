"""Audit the user's saved Cisco document without executing it or its modules."""
from pathlib import Path
import sys,json,hashlib,collections,xml.etree.ElementTree as ET
from pkt_document_codec import decode_document
ROOT=Path(__file__).resolve().parents[1]
source=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'packet-tracer/clinic8.pkt'
raw=source.read_bytes();root=ET.fromstring(decode_document(raw));nodes=root.findall('NETWORK/DEVICES/DEVICE')
by_name={d.findtext('ENGINE/NAME'):d for d in nodes};assert len(by_name)==len(nodes)
refs={d.findtext('ENGINE/SAVE_REF_ID'):d for d in nodes};assert len(refs)==len(nodes)
assert root.findtext('VERSION')=='8.2.2.0400'
project=json.loads((ROOT/'docs/project-data.json').read_text())
assert {e['id'] for e in project['endpoints']} <= set(by_name)
cables=root.findall('NETWORK/LINKS/LINK');assert len(cables)==112
used=set()
for link in cables:
 c=link.find('CABLE');assert c is not None
 for side,index in [('FROM',0),('TO',1)]:
  ref=c.findtext(side);port=c.findall('PORT')[index].text
  assert ref in refs and (ref,port) not in used
  used.add((ref,port))
vlans={}
for name,d in by_name.items():
 if d.findtext('ENGINE/TYPE')=='Switch':
  expected={901,902,903} if name=='SW-PROVIDER' else {10,90,99}|({20} if name.startswith('SW-C') else set())|({30} if name.startswith('SW-C1') else set())
  present={int(v.attrib['number']) for v in d.findall('ENGINE/VLANS/VLAN')};assert expected <= present
  vlans[name]=sorted(present)
pc_dhcp=0;wireless=[];aps=[]
for name,d in by_name.items():
 typ=d.findtext('ENGINE/TYPE')
 if typ=='Pc':
  p=next(p for p in d.findall('ENGINE/.//PORT') if p.findtext('TYPE')=='eCopperFastEthernet');assert p.findtext('PORT_DHCP_ENABLE')=='true';pc_dhcp+=1
 if typ=='AccessPoint':
  wc=d.find('ENGINE/WIRELESS_SERVER/WIRELESS_COMMON');assert wc.findtext('AUTHEN_TYPE')=='4' and wc.findtext('ENCRYPT_TYPE')=='4'
  assert wc.findtext('SSID')=='Clinic8-'+name[:2]+'-Guest'
  aps.append({'name':name,'ssid':wc.findtext('SSID'),'wpa2_aes_saved':True})
 if typ=='TabletPC':
  p=next(p for p in d.findall('ENGINE/.//PORT') if p.findtext('TYPE')=='eHostWirelessN')
  wireless.append({'name':name,'ssid':d.findtext('ENGINE/WIRELESS_CLIENT/WIRELESS_COMMON/SSID'),'address_mode':'DHCP' if p.findtext('PORT_DHCP_ENABLE')=='true' else 'STATIC','saved_ip':p.findtext('IP') or None,'gateway':d.findtext('ENGINE/GATEWAY'),'dns':p.findtext('PORT_DNS')})
assert pc_dhcp==84 and len(wireless)==4 and len(aps)==4
report={'source_name':source.name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'version':root.findtext('VERSION'),'device_counts':dict(collections.Counter(d.findtext('ENGINE/TYPE') for d in nodes)),'device_count':len(nodes),'cable_count':len(cables),'unique_cable_endpoints':len(used),'vlans':vlans,'wired_pcs_with_dhcp_enabled':pc_dhcp,'access_points':aps,'tablets':wireless,'checks':['EAX/zlib integrity','unique device names and refs','112 cables resolve and have no repeated endpoint','all 99 project endpoints present','7 native VLAN databases contain project VLANs','84 wired PC DHCP flags enabled','4 AP SSIDs and WPA2/AES saved'],'pending':['C1 and B1 tablets save static mode; user must select DHCP on Wireless0','Actual Logical Workspace screenshot required','Reopened user tests reported successful after initial name resolution delay; not independently simulated in cloud','Some acceptance checks remain outside user-confirmed test scope']}
(ROOT/'packet-tracer/final-inspection.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps({'bytes':report['bytes'],'sha256':report['sha256'],'devices':len(nodes),'cables':len(cables),'tablet_modes':[(t['name'],t['address_mode']) for t in wireless]},ensure_ascii=False))
