"""Prepare a wiring candidate by inserting XML only into the original LINKS.
Preserves all source document bytes outside that insertion, including CDATA.
Opening in Cisco still requires runtime verification.
"""
from pathlib import Path
import sys,json,re,copy,xml.etree.ElementTree as ET,hashlib
from pkt_document_codec import decode_document,encode_document
ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'packet-tracer/recovery/clinic8-one-link-original.pkt'
raw=source.read_bytes();xml=decode_document(raw);original=ET.fromstring(xml)
# Reproduction of the exact user's container verifies the encoder independently
# of its ability to decode its own output.
assert encode_document(xml)==raw
failed=ET.fromstring(decode_document((ROOT/'packet-tracer/native/clinic8-wired.pkt').read_bytes()))
original_links=original.find('NETWORK/LINKS');candidate_links=failed.find('NETWORK/LINKS')
assert len(original_links)==1 and len(candidate_links)==112
by_ref={d.findtext('ENGINE/SAVE_REF_ID'):d for d in original.findall('NETWORK/DEVICES/DEVICE')}
fixed_ap_ports=[]
for link in list(candidate_links)[1:]:
 c=link.find('CABLE')
 for side,index in [('FROM',0),('TO',1)]:
  d=by_ref[c.findtext(side)]
  if d.findtext('ENGINE/TYPE')=='AccessPoint':
   old=c.findall('PORT')[index].text
   assert old=='FastEthernet0'
   c.findall('PORT')[index].text='Port 0'
   fixed_ap_ports.append(d.findtext('ENGINE/NAME'))
assert len(fixed_ap_ports)==4
pattern=rb'(<LINKS>)(.*?)(</LINKS>)'
regions=list(re.finditer(pattern,xml,re.S));assert len(regions)==1
region=regions[0]
addition=b''.join(ET.tostring(link,encoding='utf-8') for link in list(candidate_links)[1:])
# Insert at the closing tag without serializing any original element.
changed=xml[:region.start(3)]+addition+xml[region.start(3):]
assert changed[:region.start(3)]==xml[:region.start(3)]
assert changed[region.start(3)+len(addition):]==xml[region.start(3):]
assert changed.count(b'<![CDATA[')==xml.count(b'<![CDATA[')==6
parsed=ET.fromstring(changed)
assert len(parsed.find('NETWORK/LINKS'))==112
assert ET.tostring(parsed.find('NETWORK/DEVICES'))==ET.tostring(original.find('NETWORK/DEVICES'))
assert ET.tostring(parsed.find('SCRIPT_MODULE'))==ET.tostring(original.find('SCRIPT_MODULE'))
packed=encode_document(changed);assert decode_document(packed)==changed
out=ROOT/'packet-tracer/native/clinic8-wired-preserved.pkt';out.write_bytes(packed)
report={'file':out.name,'bytes':len(packed),'sha256':hashlib.sha256(packed).hexdigest(),'version':parsed.findtext('VERSION'),'device_count':len(parsed.findall('NETWORK/DEVICES/DEVICE')),'cable_count':112,'original_xml_outside_insertion':'BYTE_IDENTICAL','source_container_reproduction':'BYTE_IDENTICAL','original_cdata_blocks_preserved':6,'runtime':'NOT_RUN','prior_candidate_runtime':'OPEN_FAILED_USER','invalid_ap_port_names_corrected':fixed_ap_ports,'opening_failure_cause':'INVALID_AP_PORT_NAMES_FOUND; runtime confirmation pending','limitations':['Inserted cable records still require Cisco runtime verification','IP/VLAN/services not configured']}
(ROOT/'packet-tracer/native/preserved-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
assert source.read_bytes()==raw
print(json.dumps(report,ensure_ascii=False))
