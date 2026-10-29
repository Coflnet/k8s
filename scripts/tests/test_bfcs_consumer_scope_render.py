"""EU-local Redis connection topology must not enter remote BFCS Pod specs."""
from pathlib import Path
import subprocess
import unittest
import yaml

CHART = Path(__file__).resolve().parents[2] / 'main/sky/chart'
CONNECTION = ('sky-bfcs-redis-shared-tls.sky.svc.cluster.local:6380,ssl=true,'
              'sslHost=sky-bfcs-redis-shared.sky.svc.cluster.local,syncTimeout=1000')


def render(cluster):
    files = ['eu.yaml']
    if cluster == 'eu': files += ['talos.yaml', 'redis-optional-tls-eu.yaml', 'bfcs-shared-redis-eu.yaml']
    elif cluster == 'contabo': files += ['talos-datawagon.yaml', 'talos-contabo.yaml']
    else: files += ['talos-' + cluster + '.yaml']
    command = ['helm', 'template', 'sky', str(CHART), '-n', 'sky']
    for name in files: command += ['-f', str(CHART / name)]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    return {(o['kind'], o['metadata']['name']): o for o in yaml.safe_load_all(result.stdout) if o}


class BfcsConsumerScope(unittest.TestCase):
    def test_exact_eu_entries_and_original_publisher_ref(self):
        objects = render('eu')
        for kind, name, index in [('Deployment', 'sky-bfcs', 3), ('Rollout', 'sky-mod-commands', 4)]:
            env = objects[kind, name]['spec']['template']['spec']['containers'][0]['env']
            self.assertEqual([e for e in env if e['name'] == 'REDIS_FLIP_INSTANCES__' + str(index)],
                             [{'name': 'REDIS_FLIP_INSTANCES__' + str(index), 'value': CONNECTION}])
        env = objects['Deployment', 'sky-bfcs']['spec']['template']['spec']['containers'][0]['env']
        self.assertEqual([e for e in env if e['name'] == 'FLIP_REDIS_OPTIONS'], [{'name': 'FLIP_REDIS_OPTIONS',
            'valueFrom': {'secretKeyRef': {'name': 'sky-bfcs-redis-auth', 'key': 'connection'}}}])

    def test_all_remote_consumers_keep_their_existing_topology(self):
        for cluster in ('linode', 'cloudfanatic', 'datawagon', 'contabo'):
            with self.subTest(cluster=cluster):
                objects = render(cluster)
                env = objects['Deployment', 'sky-bfcs']['spec']['template']['spec']['containers'][0]['env']
                self.assertFalse(any(e.get('value') == CONNECTION for e in env))


if __name__ == '__main__': unittest.main()
