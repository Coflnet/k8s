# Preserve active Pub/Sub while adding optional TLS

The four durable candidates `sky-global-redis`, `sky-mod-commands-redis`,
`sky-settings-redis`, and `sky-sniper-redis` use `/data/redis.conf` on their existing
RWO encrypted PVCs. Their running Deployment templates remain identical when
`global.redisOptionalTls.externalReloaderServices` selects them. The matching
`listenerServices` entries create the optional 6380 Services; plaintext 6379 and
all existing business connections remain available.

Deploy the Fleet `redis-pki` ConfigMap worker first. Then add the reviewed EU
CronJobs and network policies through GitOps. Each CronJob runs every 15 minutes,
for at most 60 seconds, with `Forbid` concurrency and no Job retries. Required
Pod affinity places its short-lived worker beside the existing Redis candidate,
sharing that exact PVC without changing the Redis Pod. Completed workers release
their mounts; no long-lived updater can pin the volume to an old node.

After the first GitOps rollout, create one initial Job from each CronJob so the
new TLS listeners become usable immediately. Require successful Job completion
and independently verify the served certificate, hostname/root chain and TLS
PING without a client certificate. Confirm unchanged Redis Pod/container IDs,
Pub/Sub subscriber counts and application traffic before considering enrollment
complete. The network policies permit only the matching Redis candidate on
6379/6380 and cluster DNS; the worker has no API token.

Each run reads one projected certificate generation, writes mode-0600 files in a
mode-0700 generation directory on the encrypted PVC, atomically advances
`/data/optional-tls/current`, and changes only five TLS settings before
`CONFIG REWRITE`. It verifies the served leaf, trusted root chain, required DNS
SAN and optional client-certificate behavior. Unchanged material, persisted
settings and a valid live listener cause no Redis configuration write. A failed
rotation restores the previous generation and TLS settings; a later Job retries
an interrupted persistence step. A PVC-local lock also excludes an overlapping
manual initial Job.

Certificate propagation can take 15 minutes plus scheduling time; the current
24-hour certificate and eight-hour renewal margin cover this interval. Keep the
CronJobs enabled while their listeners are in use. Event-broker Redis has no
persistent configuration file and is excluded from this method.
