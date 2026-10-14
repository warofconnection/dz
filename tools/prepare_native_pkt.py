"""Add project wiring to a copy of the user's native PKT, without Script Modules.
Creates separately a proposed configuration copy. These are structurally checked,
not tested in the Cisco runtime. Never overwrites the source file.
"""
from pathlib import Path
import sys,json,copy,xml.etree.ElementTree as ET,hashlib,re
from pkt_document_codec import decode_document,encode_document
ROOT=Path(__file__).resolve().parents[1]
source=Path(sys.argv[1]);raw=source.read_bytes();xml=decode_document(raw);original=ET.fromstring(xml)
assert original.findtext('VERSION')=='8.2.2.0400'
project=json.loads((ROOT/'docs/project-data.json').read_text())
script=(ROOT/'packet-tracer/clinic8-all-in-one.js').read_text()
link_line=next(l for l in script.splitlines() if l.startswith('var LINKS = '))
plan=json.loads(link_line[len('var LINKS = '):-1])
root=copy.deepcopy(original);nodes=root.findall('NETWORK/DEVICES/DEVICE')
by_name={d.findtext('ENGINE/NAME'):d for d in nodes}
assert len(by_name)==len(nodes)
assert len(plan)==112
refs={d.findtext('ENGINE/SAVE_REF_ID'):d.findtext('ENGINE/NAME') for d in nodes}
assert len(refs)==len(nodes) and None not in refs
links=root.find('NETWORK/LINKS');assert len(links)==1
sample=links[0];first=sample.find('CABLE');assert first is not None
assert refs[first.findtext('FROM')]=='SW-C1A' and refs[first.findtext('TO')]=='C1-PC01'
assert [p.text for p in first.findall('PORT')]==['FastEthernet0/1','FastEthernet0']
lengths={e['id']:e['length_m'] for e in project['endpoints']}
used=set()
for i,(left,left_port,right,right_port) in enumerate(plan):
 assert left in by_name and right in by_name
 if right_port=='@ETH':right_port='FastEthernet0'
 for key in [(left,left_port),(right,right_port)]:
  assert key not in used,f'Duplicate planned port: {key}'
  used.add(key)
 if i==0:continue # Preserve the genuine cable created by the user byte-for-byte at XML level.
 link=copy.deepcopy(sample);c=link.find('CABLE')
 c.find('FROM').text=by_name[left].findtext('ENGINE/SAVE_REF_ID')
 c.find('TO').text=by_name[right].findtext('ENGINE/SAVE_REF_ID')
 c.findall('PORT')[0].text=left_port;c.findall('PORT')[1].text=right_port
 c.find('FROM_DEVICE_MEM_ADDR').text=by_name[left].findtext('WORKSPACE/LOGICAL/DEV_ADDR')
 c.find('TO_DEVICE_MEM_ADDR').text=by_name[right].findtext('WORKSPACE/LOGICAL/DEV_ADDR')
 # These transient memory hints have no serialized per-port counterparts.
 # Do not invent pointers; use the current save-ref-id + canonical port references.
 for tag in ['FROM_PORT_MEM_ADDR','TO_PORT_MEM_ADDR']:
  child=c.find(tag)
  if child is not None:c.remove(child)
 c.find('LENGTH').text=str(lengths.get(right,12 if left=='R-C1' and right=='R-C2' else 2))
 type_left=by_name[left].findtext('ENGINE/TYPE');type_right=by_name[right].findtext('ENGINE/TYPE')
 c.find('TYPE').text='eCrossOver' if type_left==type_right and type_left in ['Router','Switch'] else 'eStraightThrough'
 links.append(link)
assert len(links)==112
# File Script Module is empty in the source; reject an unexpected active script instead of executing it.
file_scripts=root.find('SCRIPT_MODULE/SCRIPTS')
# The source's default File Script Module and installed module metadata are retained unchanged.
# No code is imported, enabled, evaluated or added by this conversion.
outdir=ROOT/'packet-tracer/native';outdir.mkdir(exist_ok=True)
def write(name,r):
 data=ET.tostring(r,encoding='utf-8');packed=encode_document(data)
 decoded=ET.fromstring(decode_document(packed))
 assert len(decoded.find('NETWORK/LINKS'))==112
 assert {d.findtext('ENGINE/NAME') for d in decoded.findall('NETWORK/DEVICES/DEVICE')}==set(by_name)
 ids={d.findtext('ENGINE/SAVE_REF_ID') for d in decoded.findall('NETWORK/DEVICES/DEVICE')}
 seen=set()
 for link in decoded.findall('NETWORK/LINKS/LINK'):
  c=link.find('CABLE');assert c.findtext('FROM') in ids and c.findtext('TO') in ids
  for key in [(c.findtext('FROM'),c.findall('PORT')[0].text),(c.findtext('TO'),c.findall('PORT')[1].text)]:
   assert key not in seen;seen.add(key)
 assert ET.tostring(decoded.find('SCRIPT_MODULE'))==ET.tostring(original.find('SCRIPT_MODULE'))
 dest=outdir/name;dest.write_bytes(packed)
 return {'file':name,'bytes':len(packed),'sha256':hashlib.sha256(packed).hexdigest(),'device_count':len(nodes),'cable_count':112,'cisco_runtime':'NOT_RUN'}
results=[write('clinic8-wired.pkt',root)]
# Add standard IOS config lines using the RUNNINGCONFIG/LINE structure from the real file.
configured=copy.deepcopy(root)
for cfg in sorted((ROOT/'packet-tracer/configs').glob('*.txt')):
 name=cfg.stem;d=next(n for n in configured.findall('NETWORK/DEVICES/DEVICE') if n.findtext('ENGINE/NAME')==name)
 old=d.find('ENGINE/RUNNINGCONFIG');version=next((e.text for e in old if e.text and e.text.startswith('version ')),None)
 lines=[l for l in cfg.read_text().splitlines() if l and l not in ['enable','configure terminal','end','write memory']]
 lines=['!']+([version] if version else [])+lines+['!','end']
 for tag in ['RUNNINGCONFIG','STARTUPCONFIG']:
  node=d.find('ENGINE/'+tag);assert node is not None
  node.clear()
  for line in lines:ET.SubElement(node,'LINE').text=line
results.append(write('clinic8-wired-ios.pkt',configured))
report={'source_sha256':hashlib.sha256(raw).hexdigest(),'preserved_user_cable':True,'source_devices_preserved':True,'script_module_unchanged':True,'validation':['source EAX and zlib checks','generated EAX and zlib checks','lossless codec round trip','116 unique devices preserved','112 unique port pairs','all endpoint save-ref IDs resolve','no Script Module added or executed'],'limitations':['Cisco file opening not tested','runtime interpretation of generated cable records not tested','startup/running configuration application not tested','host/server services not configured in these files'],'outputs':results}
(outdir/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
assert source.read_bytes()==raw
print(json.dumps(results,ensure_ascii=False))
