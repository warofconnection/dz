"""Read/write an uploaded Packet Tracer 8.2.2 document, with integrity checks.
Does not run Packet Tracer, script modules, logins, or document code.
Requires the BSD-licensed PyPI 'twofish' library. Python 3.12 compatibility only
changes extension discovery; the library's known-answer self-tests stay enabled.
"""
from pathlib import Path
import sys,types,importlib.util,hmac,struct,zlib
try:
 import imp
except ModuleNotFoundError:
 shim=types.ModuleType('imp')
 def find_module(name):
  spec=importlib.util.find_spec(name)
  if spec is None:raise ImportError(name)
  return None,spec.origin,None
 shim.find_module=find_module
 sys.modules['imp']=shim
from twofish import Twofish

def xor(a,b):return bytes(x^y for x,y in zip(a,b))
def shift(b):
 n=int.from_bytes(b,'big');return (((n<<1)&((1<<128)-1))^(0x87 if n>>127 else 0)).to_bytes(16,'big')
def cmac(cipher,data):
 k1=shift(cipher.encrypt(bytes(16)));k2=shift(k1);blocks=max(1,(len(data)+15)//16)
 if data and len(data)%16==0:tail=xor(data[-16:],k1)
 else:
  rem=data[(blocks-1)*16:];tail=xor(rem+b'\x80'+bytes(15-len(rem)),k2)
 state=bytes(16)
 for i in range(blocks-1):state=cipher.encrypt(xor(state,data[i*16:i*16+16]))
 return cipher.encrypt(xor(state,tail))
def crypt(cipher,data,nonce_tag):
 counter=int.from_bytes(nonce_tag,'big');out=bytearray()
 for i in range(0,len(data),16):
  out+=xor(data[i:i+16],cipher.encrypt(counter.to_bytes(16,'big')))
  counter=(counter+1)&((1<<128)-1)
 return bytes(out)
def tags(cipher,data):
 omac=lambda n,d:cmac(cipher,bytes(15)+bytes([n])+d)
 nonce_tag=omac(0,bytes([0x10])*16)
 tag=xor(xor(nonce_tag,omac(1,b'')),omac(2,data))
 return nonce_tag,tag

def decode_document(raw,max_bytes=50*1024*1024):
 size=len(raw)
 if size<20:raise ValueError('Truncated PKT container')
 wrapped=bytes(raw[size-1-i]^((size*(1-i))&255) for i in range(size))
 cipher=Twofish(bytes([0x89])*16);cipher_text,tag=wrapped[:-16],wrapped[-16:]
 nonce_tag,expected=tags(cipher,cipher_text)
 if not hmac.compare_digest(tag,expected):raise ValueError('PKT EAX integrity check failed')
 data=crypt(cipher,cipher_text,nonce_tag)
 data=bytes(v^((len(data)-i)&255) for i,v in enumerate(data))
 expected_size=struct.unpack('>I',data[:4])[0]
 if expected_size>max_bytes:raise ValueError('Uncompressed document exceeds limit')
 d=zlib.decompressobj();xml=d.decompress(data[4:],expected_size+1)
 if len(xml)!=expected_size or not d.eof or d.unused_data:raise ValueError('Zlib integrity/size mismatch')
 return xml

def encode_document(xml):
 data=struct.pack('>I',len(xml))+zlib.compress(xml,6)
 data=bytes(v^((len(data)-i)&255) for i,v in enumerate(data))
 cipher=Twofish(bytes([0x89])*16);nonce_tag,_=tags(cipher,b'')
 encrypted=crypt(cipher,data,nonce_tag);_,tag=tags(cipher,encrypted)
 wrapped=encrypted+tag;size=len(wrapped);out=bytearray(size)
 for i,v in enumerate(wrapped):out[size-1-i]=v^((size*(1-i))&255)
 out=bytes(out)
 if decode_document(out)!=xml:raise ValueError('Encoded PKT failed lossless round-trip validation')
 return out
