"""Проверка согласованности артефактов; не симуляция Cisco."""
from pathlib import Path
from collections import Counter
import json, math, zipfile
from docx import Document
from pptx import Presentation
R=Path(__file__).resolve().parents[1]
a=json.loads((R/'docs/project-data.json').read_text());e=a['endpoints'];p=a['ports']
assert len(e)==99 and len(p)==99
assert Counter(x['type'] for x in e)=={'pc':84,'printer':8,'ap':4,'server':3}
assert len({x['id'] for x in e})==99
assert {x['id'] for x in e}=={x['endpoint'] for x in p}
assert len({(x['device'],x['port']) for x in p})==99
assert max(x['length_m'] for x in e)<=90
assert math.isclose(a['copper_m'],sum(x['length_m'] for x in e))
assert a['spools']*305>=a['copper_m']*1.2
assert a['total_rub']==sum(x[2]*x[3] for x in a['equipment'])
vl={x['id']:x['vlan'] for x in e}
for x in p:
 assert int(x['port'].split('/')[-1])<=24
 assert vl[x['endpoint']]==x['vlan']
 cfg=(R/'packet-tracer/configs'/f'{x["device"]}.txt').read_text()
 assert f'description {x["endpoint"]}\nswitchport mode access\nswitchport access vlan {x["vlan"]}' in cfg
for f in ['C1','C2','B1','B2']:
 cfg=(R/f'packet-tracer/configs/R-{f}.txt').read_text()
 assert cfg.index('permit udp any eq 68 any eq 67')<cfg.index('deny ip any 10.0.0.0')
 assert 'ip access-group GUEST-IN in' in cfg
assert [round(sum(a['loads'][f])*1.5,1) for f in ['C1','C2','B1','B2']]==[180.6,132.6,92.7,92.7]
D=Document(R/'docs/Расчёты_вариант_8.docx');S=Presentation(R/'docs/Презентация_вариант_8.pptx')
assert len(S.slides)==18
text='\n'.join(shape.text for s in S.slides for shape in s.shapes if shape.has_text_frame)
assert 'Устинов Илья Максимович' in text and 'ИУ10-59' in text and 'Федорова В. А.' in text
for i in range(1,15):assert any(s.shapes[0].text.startswith(str(i)+'.') for s in S.slides)
assert 'Общая длина Cat6: 2868.4 м' in '\n'.join(x.text for x in D.paragraphs)
for f in [R/'docs/Расчёты_вариант_8.docx', R/'docs/Презентация_вариант_8.pptx']:
 with zipfile.ZipFile(f) as z:assert z.testzip() is None
print('Проверки согласованности пройдены: 99 устройств, порты/VLAN, нагрузка, кабель, смета, 18 слайдов и DOCX.')
print('Cisco Packet Tracer: модель НЕ ПРОВЕРЕНА; результаты функциональных испытаний отсутствуют.')
