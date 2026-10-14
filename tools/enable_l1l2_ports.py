"""Enable only cabled router Ethernet ports, without adding L3 settings.
Operate on saved documents, preserving all bytes outside edited DEVICE blocks.
Cisco opening and live link indicators must still be checked in Cisco.
"""
from pathlib import Path
from xml.dom import minidom
import xml.etree.ElementTree as E
import re,json,hashlib,ipaddress,copy
from pkt_document_codec import decode_document,encode_document
R=Path(__file__).resolve().parents[1]
source=R/'packet-tracer/clinic8-L1-L2-annotated.pkt';raw=source.read_bytes();xml=decode_document(raw);old=E.fromstring(xml)
connected={}
for link in old.findall('NETWORK/LINKS/LINK/CABLE'):
 ports=link.findall('PORT');assert len(ports)==2
 for tag,port in zip(['FROM','TO'],ports):connected.setdefault(link.findtext(tag),set()).add(port.text)
changes=[]
def direct(n,tag):return [x for x in n.childNodes if x.nodeType==x.ELEMENT_NODE and x.tagName==tag]
def value(n):return ''.join(x.data for x in n.childNodes if x.nodeType in [x.TEXT_NODE,x.CDATA_SECTION_NODE])
def setvalue(n,s):
 for c in list(n.childNodes):n.removeChild(c)
 n.appendChild(n.ownerDocument.createTextNode(s))
def edit(match):
 doc=minidom.parseString(match.group());engine=direct(doc.documentElement,'ENGINE')[0]
 if value(direct(engine,'TYPE')[0])!='Router':return match.group()
 name=value(direct(engine,'NAME')[0]);ref=value(direct(engine,'SAVE_REF_ID')[0]);ports=connected.get(ref,set())
 assert all(re.fullmatch('GigabitEthernet0/[0-2]',p) for p in ports),(name,ports)
 module=direct(engine,'MODULE')[0];physical=[p for p in module.getElementsByTagName('PORT') if value(direct(p,'TYPE')[0])=='eCopperGigabitEthernet'];assert len(physical)==3
 enabled=[]
 for i,p in enumerate(physical):
  interface=f'GigabitEthernet0/{i}'
  if interface not in ports:continue
  power=direct(p,'POWER')[0]
  if value(power)=='false':setvalue(power,'true');enabled.append(interface)
 run=direct(engine,'RUNNINGCONFIG')[0];current=None;removed=[]
 for line in list(direct(run,'LINE')):
  s=value(line).strip()
  if s.startswith('interface '):current=s.split(' ',1)[1]
  elif s=='!':current=None
  if current in ports and s=='shutdown':run.removeChild(line);removed.append(current)
 assert set(removed)==set(enabled),(name,removed,enabled)
 # Saving the physical enablement in startup config prevents a later power cycle
 # from bringing the connected ports back to the factory shutdown state.
 startup=direct(engine,'STARTUPCONFIG')[0]
 for c in list(startup.childNodes):startup.removeChild(c)
 for c in run.childNodes:startup.appendChild(c.cloneNode(True))
 changes.append({'device':name,'enabled':sorted(enabled),'unused_ports_left_disabled':[f'GigabitEthernet0/{i}' for i in range(3) if f'GigabitEthernet0/{i}' not in ports]})
 return doc.documentElement.toxml(encoding='utf-8')
updated=re.sub(rb'<DEVICE>.*?</DEVICE>',edit,xml,flags=re.S);new=E.fromstring(updated)
assert len(changes)==6 and sum(len(c['enabled']) for c in changes)==13, changes
assert source.read_bytes()==raw
for path in ['NETWORK/LINKS','RECTANGLES','PHYSICALWORKSPACE','CLUSTERS']:
 assert E.tostring(old.find(path))==E.tostring(new.find(path)),path
before=old.findall('NETWORK/DEVICES/DEVICE');after=new.findall('NETWORK/DEVICES/DEVICE');assert len(before)==len(after)==120
for a,b in zip(before,after):
 assert a.findtext('ENGINE/NAME')==b.findtext('ENGINE/NAME')
 assert E.tostring(a.find('WORKSPACE'))==E.tostring(b.find('WORKSPACE'))
 for node in b.find('ENGINE').iter():
  try:addr=ipaddress.ip_address((node.text or '').strip())
  except ValueError:continue
  assert addr.is_unspecified,(b.findtext('ENGINE/NAME'),node.tag,str(addr))
 for cfg in ['RUNNINGCONFIG','STARTUPCONFIG']:
  forbidden=('ip address ','ipv6 address ','ip route ','ipv6 route ','ip dhcp ','ip nat ','access-list ','ip access-list ','encapsulation dot1Q ','switchport access vlan ')
  assert not any((l.text or '').strip().startswith(forbidden) for l in b.findall('ENGINE/'+cfg+'/LINE'))
 # Exact XML equality after reverting the authorized port and config edits.
 restored=copy.deepcopy(b)
 if a.findtext('ENGINE/TYPE')=='Router':
  for tag in ['RUNNINGCONFIG','STARTUPCONFIG']:
   dest=restored.find('ENGINE/'+tag);src=a.find('ENGINE/'+tag)
   dest.clear();dest.attrib.update(src.attrib);dest.text=src.text;dest.tail=src.tail
   for c in src:dest.append(copy.deepcopy(c))
  for pa,pb in zip(a.findall('ENGINE/MODULE/.//PORT'),restored.findall('ENGINE/MODULE/.//PORT')):pb.find('POWER').text=pa.findtext('POWER')
 assert E.tostring(a)==E.tostring(restored),a.findtext('ENGINE/NAME')
output=R/'packet-tracer/clinic8-L1-L2-ready.pkt';output.write_bytes(encode_document(updated))
report={'file':output.name,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'source_sha256':hashlib.sha256(raw).hexdigest(),'devices':120,'cables':112,'router_ports_enabled':sum(len(c['enabled']) for c in changes),'changes':changes,'checks':['cables/layout/annotations unchanged','no assigned IPv4/IPv6','no custom routing/DHCP/NAT/ACL/VLAN','only connected router ports enabled','persistent startup config','no other device changes','lossless authenticated container round trip'],'cisco_opening':'NOT_RUN'}
(R/'packet-tracer/ports-enabled-inspection.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False))
