from pathlib import Path
import zipfile
ROOT=Path(__file__).resolve().parents[1]
files={
 'Презентация_вариант_8.pptx':'docs/Презентация_вариант_8.pptx',
 'Презентация_вариант_8.pdf':'docs/Презентация_вариант_8.pdf',
 'Расчёты_вариант_8.docx':'docs/Расчёты_вариант_8.docx',
 'clinic8-L1-L2.pkt':'packet-tracer/clinic8-L1-L2-ready.pkt',
 'Схемы/общий-вид-Cisco.png':'diagrams/packet-tracer-l1l2.png',
 'Схемы/связи-площадок.png':'diagrams/logical-draft.png',
 **{'Схемы/'+name+'.png':'diagrams/'+name+'.png' for name in ['floor-C1','floor-C2','floor-B1','floor-B2','site','org']}}
folder=ROOT/'deliverables';folder.mkdir(exist_ok=True);archive=folder/'ИТС_ДЗ1_Вариант8_L1-L2.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
 for name,source in files.items():z.write(ROOT/source,name)
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for name,source in files.items():assert z.read(name)==(ROOT/source).read_bytes()
print('Package:',archive.name,'files',len(files),'bytes',archive.stat().st_size)
