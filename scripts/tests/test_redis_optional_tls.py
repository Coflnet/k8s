"""Run with the Fleet redis-pki/chart/files/redis-optional-tls-reloader.py path.
Optional second argument writes the public JSON result. Requires Docker and cryptography.
"""
from pathlib import Path
import datetime as dt
import json, os, secrets, shutil, subprocess, tempfile, select, sys
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
if len(sys.argv) not in (2, 3) or not Path(sys.argv[1]).is_file():
 raise SystemExit('Usage: test_redis_optional_tls.py RELOADER_SCRIPT [RESULT_JSON]')
PYTHON='python:3.13-alpine@sha256:8bcfa47b04b853a17aaf909362b847b2112fd6ec4105ea553ef9a43bafbb5916'
IMAGES=[('redis72','redis@sha256:0637954999d01b7c9ce9167db2da50656e2590d3b884f1c600c5f63bb6e6773c','redis-server','redis-cli'),('valkey72','valkey/valkey@sha256:cbfcb3772ceb0f87ba2bfb2948a3339659696538e9456c0da23edc99fdefb70a','valkey-server','valkey-cli'),('redis74','redis@sha256:858f009f9709ce576febc734aa78b8f6d624b82571f9ddb6bda4377c833b3499','redis-server','redis-cli')]
def command(*argv):
 result=subprocess.run(argv,capture_output=True,text=True)
 if result.returncode: raise RuntimeError(f'{argv[0:3]} failed: {result.stderr[-1500:]} {result.stdout[-1500:]}')
 return result.stdout
for image in [PYTHON]+[i[1] for i in IMAGES]:
 if subprocess.run(['docker','image','inspect',image],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
  command('docker','pull',image)
now=dt.datetime.now(dt.timezone.utc)
ca_key=ec.generate_private_key(ec.SECP256R1())
ca_name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Disposable test CA')])
ca=(x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name).public_key(ca_key.public_key()).serial_number(1).not_valid_before(now-dt.timedelta(minutes=1)).not_valid_after(now+dt.timedelta(days=1)).add_extension(x509.BasicConstraints(ca=True,path_length=None),True).add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()),False).add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),False).add_extension(x509.KeyUsage(True,False,False,False,False,True,True,False,False),True).sign(ca_key,hashes.SHA256()))
results=[]
for label,image,server,cli in IMAGES:
 names=[]
 with tempfile.TemporaryDirectory(prefix='redis-tls-experiment-') as directory:
  root=Path(directory); password=secrets.token_hex(16)
  for serial in [101,102]:
   target=root/f'g{serial}';target.mkdir()
   key=ec.generate_private_key(ec.SECP256R1())
   subject=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'redis.sky.svc.cluster.local')])
   cert=(x509.CertificateBuilder().subject_name(subject).issuer_name(ca_name).public_key(key.public_key()).serial_number(serial).not_valid_before(now-dt.timedelta(minutes=1)).not_valid_after(now+dt.timedelta(hours=1)).add_extension(x509.BasicConstraints(ca=False,path_length=None),True).add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),False).add_extension(x509.KeyUsage(True,False,False,False,False,False,False,False,False),True).add_extension(x509.SubjectAlternativeName([x509.DNSName('redis.sky.svc.cluster.local')]),False).add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),False).sign(ca_key,hashes.SHA256()))
   (target/'tls.crt').write_bytes(cert.public_bytes(serialization.Encoding.PEM))
   (target/'tls.key').write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
   (target/'ca.crt').write_bytes(ca.public_bytes(serialization.Encoding.PEM))
  (root/'..data').symlink_to('g101')
  for name in ['tls.crt','tls.key','ca.crt']: (root/name).symlink_to('..data/'+name)
  shutil.copy(sys.argv[1],root/'reloader.py')
  (root/'probe.py').write_text('''import hashlib, os, socket, ssl
context=ssl.create_default_context(cafile='/optional-tls/ca.crt')
with context.wrap_socket(socket.socket(),server_hostname='redis.sky.svc.cluster.local') as s:
 s.connect(('127.0.0.1',6380))
 password=os.environ['REDIS_PASSWORD'].encode()
 s.sendall(b'*2\\r\\n$4\\r\\nAUTH\\r\\n$%d\\r\\n'%len(password)+password+b'\\r\\n')
 assert s.recv(100)==b'+OK\\r\\n'
 s.sendall(b'*1\\r\\n$4\\r\\nPING\\r\\n'); assert s.recv(100)==b'+PONG\\r\\n'
 print(hashlib.sha256(s.getpeercert(binary_form=True)).hexdigest())
''')
  mount=f'type=bind,src={root},dst=/optional-tls,readonly'
  name=f'redis-tls-test-{os.getpid()}-{label}'; watcher=name+'-watch'
  try:
   command('docker','run','-d','--name',name,'--network','none','--read-only','--user',f'{os.getuid()}:{os.getgid()}','--mount',mount,'--env',f'REDIS_PASSWORD={password}',image,server,'--port','6379','--save','','--appendonly','no','--requirepass',password,'--tls-port','6380','--tls-cert-file','/optional-tls/tls.crt','--tls-key-file','/optional-tls/tls.key','--tls-ca-cert-file','/optional-tls/ca.crt','--tls-auth-clients','optional')
   names.append(name)
   command('docker','run','-d','--name',watcher,'--network',f'container:{name}','--read-only','--user',f'{os.getuid()}:{os.getgid()}','--mount',mount,'--env',f'REDIS_PASSWORD={password}','--env','REDIS_TLS_SERVER_NAME=redis.sky.svc.cluster.local',PYTHON,'python3','-B','/optional-tls/reloader.py')
   names.append(watcher)
   before=command('docker','exec',watcher,'python3','-B','/optional-tls/probe.py').strip()
   command('docker','exec',watcher,'python3','-B','/optional-tls/reloader.py','--check')
   plain=command('docker','exec',name,'sh','-ec',f'REDISCLI_AUTH="$REDIS_PASSWORD" {cli} PING').strip()
   assert plain=='PONG',plain
   denied=command('docker','exec',name,cli,'PING').strip()
   assert denied.startswith('NOAUTH'),denied
   command('docker','kill','--signal=STOP',watcher)
   (root/'..data_tmp').symlink_to('g102');(root/'..data_tmp').replace(root/'..data')
   stale=subprocess.run(['docker','exec',watcher,'python3','-B','/optional-tls/reloader.py','--check'],capture_output=True,text=True,timeout=15)
   assert stale.returncode!=0 and 'stale TLS certificate' in stale.stderr, stale.stderr
   command('docker','kill','--signal=CONT',watcher)
   # Wait on the actual reload event from the container log stream, bounded.
   logs=subprocess.Popen(['docker','logs','--follow',watcher],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
   try:
    assert select.select([logs.stdout],[],[],20)[0], 'No reload event within 20 seconds'
    event=logs.stdout.readline().strip()
    assert event=='Redis TLS certificate/trust reloaded',event
   finally:
    logs.terminate();logs.wait(timeout=5)
   after=command('docker','exec',watcher,'python3','-B','/optional-tls/probe.py').strip()
   assert before!=after
   command('docker','exec',watcher,'python3','-B','/optional-tls/reloader.py','--check')
   results.append({'image':image,'plaintext_authenticated':'PONG','plaintext_without_password':'NOAUTH','tls_without_client_certificate':'PONG','event_driven_certificate_rotation':'verified','listener_freshness_probe':'rejects-stale-accepts-current','restarts':0})
  finally:
   for name in reversed(names): subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
if len(sys.argv)>2: Path(sys.argv[2]).write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2))
