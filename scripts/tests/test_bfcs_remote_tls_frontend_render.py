"""Remote BFCS TLS is additive and cannot move the live publication mesh."""
from pathlib import Path
import subprocess
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[2]
CHART = ROOT / 'main/sky/chart'


def render(cluster, enabled=True):
    command = ['helm', 'template', 'sky', str(CHART), '-n', 'sky',
               '-f', str(CHART / 'eu.yaml'), '-f', str(CHART / ('talos-' + cluster + '.yaml'))]
    if not enabled:
        command += ['--set', 'bfcsRemoteTlsFrontend.enabled=false']
    result = subprocess.run(command, text=True, capture_output=True, check=True)
    return {(o['kind'], o['metadata']['name']): o for o in yaml.safe_load_all(result.stdout) if o}


class BfcsRemoteFrontend(unittest.TestCase):
    def test_all_existing_objects_remain_identical_on_both_clusters(self):
        for cluster in ('linode', 'cloudfanatic'):
            with self.subTest(cluster=cluster):
                before, after = render(cluster, False), render(cluster)
                for key, value in before.items():
                    self.assertEqual(after[key], value, key)
                self.assertEqual(len(after) - len(before), 9)

    def test_all_five_consumer_clusters_get_only_the_exact_remote_tls_routes(self):
        for cluster in ('linode', 'cloudfanatic', 'datawagon', 'contabo', 'eu'):
            with self.subTest(cluster=cluster):
                actual = 'talos' if cluster == 'eu' else 'talos-' + cluster
                command = ['helm', 'template', 'sky', str(CHART), '-n', 'sky', '-f', str(CHART / 'eu.yaml')]
                if cluster == 'contabo': command += ['-f', str(CHART / 'talos-datawagon.yaml')]
                command += ['-f', str(CHART / (actual + '.yaml'))]
                output = subprocess.run(command, capture_output=True, text=True, check=True)
                objects = [o for o in yaml.safe_load_all(output.stdout) if o]
                policy = next(o['spec'] for o in objects if o['kind'] == 'NetworkPolicy' and
                              o['metadata']['name'] == 'sky-bfcs-remote-tls-egress')
                self.assertEqual(policy['podSelector'], {'matchExpressions': [
                    {'key': 'app', 'operator': 'In', 'values': ['sky-bfcs', 'sky-mod-commands']}]})
                self.assertEqual(policy['egress'], [{'to': [
                    {'ipBlock': {'cidr': '172.232.26.243/32'}}, {'ipBlock': {'cidr': '23.158.232.23/32'}}],
                    'ports': [{'protocol': 'TCP', 'port': 31380}]}])

    def test_local_backend_and_exact_external_identity(self):
        for cluster, ip in (('linode', '172.232.26.243'), ('cloudfanatic', '23.158.232.23')):
            with self.subTest(cluster=cluster):
                objects = render(cluster)
                cert = objects['Certificate', 'sky-bfcs-redis-frontend-tls']['spec']
                self.assertEqual(cert['ipAddresses'], [ip])
                self.assertEqual(cert['issuerRef']['name'], 'bfcs-redis-frontend-' + cluster)
                self.assertIn('sky-bfcs-redis.sky.talos-' + cluster + '.coflnet.internal', cert['dnsNames'])
                backend = objects['Service', 'sky-bfcs-redis-frontend-local']['spec']
                self.assertEqual(backend['internalTrafficPolicy'], 'Local')
                self.assertEqual(backend['selector'], {'app': 'sky-bfcs-redis'})
                external = objects['Service', 'sky-bfcs-redis-frontend-tls']['spec']
                self.assertEqual(external['externalTrafficPolicy'], 'Local')
                self.assertEqual(external['ports'][0]['nodePort'], 31380)
                pod = objects['Deployment', 'sky-bfcs-redis-frontend']['spec']['template']['spec']
                self.assertFalse(pod['automountServiceAccountToken'])
                self.assertNotIn('persistentVolumeClaim', str(pod['volumes']))
                self.assertEqual(pod['affinity']['podAffinity']['requiredDuringSchedulingIgnoredDuringExecution'],
                    [{'labelSelector': {'matchLabels': {'app': 'sky-bfcs-redis'}},
                      'topologyKey': 'kubernetes.io/hostname'}])
                config = objects['ConfigMap', 'sky-bfcs-redis-frontend-config']['data']
                self.assertIn('ssl_verify_client optional;', config['nginx.conf'])
                self.assertIn('access_log off;', config['nginx.conf'])
                self.assertNotIn('kill -TERM', config['reload-tls.sh'])
                policy = objects['NetworkPolicy', 'sky-bfcs-redis-frontend']['spec']
                cidrs = [p['ipBlock']['cidr'] for p in policy['ingress'][0]['from'] if 'ipBlock' in p]
                self.assertEqual(len(cidrs), 11)
                self.assertTrue(all(c.endswith('/32') for c in cidrs))


if __name__ == '__main__':
    unittest.main()
