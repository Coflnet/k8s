"""Run: python3 scripts/tests/test_sky_proxy_kafka_client_render.py
Renders the sky chart with the talos-eu-hcloud values and asserts that sky-proxy's Kafka client uses its own leaf:
each KAFKA__TLS__* key exactly once (pki.env replaces the global legacy paths), the leaf Secret on its own read-only
volume without subPath, and pki-client still the Cockroach leaf."""
from pathlib import Path
import subprocess, sys
import yaml
BUNDLE = Path(__file__).resolve().parents[2] / 'main/sky'
LEAF_ENV = {'KAFKA__TLS__CA_LOCATION': '/pki/trust/kafka-ca.crt',
            'KAFKA__TLS__CERTIFICATE_LOCATION': '/pki/kafka-client/tls.crt',
            'KAFKA__TLS__KEY_LOCATION': '/pki/kafka-client/tls.key',
            'KAFKA__TLS__RELOAD_ON_CHANGE': 'true'}

def values_files():
    fleet = yaml.safe_load((BUNDLE / 'fleet.yaml').read_text())
    target = next(t for t in fleet['targetCustomizations'] if t['clusterName'] == 'talos-eu-hcloud')
    return fleet['helm']['valuesFiles'] + target['helm']['valuesFiles']

def render_pod():
    args = ['helm', 'template', 'sky', str(BUNDLE / 'chart'), '-n', 'sky']
    for f in values_files(): args += ['-f', str(BUNDLE / f)]
    docs = yaml.safe_load_all(subprocess.run(args, check=True, capture_output=True, text=True).stdout)
    return next(d for d in docs if d and d['kind'] == 'Deployment' and d['metadata']['name'] == 'sky-proxy')['spec']['template']['spec']

pod = render_pod()
c = pod['containers'][0]
errors = []
env = [e for e in c['env'] if e['name'].startswith('KAFKA__TLS__')]
if len(env) != len(LEAF_ENV) or {e['name']: e.get('value') for e in env} != LEAF_ENV: errors.append(f'env {env}')
mounts = {m['name']: m for m in c['volumeMounts']}
if mounts.get('pki-kafka-client') != {'name': 'pki-kafka-client', 'mountPath': '/pki/kafka-client', 'readOnly': True}:
    errors.append(f"mount {mounts.get('pki-kafka-client')}")
volumes = {v['name']: v for v in pod['volumes']}
if volumes.get('pki-kafka-client', {}).get('secret') != {'secretName': 'sky-proxy-client', 'defaultMode': 0o440}:
    errors.append(f"volume {volumes.get('pki-kafka-client')}")
if volumes.get('pki-client', {}).get('secret', {}).get('secretName') != 'sky-proxy-cockroach-client':
    errors.append('pki-client is no longer the Cockroach leaf')
print('FAIL' if errors else 'ok  ', 'sky-proxy', '; '.join(errors))
sys.exit(1 if errors else 0)
