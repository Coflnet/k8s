# Preserve leaderboard Valkey while adding optional TLS

The existing `sky/redis` Pod has no writable data volume or certificate mount.
Runtime `CONFIG SET tls-*` is supported, but supplying files inside that old
container would be temporary; persisting mounts/startup args through GitOps
still replaces the Pod and loses its volatile state. Use a same-image replica
handoff to the separately declared `redis-upgrade` PVC candidate.

The helper remains `ansible/scripts/handoff-sky-redis.sh KUBECONFIG redis persistent-v1 PHASE`.
It pins the exact current Valkey digest and version, Service/controller/Pod/PVC
identities, encrypted two-replica storage, replica sync, persisted primary role,
Service EndpointSlices and all six Cilium backend maps. Replication does not
copy ACLs: the helper copies complete hashed ACL rules over stdin into a 0600
file on the encrypted PVC, loads them and checks equality without logging rules.
Keep administrative ACL changes paused throughout this bounded handoff. Data
writers continue normally until coordinated `FAILOVER` briefly pauses writes.

Do not add `valkey-handoff-eu.yaml` to Fleet automatically. Apply these reviewed
stages, checking each result before proceeding:

1. Require the exact `redis-shared-tls` certificate Ready, matching private key
   and valid root chain, and all existing clients/Service endpoints healthy.
   Require `redis-upgrade` PVC/Deployment absent or matching a retained task
   receipt. Record source Pod/run IDs, version, memory, keyspace counts, TTL
   behavior, clients and replica state. Confirm scheduling/storage capacity:
   candidate requests 128Mi, limit 512Mi; observed source peak was 122,171,008
   bytes with 99,020,800 RSS. No node drain, pressure, image upgrade or concurrent
   maintenance may overlap the handoff.
2. Add `./chart/valkey-handoff-eu.yaml` to only leaderboard's EU Fleet target.
   Keep `global.redisOptionalTls.listenersEnabled: false`. This creates the
   same-image TLS-capable candidate with AOF/everysec and an ACL file configured
   before first boot. The current Deployment and Service remain unchanged.
   The candidate deliberately stays NotReady until both primary role and its
   durable `/data/active` marker exist. Require it Scheduled/Running, no OOM or
   restarts, encrypted PVC Bound and healthy on two Longhorn replicas.
3. Run `label-old`; this creates/validates the owned receipt before applying
   its temporary Pod route label. Then declare
   `global.redisUpgrade.routes.redis: persistent-v1` in that EU values file.
   Wait for Fleet and prove the old Pod is still the only Ready Service endpoint.
4. Run `sync`. Concurrent writes replicate while the helper copies ACLs, sets
   and persists REPLICAOF, and waits for an online synchronized replica with AOF.
   Recheck application health, storage and source/candidate identity before
   `cutover`. `cutover` uses `FAILOVER TO ... TIMEOUT 30000`, persists the new
   primary, activates its marker, proves endpoint/backend convergence and
   disconnects old client sockets so they reconnect through the same Service.
   Expect bounded READONLY/reconnect errors; clients must retry appropriately.
   Do not replace this with `REPLICAOF NO ONE`, a snapshot-only copy or a forced
   failover. If interrupted, inspect the receipt/roles and resume that phase.
5. Run `verify` and `disconnect-old`; require acknowledged application writes,
   key counts/data structures/absolute TTLs and ACL behavior intact. Then declare
   `global.redisUpgrade.retired.redis: true` and wait for the old Deployment to
   reach zero. Keep the candidate/PVC as the authoritative store and enroll its
   existing backup policy before later maintenance.
6. Finally set `listenersEnabled: true` and `listenerServices: [redis]` for the
   EU leaderboard chart. The TLS Service now routes to the active persistent
   candidate. This final flag does not alter the already running candidate's
   Pod template, so it causes no second data movement or Redis restart.

The isolated exact-image test recorded 989 acknowledged concurrent writes
surviving a 0.914-second coordinated failover and AOF restart, complete ACL
transfer, stream pending state, hashes and absolute TTLs. It used idempotent
write retries; it does not establish crash/power-loss durability or production
Kubernetes routing behavior. Existing Cilium/application health gates cover
that route during the real handoff. No production handoff was performed here.
