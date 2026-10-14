"""Add physical project labels using Packet Tracer's native drawing schema.
Preserve all device engines and cables. Opening the annotated copy is a separate
Cisco runtime check; codec integrity is not a runtime compatibility claim.
"""
from pathlib import Path
import re,uuid,hashlib,json,xml.etree.ElementTree as E
from pkt_document_codec import decode_document,encode_document
R=Path(__file__).resolve().parents[1]
source=R/'packet-tracer/clinic8-L1-L2.pkt';xml=decode_document(source.read_bytes());old=E.fromstring(xml)
rects=E.Element('RECTANGLES');notes=E.Element('NOTES')
zones=[(20,470,1010,945,(225,239,255),'ЦЕНТРАЛЬНЫЙ КОРПУС • ЭТАЖ 1 | 24 ПК • регистратура, терапия, диагностика'),(20,945,1010,1450,(225,245,237),'ЦЕНТРАЛЬНЫЙ КОРПУС • ЭТАЖ 2 | 24 ПК • специалисты, администрация, ИТ'),(1070,470,2010,945,(255,243,221),'ФИЛИАЛ 1 | 18 ПК • регистратура, терапия, сестринская'),(1070,945,2010,1450,(242,231,253),'ФИЛИАЛ 2 | 18 ПК • регистратура, терапия, сестринская'),(760,30,1570,465,(239,241,245),'СЕТЬ ОПЕРАТОРА • внешние ресурсы | оборудование вне сметы')]
def child(parent,tag,value):E.SubElement(parent,tag).text=str(value)
for i,(x1,y1,x2,y2,color,title) in enumerate(zones):
 r=E.SubElement(rects,'RECTANGLE',uuid='{'+str(uuid.uuid4())+'}')
 for tag,v in [('TopLeftX',x1),('TopLeftY',y1),('BottomRightX',x2),('BottomRightY',y2)]:child(r,tag,v)
 c=E.SubElement(r,'Color')
 for tag,v in zip(['Red','Green','Blue'],color):child(c,tag,v)
 E.SubElement(r,'Filled',OUTLINECOLOR='#176dea',OUTLINED='true').text='1'
 child(r,'RECTCLUSTERID','1-1');child(r,'MEM_ADDR',910000000+i)
 n=E.SubElement(notes,'NOTE',uuid='{'+str(uuid.uuid4())+'}')
 for tag,v in [('X',x1+15),('Y',y1+(45 if y1==945 else 8)),('Z',40000+i),('TEXT',title),('NOTECLUSTERID','1-1'),('MEM_ADDR',920000000+i)]:child(n,tag,v)
# Native NOTE records are stored under PHYSICALWORKSPACE/NOTES and refer to
# the logical root by NOTECLUSTERID, as in Cisco's bundled sample documents.
assert old.find('RECTANGLES') is not None and old.find('PHYSICALWORKSPACE/NOTES') is not None
assert not list(old.find('RECTANGLES')) and not list(old.find('PHYSICALWORKSPACE/NOTES'))
xml=re.sub(rb'<RECTANGLES\s*/>',E.tostring(rects),xml,count=1)
# Restrict NOTES replacement to the physical workspace region.
a=xml.index(b'<PHYSICALWORKSPACE>');b=xml.index(b'</PHYSICALWORKSPACE>',a)
part=xml[a:b];part,count=re.subn(rb'<NOTES\s*/>',E.tostring(notes),part,count=1);assert count==1
xml=xml[:a]+part+xml[b:];new=E.fromstring(xml)
for tag in ['NETWORK','CLUSTERS']:
 assert E.tostring(old.find(tag))==E.tostring(new.find(tag))
assert len(new.findall('RECTANGLES/RECTANGLE'))==5
assert len(new.findall('PHYSICALWORKSPACE/NOTES/NOTE'))==5
out=R/'packet-tracer/clinic8-L1-L2-annotated.pkt';out.write_bytes(encode_document(xml))
(R/'packet-tracer/annotated-inspection.json').write_text(json.dumps({'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'annotated_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'network_unchanged':True,'background_zones':5,'labels':5,'cisco_opening':'NOT_RUN'},indent=2))
print(out.name,out.stat().st_size)
