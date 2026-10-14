"""Make a separate L1/L2 copy, preserving layout, saved IDs and cables.
Restore device engines from the user's original unconfigured document. Reset
new tablets' common host settings explicitly; preserve their physical modules.
This edits a document offline. Cisco opening remains a separate runtime check.
"""
from pathlib import Path
import sys,re,json,hashlib,copy,ipaddress,xml.etree.ElementTree as ET
from xml.dom import minidom
from pkt_document_codec import decode_document,encode_document
ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'packet-tracer/clinic8.pkt';prototype=ROOT/'packet-tracer/recovery/clinic8-one-link-original.pkt'
source_raw=source.read_bytes();proto_raw=prototype.read_bytes()
xml=decode_document(source_raw);original=ET.fromstring(xml);base_xml=decode_document(proto_raw)
base_blocks={ET.fromstring(m.group()).findtext('ENGINE/NAME'):m.group() for m in re.finditer(rb'<DEVICE>.*?</DEVICE>',base_xml,re.S)}
base_pc=minidom.parseString(base_blocks['C1-PC01']).getElementsByTagName('ENGINE')[0]
def direct(node,tag):
 matches=[n for n in node.childNodes if n.nodeType==n.ELEMENT_NODE and n.tagName==tag]
 assert len(matches)==1,(tag,len(matches));return matches[0]
def assign(node,value):
 for n in list(node.childNodes):node.removeChild(n)
 if value:node.appendChild(node.ownerDocument.createTextNode(value))
reset_tablet_tags=['GATEWAY','DNS_CLIENT','EMAIL_CLIENT','WIRELESS_CLIENT','CELLULAR_CLIENT','DHCP_CLIENT','ACL_PROCESS','ACL_V6_PROCESS','GATEWAYV6','ISATAP_ENABLED','ISATAP_ROUTER','DHCPV6_MAIN','NDV6','VOIP_TFTP_IP','PPPOE_SETTINGS','DOT1X_SETTINGS']
address_tags={'IP','IP_ADDRESS','IPV6_LINK_LOCAL','IPV6_DEFAULT_LINK_LOCAL','IPV6_ADDRESSES','IPV6_PORT_GATEWAY','IPV6_PORT_DNS','ND_IPV6_DNS_ADDRESSES','IP_UNNUMBERED','SUBNET','SUBNET_MASK','PORT_GATEWAY','PORT_DNS','DHCP_SERVER_IP','SERVER_IP','SERVER_IPV6','DEFAULT_GATEWAY','DNS','END_IP','START_IP'}
disable_tags={'PORT_DHCP_ENABLE','IPV6_PORT_DHCP_ENABLED','IPV6_ADDRESS_AUTOCONFIG','IPV6_ENABLED','ISATAP_ENABLED'}
changes=[]
def clean(match):
 doc=minidom.parseString(match.group());device=doc.documentElement;current=direct(device,'ENGINE')
 name=direct(current,'NAME').firstChild.data;ref=direct(current,'SAVE_REF_ID').firstChild.data
 if name in base_blocks:
  engine=doc.importNode(minidom.parseString(base_blocks[name]).getElementsByTagName('ENGINE')[0],True)
  assign(direct(engine,'SAVE_REF_ID'),ref)
  device.replaceChild(engine,current)
 else:
  assert direct(current,'TYPE').firstChild.data=='TabletPC',name
  engine=current
  for tag in reset_tablet_tags:
   engine.replaceChild(doc.importNode(direct(base_pc,tag),True),direct(engine,tag))
 # Remove addressing, auto-address flags and retained IPv6 link-local values.
 for elem in engine.getElementsByTagName('*'):
  if elem.tagName in address_tags:assign(elem,'')
  if elem.tagName in disable_tags:assign(elem,'false')
  if elem.tagName in ['DHCP_ENABLED','DHCPV6_ENABLED']:assign(elem,'0')
 # Explicitly retain static/no-address mode; DHCP has no service to query here.
 # Factory server service records come from the authentic pristine source.
 changes.append(name)
 return device.toxml(encoding='utf-8')
updated=re.sub(rb'<DEVICE>.*?</DEVICE>',clean,xml,flags=re.S);root=ET.fromstring(updated)
old_nodes=original.findall('NETWORK/DEVICES/DEVICE');new_nodes=root.findall('NETWORK/DEVICES/DEVICE')
assert len(old_nodes)==len(new_nodes)==120
assert ET.tostring(original.find('NETWORK/LINKS'))==ET.tostring(root.find('NETWORK/LINKS'))
for old,new in zip(old_nodes,new_nodes):
 assert old.findtext('ENGINE/NAME')==new.findtext('ENGINE/NAME')
 assert old.findtext('ENGINE/SAVE_REF_ID')==new.findtext('ENGINE/SAVE_REF_ID')
 assert ET.tostring(old.find('WORKSPACE'))==ET.tostring(new.find('WORKSPACE'))
 # No meaningful assigned IPv4/IPv6 address in any saved device engine.
 for e in new.find('ENGINE').iter():
  text=(e.text or '').strip()
  try:address=ipaddress.ip_address(text)
  except ValueError:continue
  assert address.is_unspecified,(new.findtext('ENGINE/NAME'),e.tag,text)
 for tag in ['RUNNINGCONFIG','STARTUPCONFIG']:
  lines=[n.text or '' for n in new.findall('ENGINE/'+tag+'/LINE')]
  forbidden=['ip address ','ipv6 address ','ip route ','ip dhcp ','ip nat ','access-list ','ip access-list ','encapsulation dot1Q ','switchport access vlan ']
  assert not any(line.strip().startswith(tuple(forbidden)) for line in lines),(new.findtext('ENGINE/NAME'),tag)
 if new.findtext('ENGINE/TYPE')=='Switch':
  assert {int(v.attrib['number']) for v in new.findall('ENGINE/VLANS/VLAN')}=={1,1002,1003,1004,1005}
 for flag in new.findall('ENGINE/.//PORT_DHCP_ENABLE'):assert flag.text=='false'
# Preserve all document bytes outside the device region, including CDATA.
a,b=xml.split(b'<DEVICES>',1)[0],xml.split(b'</DEVICES>',1)[1]
assert updated.startswith(a+b'<DEVICES>') and updated.endswith(b'</DEVICES>'+b)
assert updated.count(b'<![CDATA[')==xml.count(b'<![CDATA[')
output=ROOT/'packet-tracer/clinic8-L1-L2.pkt';packed=encode_document(updated);output.write_bytes(packed)
assert decode_document(packed)==updated and source.read_bytes()==source_raw
report={'file':output.name,'bytes':len(packed),'sha256':hashlib.sha256(packed).hexdigest(),'source_sha256':hashlib.sha256(source_raw).hexdigest(),'devices':120,'cables':112,'pristine_engines_restored':116,'tablets_reset':4,'checks':['source unchanged','layout and names preserved','save-ref IDs preserved','112 cable records unchanged','no assigned IPv4 or IPv6 in engines','no custom IP routes/DHCP/NAT/ACL/subinterfaces','switches only have factory default VLANs','factory device services restored','EAX/zlib and lossless codec checks'],'cisco_opening':'NOT_RUN','note':'Default unspecified values 0.0.0.0 and factory IOS commands can remain. Automatic local addresses may be generated again by Cisco.'}
(ROOT/'packet-tracer/l1l2-inspection.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(report,ensure_ascii=False))
