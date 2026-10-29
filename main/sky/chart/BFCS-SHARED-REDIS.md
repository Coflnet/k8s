# BFCS Redis TLS coexistence

Keep `sky-bfcs-redis` and every current consumer connection running. Add the
independent `sky-bfcs-redis-shared` broker and its
`sky-bfcs-redis-shared-tls.sky.svc.cluster.local:6380` Service. This is a second
Pub/Sub instance, not a replacement endpoint for the old Service.

The EU-only `bfcs-shared-redis-eu.yaml` initially creates the new broker without
changing any existing rendered object. Its exact certificate uses the dedicated
`sky/bfcs-shared-root` Issuer and `redis-server-bfcs-shared` role. The existing
namespace shared-root ConfigMap, renewal reloader and probes are reused.
The new broker keeps the current EU default-user/nopass contract; its external
Pod ingress permits only TLS6380 from BFCS and ModCommands. Old broker auth,
credentials, roots, connections and Service selectors remain untouched.

1. Provision the exact new role/JWT profile through the narrow child-token
   workflow and publish the new namespaced Issuer through Fleet. Apply the new
   broker source and require its certificate, independent endpoint and TLS
   freshness probe healthy. Leave consumersEnabled false and publisherRevision
   empty. No old Pod or Service changes in this stage.
2. Run the Ansible helper `configure-bfcs-redis-coexistence.py consume --execute
   --receipt PRIVATE/consumers.json` inside a narrow OpenBao session. It reads
   both current KV versions and CAS-patches only BFCS
   `REDIS_FLIP_INSTANCES__3` and ModCommands `REDIS_FLIP_INSTANCES__4`. Every
   previous instance, publisher field and unrelated secret field is preserved
   and read back. The helper defaults to audit; `consume --print-policy` renders
   its exact two-leaf task policy. Revoke/prove403/remove the child immediately.
3. Set `global.bfcsSharedRedis.consumersEnabled: true` only in the EU values
   file and reconcile consumers normally. Their old publication target remains
   unchanged. The flag adds the shared-root mount and
   `SSL_CERT_DIR=/etc/ssl/certs:/redis-shared-trust`, preserving system roots.
   Existing application code subscribes to multiple instances. Allow rolling
   availability: BFCS's singleton keeps its old Ready Pod until the new one is
   Ready. For ModCommands use an EU canary override maxUnavailable0/maxSurge1
   during this change if capacity allows; never scale either workload to zero.
   Stop on scheduling or analysis failure; the old broker keeps serving.
4. Run `verify --consumer-receipt PRIVATE/consumers.json --kubeconfig KUBECONFIG
   --receipt PRIVATE/canary.json`. It binds the verified TLS leaf, independent
   old/new endpoints and every current fully updated Ready consumer Pod. It
   requires both snipes/beat subscriptions on the new broker from every
   consumer, rejecting unknown clients. The immutable0600 receipt contains no
   credentials. This phase is read-only against production.
5. In a new narrow child session run `publish --execute --consumer-receipt
   PRIVATE/consumers.json --canary-receipt PRIVATE/canary.json --kubeconfig
   KUBECONFIG --receipt PRIVATE/publisher.json`. It rechecks live canary evidence,
   rejects a changed old publisher, and CAS-patches only FLIP_REDIS_OPTIONS.
   Revoke/prove403/remove that child immediately. Then set the EU
   `global.bfcsSharedRedis.publisherRevision: shared-tls-v1` to roll only BFCS;
   its primary multiplexer is constructed at startup. Both brokers remain
   subscribed throughout the rolling publisher transition.
6. Verify BFCS Ready, its additional publisher connection on the TLS broker,
   business publication and all consumer subscriptions. Retain the old broker
   and all old instance entries. Retirement and mandatory mTLS are separate.

Both exact deployed application images were tested with their actual shipped
StackExchange.Redis assembly. The proposed TLS connection parsed and connected
with standard validation; wrongCA/SAN failed; all120 public roots remained.
IConfiguration tests showed the new flat last-provider keys append correctly,
including ModCommands's existing gapped0/2/3 indices. Message deduplication in
ModBackgroundService already suppresses duplicate auction/finder/price tuples
across subscribed brokers. No application image build is needed.
