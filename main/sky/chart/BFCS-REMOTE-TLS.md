# Existing global BFCS brokers: additive TLS

This phase enables optional mTLS on the existing Linode and CloudFanatic Redis
brokers. It does not move publishing, create replacement brokers, change Redis
ACLs, restart Redis, or disconnect its existing subscribers. The requested eventual
second-broker and dual-consumer migration remains pending global continuity proof.
The EU `sky-bfcs-redis-shared` broker remains independent and additive.

Each cluster adds the pinned, previously tested Nginx stream frontend with the
same event-driven certificate reload files as the leaderboard frontend. TLS
terminates at this frontend. The backend hop is plaintext on the same node:
required Pod affinity targets the existing `sky-bfcs-redis` Pod, and the dedicated
backend Service uses `internalTrafficPolicy: Local` so it cannot fall back to a
remote node. This is transport support through a proxy, not native Redis TLS.
Both frontend replicas share the original singleton broker's node and failure
domain; they do not provide broker HA. Existing plaintext NodePort 31379 remains.

New endpoints are `172.232.26.243:31380` (Linode) and `23.158.232.23:31380`
(CloudFanatic). Each leaf has only its exact IP SAN and its cluster-specific
`sky-bfcs-redis.sky.talos-CLUSTER.coflnet.internal` identity plus the local TLS
Service DNS SAN. Certificate verification must remain enabled. Client certificates
are optional and validated against the shared root when supplied. Existing Redis
password/ACL authentication passes through unchanged. No request logs are enabled.

The NodePort uses `externalTrafficPolicy: Local`, preserving the real source IP.
The frontend accepts only the existing reviewed mesh consumer node /32 allowlist
and local BFCS Pods. The frontend's egress allows only local Redis 6379 and DNS.
The corresponding Talos firewall rule must add 31380 for the same exact consumer
source allowlist, and the port must be unallocated before deployment.

Deploy through GitOps in this order:

1. Use the narrow child-token wrapper to provision `bfcs-linode` and
   `bfcs-cloudfanatic` profiles from `configure-database-pki-issuers.sh`. Verify the
   existing `jwt-talos-linode` and `jwt-talos-cloudfanatic` mounts against their
   exact public OIDC issuers first; this helper does not create auth mounts.
   Revoke the child, prove it invalid, and remove its artifact.
2. Reconcile Fleet `redis-pki`: only the two remote target customizations create
   their namespaced frontend Issuer/SA/TokenRequest binding and shared-root trust.
   Existing `openbao-secrets` connectivity and listener trust are reused.
3. Reconcile the additive frontend resources. Require the Certificate and Issuer
   Ready, two Ready frontends, and local-backend endpoints on the original broker
   node. Compare old Redis Deployment/Service and Pod UID/runID to the preflight
   snapshot. No application configuration changes belong to this phase.
4. Add the reviewed Talos 31380 firewall rule through the existing firewall helper.
   From each actual consumer cluster, verify the served certificate/chain/IP SAN,
   password authentication, optional trusted client certificate, and rejection of
   wrong CA, hostname/IP, client CA and password. Verify unchanged plaintext
   subscriptions and broker runID. A temporary synthetic isolated channel may be
   used only with separate explicit authorization; do not publish test business
   messages. Confirm event-driven leaf renewal without changing old connections.

The shared KV path `kv/sky/sky-bfcs` is read by Linode as well as EU. Never point
its `FLIP_REDIS_OPTIONS` at the EU-internal `.svc` broker. The already appended
EU-only consumer entry must become an EU-only environment setting before removing
that exact key from shared KV using a read-before-write CAS merge patch with JSON
null. Apply the same relocation to the EU-only ModCommands entry. Check the exact
old values first, preserve every other key and previous consumer, verify the EU
Pods retain the same effective subscription, then remove only the two appended
shared keys. Existing publish-helper receipts become stale; do not reuse them.

Before any eventual publisher migration, inventory all live BFCS/ModCommands
consumers (EU, Linode, CloudFanatic, Datawagon, Contabo), establish verified TLS
routes and subscriptions from every consumer to every new publication broker,
and separate cluster-specific publication topology from shared credential KV.
`ModBackgroundService` skips an unreachable entry at startup once another broker
connects; a Ready Pod alone does not prove the complete mesh is subscribed.

Removing the new frontend/Service disables only the new TLS path. Keep the Issuer,
trust and leaf until no new TLS clients remain. The old Redis Pod, plaintext
Service, broker data and global consumer routes remain the rollback anchor.
