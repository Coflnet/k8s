"""Run: python3 scripts/tests/test_payments_kafka_client_render.py
Renders the payments chart with the talos-eu-hcloud values and asserts that sky/ane use their own Kafka client
leaf (own read-only Secret volume without subPath, CA from the /pki/trust mount) and dash/tab are untouched."""
from pathlib import Path
import subprocess, sys
import yaml
CHART = Path(__file__).resolve().parents[2] / 'main/payments/chart'
FILES = ['talos.yaml', 'talos-openbao-secrets-cutover.yaml']
LEAF_ENV = {'KAFKA__TLS__CA_LOCATION': '/pki/trust/kafka-ca.crt',
            'KAFKA__TLS__CERTIFICATE_LOCATION': '/pki/kafka-client/tls.crt',
            'KAFKA__TLS__KEY_LOCATION': '/pki/kafka-client/tls.key'}

def render():
    args = ['helm', 'template', 'payments', str(CHART), '-n', 'payment']
    for f in FILES: args += ['-f', str(CHART / f)]
    docs = yaml.safe_load_all(subprocess.run(args, check=True, capture_output=True, text=True).stdout)
    return {d['metadata']['name']: d['spec']['template']['spec'] for d in docs if d and d.get('kind') == 'Deployment'}

def leaf_errors(instance, pod):
    c = pod['containers'][0]
    env = [e for e in c['env'] if e['name'].startswith('KAFKA__TLS__')]
    errors = [] if {e['name']: e.get('value') for e in env} == LEAF_ENV and len(env) == 3 else [f'env {env}']
    mounts = {m['name']: m for m in c['volumeMounts']}
    if mounts.get('kafka-client') != {'name': 'kafka-client', 'mountPath': '/pki/kafka-client', 'readOnly': True}:
        errors.append(f"mount {mounts.get('kafka-client')}")
    if mounts.get('cockroach-client-trust', {}).get('mountPath') != '/pki/trust':
        errors.append('no /pki/trust mount for kafka-ca.crt')
    volumes = {v['name']: v for v in pod['volumes']}
    if volumes.get('kafka-client', {}).get('secret') != {'secretName': f'{instance}-payments-kafka-client', 'defaultMode': 0o440}:
        errors.append(f"volume {volumes.get('kafka-client')}")
    return errors

def untouched_errors(pod):
    c = pod['containers'][0]
    errors = [f"env {e['name']}" for e in c['env'] if e['name'].startswith('KAFKA__TLS__')]
    return errors + [f"volume {v['name']}" for v in pod['volumes'] if v['name'] == 'kafka-client']

pods = render()
failed = False
for instance in ('sky', 'ane', 'dash', 'tab'):
    pod = pods[f'{instance}-payments']
    errors = leaf_errors(instance, pod) if instance in ('sky', 'ane') else untouched_errors(pod)
    print(('FAIL' if errors else 'ok  '), instance, '; '.join(errors))
    failed |= bool(errors)
sys.exit(1 if failed else 0)
