from pathlib import Path
import json
R=Path(__file__).resolve().parents[1];data=json.loads((R/'docs/project-data.json').read_text());C=R/'packet-tracer/configs'
def write(n,lines): (C/(n+'.txt')).write_text('\n'.join(['enable','configure terminal','hostname '+n,'no ip domain-lookup']+lines+['end','write memory','']))
for floor,s in [('C1',1),('C2',2),('B1',11),('B2',12)]:
 lines=[]
 vlans=[10,20,30,90,99] if floor=='C1' else [10,20,90,99] if floor=='C2' else [10,90,99]
 for v in vlans:
  lines += [f'ip dhcp excluded-address 10.{s}.{v}.1 10.{s}.{v}.49',f'ip dhcp pool {floor}-V{v}',f'network 10.{s}.{v}.0 255.255.255.0',f'default-router 10.{s}.{v}.1',f'dns-server {"203.0.113.10" if v==90 else "10.1.30.11"}','exit'] if v not in [30,99] else []
 lines+=['ip access-list extended GUEST-IN','permit udp any eq 68 any eq 67','deny ip any 10.0.0.0 0.255.255.255','permit ip any any','exit','interface GigabitEthernet0/0','no shutdown','exit']
 for v in vlans:
  lines += [f'interface GigabitEthernet0/0.{v}',f'encapsulation dot1Q {v}',f'ip address 10.{s}.{v}.1 255.255.255.0']
  if v==90: lines+=['ip access-group GUEST-IN in']
  lines+=['exit']
 if floor=='C1':
  lines+=['interface GigabitEthernet0/1','description TO-R-C2','ip address 10.255.0.1 255.255.255.252','no shutdown','exit','interface GigabitEthernet0/2','description TO-R-EDGE','ip address 10.255.0.5 255.255.255.252','no shutdown','exit','ip route 10.2.0.0 255.255.0.0 10.255.0.2','ip route 0.0.0.0 0.0.0.0 10.255.0.6']
 elif floor=='C2':lines+=['interface GigabitEthernet0/1','description TO-R-C1','ip address 10.255.0.2 255.255.255.252','no shutdown','exit','ip route 0.0.0.0 0.0.0.0 10.255.0.1']
 else:
  b=int(floor[-1]);lines+=['interface GigabitEthernet0/1','description TO-OPERATOR',f'ip address 10.255.{b}.2 255.255.255.252','no shutdown','exit',f'ip route 0.0.0.0 0.0.0.0 10.255.{b}.1']
 write('R-'+floor,lines)
write('R-EDGE',['interface GigabitEthernet0/0','ip address 10.255.0.6 255.255.255.252','ip nat inside','no shutdown','exit','interface GigabitEthernet0/1','no shutdown','exit','interface GigabitEthernet0/1.901','encapsulation dot1Q 901','ip address 10.255.1.1 255.255.255.252','ip nat inside','exit','interface GigabitEthernet0/1.902','encapsulation dot1Q 902','ip address 10.255.2.1 255.255.255.252','ip nat inside','exit','interface GigabitEthernet0/1.903','encapsulation dot1Q 903','ip address 198.51.100.2 255.255.255.252','ip nat outside','exit','access-list 1 permit 10.0.0.0 0.255.255.255','ip nat inside source list 1 interface GigabitEthernet0/1.903 overload','ip route 10.1.0.0 255.255.0.0 10.255.0.5','ip route 10.2.0.0 255.255.0.0 10.255.0.5','ip route 10.11.0.0 255.255.0.0 10.255.1.2','ip route 10.12.0.0 255.255.0.0 10.255.2.2','ip route 0.0.0.0 0.0.0.0 198.51.100.1'])
write('R-ISP',['interface GigabitEthernet0/0','ip address 198.51.100.1 255.255.255.252','no shutdown','exit','interface GigabitEthernet0/1','ip address 203.0.113.1 255.255.255.0','no shutdown','exit'])
for sw in sorted(set(p['device'] for p in data['ports'])):
 floor=sw[3:5];s={'C1':1,'C2':2,'B1':11,'B2':12}[floor];lines=[]
 vlans=[10,20,30,90,99] if floor=='C1' else [10,20,90,99] if floor=='C2' else [10,90,99]
 for v in vlans:lines += [f'vlan {v}',f'name VLAN{v}','exit']
 used=[]
 for p in data['ports']:
  if p['device']!=sw:continue
  used.append(int(p['port'].split('/')[-1]));lines += ['interface '+p['port'],'description '+p['endpoint'],'switchport mode access',f'switchport access vlan {p["vlan"]}','spanning-tree portfast','no shutdown','exit']
 lines+=['interface GigabitEthernet0/1','description TO-ROUTER' if not sw.endswith('B') else 'description TO-SW-A','switchport mode trunk','switchport trunk allowed vlan '+','.join(map(str,vlans)),'no shutdown','exit']
 if floor.startswith('C') and sw.endswith('A'):lines+=['interface GigabitEthernet0/2','description TO-SW-B','switchport mode trunk','switchport trunk allowed vlan '+','.join(map(str,vlans)),'no shutdown','exit']
 else:lines+=['interface GigabitEthernet0/2','shutdown','exit']
 for port in range(1,25):
  if port not in used:lines+=['interface FastEthernet0/'+str(port),'shutdown','exit']
 lines+=['interface Vlan99',f'ip address 10.{s}.99.{3 if sw.endswith("B") else 2} 255.255.255.0','no shutdown','exit',f'ip default-gateway 10.{s}.99.1']
 write(sw,lines)
write('SW-PROVIDER',['vlan 901','name BRANCH1','exit','vlan 902','name BRANCH2','exit','vlan 903','name INTERNET','exit','interface GigabitEthernet0/1','description TO-R-EDGE','switchport mode trunk','switchport trunk allowed vlan 901,902,903','no shutdown','exit','interface FastEthernet0/1','description TO-R-B1','switchport mode access','switchport access vlan 901','no shutdown','exit','interface FastEthernet0/2','description TO-R-B2','switchport mode access','switchport access vlan 902','no shutdown','exit','interface GigabitEthernet0/2','description TO-R-ISP','switchport mode access','switchport access vlan 903','no shutdown','exit'])
print('Generated',len(list(C.glob('*.txt'))),'Cisco configuration files')
