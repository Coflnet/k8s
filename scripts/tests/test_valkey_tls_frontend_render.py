"""The optional Valkey frontend cannot alter any existing workload or endpoint."""
import copy
from pathlib import Path
import subprocess
import tempfile
import unittest
import yaml

CHART = Path(__file__).resolve().parents[2] / 'main/leaderboard/chart'


def render(values, *files):
    files = files or ('valkey-handoff-eu.yaml',)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml') as stream:
        yaml.safe_dump(values, stream)
        stream.flush()
        result = subprocess.run(['helm', 'template', 'leaderboard', str(CHART), '--namespace', 'sky',
            *[arg for name in files for arg in ('-f', str(CHART / name))], '-f', stream.name],
            text=True, capture_output=True, check=True)
    return {(obj['kind'], obj['metadata']['name']): obj
            for obj in yaml.safe_load_all(result.stdout) if obj}


class ValkeyFrontendRender(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        active = yaml.safe_load((CHART / 'redis-optional-tls-eu.yaml').read_text())
        cls.active = render(active)
        before = copy.deepcopy(active)
        before['valkeyTlsFrontend']['enabled'] = False
        before['global']['redisOptionalTls']['listenersEnabled'] = False
        cls.before = render(before)

    def test_all_preexisting_objects_are_identical(self):
        for key, obj in self.before.items():
            with self.subTest(resource=key):
                self.assertEqual(self.active[key], obj)
        self.assertEqual(self.active['Service', 'redis-tls']['spec']['selector'], {'app': 'redis-tls-frontend'})

    def test_restarted_valkey_pod_keeps_the_route_its_services_select(self):
        # 2026-11-12: the route label existed only on the live Pod, so a replacement
        # Pod would have left sky/redis and redis-tls-local without an endpoint.
        deployment = self.active['Deployment', 'redis']['spec']
        labels = deployment['template']['metadata']['labels']
        self.assertEqual(deployment['selector'], {'matchLabels': {'app': 'redis'}})
        for name in ('redis', 'redis-tls-local'):
            selector = self.active['Service', name]['spec']['selector']
            self.assertEqual(selector, {'app': 'redis', 'redis-route': 'persistent-v1'})
            self.assertLessEqual(selector.items(), labels.items())
        routed = [key for key, obj in self.active.items() if key[0] == 'Deployment'
                  and obj['spec']['template']['metadata']['labels'].get('redis-route') == 'persistent-v1']
        self.assertEqual(sorted(routed), [('Deployment', 'redis'), ('Deployment', 'redis-upgrade')])
        self.assertEqual(self.active['Deployment', 'redis-upgrade']['spec']['replicas'], 0)
        unrouted = render({}, 'values.yaml')
        self.assertEqual(unrouted['Deployment', 'redis']['spec']['template']['metadata']['labels'], {'app': 'redis'})

    def test_talos_maintenance_declarations(self):
        def declared(name):
            meta = self.active['Service', name]['metadata']
            return meta.get('labels'), meta.get('annotations')
        policy = 'maintenance.coflnet.com/drain-policy'
        self.assertEqual(declared('redis-tls-local'), ({policy: 'follows'}, {'maintenance.coflnet.com/follows': 'redis'}))
        self.assertEqual(declared('redis-tls'), ({policy: 'follows'}, {'maintenance.coflnet.com/follows': 'redis',
                                                                      'maintenance.coflnet.com/follows-via': 'pod-affinity',
                                                                      'maintenance.coflnet.com/max-downtime-seconds': '120'}))
        self.assertEqual(declared('leaderboard'), ({'app': 'leaderboard', policy: 'handoff'},
                                                   {'maintenance.coflnet.com/max-downtime-seconds': '0'}))
        self.assertEqual(declared('redis'), (None, None))
        budget = self.active['PodDisruptionBudget', 'redis-tls-frontend']['spec']
        self.assertEqual((budget['minAvailable'], budget['unhealthyPodEvictionPolicy']), (1, 'AlwaysAllow'))
        unfronted = render({'global': {'redisOptionalTls': {'enabled': True, 'listenersEnabled': True,
            'services': ['redis'], 'issuerName': 'i', 'trustBundleConfigMap': 'c', 'clusterIdentity': 'x'}}}, 'values.yaml')
        self.assertEqual(unfronted['Service', 'redis-tls']['metadata']['labels'], {policy: 'block'})

    def test_plaintext_is_local_and_original_pod_is_the_only_affinity_target(self):
        service = self.active['Service', 'redis-tls-local']['spec']
        self.assertEqual(service['internalTrafficPolicy'], 'Local')
        self.assertEqual(service['selector'], self.before['Service', 'redis']['spec']['selector'])
        pod = self.active['Deployment', 'redis-tls-frontend']['spec']['template']['spec']
        self.assertFalse(pod['automountServiceAccountToken'])
        self.assertFalse(any('persistentVolumeClaim' in volume for volume in pod['volumes']))
        affinity = pod['affinity']['podAffinity']['requiredDuringSchedulingIgnoredDuringExecution']
        self.assertEqual(affinity, [{'labelSelector': {'matchLabels': {'app': 'redis'},
            'matchExpressions': [{'key': 'redis-upgrade-candidate', 'operator': 'DoesNotExist'}]},
            'topologyKey': 'kubernetes.io/hostname'}])
        config = self.active['ConfigMap', 'redis-tls-frontend-config']['data']
        self.assertIn('ssl_verify_client optional;', config['nginx.conf'])
        self.assertIn("log_format pki 'tls_client_verify=$ssl_client_verify tls_client_serial=$ssl_client_serial';", config['nginx.conf'])
        self.assertIn('access_log /dev/stdout pki if=$ssl_protocol;', config['nginx.conf'])
        self.assertNotIn('kill -TERM', config['reload-tls.sh'])


if __name__ == '__main__':
    unittest.main()
