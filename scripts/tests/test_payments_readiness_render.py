"""Run: python3 scripts/tests/test_payments_readiness_render.py
Renders the payments chart with every Fleet values set and asserts the readiness probe hits /health/ready."""
from pathlib import Path
import subprocess, sys
import yaml
CHART = Path(__file__).resolve().parents[2] / 'main/payments/chart'
VALUE_SETS = {'default': [], 'talos': ['talos.yaml', 'talos-openbao-secrets-cutover.yaml'], 'us': ['us.yaml']}
def render(files):
    args = ['helm', 'template', 'payments', str(CHART), '-n', 'payment']
    for f in files: args += ['-f', str(CHART / f)]
    return [d for d in yaml.safe_load_all(subprocess.run(args, check=True, capture_output=True, text=True).stdout) if d]
def payments_probes(docs):
    for d in docs:
        if d.get('kind') != 'Deployment': continue
        for c in d['spec']['template']['spec']['containers']:
            if c.get('readinessProbe'): yield d['metadata']['name'], c['readinessProbe']
failed = False
for name, files in VALUE_SETS.items():
    probes = list(payments_probes(render(files)))
    if name == 'talos' and len(probes) != 4: print(f'FAIL {name}: expected 4 payments deployments, got {len(probes)}'); failed = True
    for dep, probe in probes:
        ok = probe['httpGet']['path'] == '/health/ready' and probe.get('timeoutSeconds', 1) > 3
        print(('ok  ' if ok else 'FAIL'), name, dep, probe['httpGet']['path'], probe.get('timeoutSeconds'))
        failed |= not ok
sys.exit(1 if failed else 0)
