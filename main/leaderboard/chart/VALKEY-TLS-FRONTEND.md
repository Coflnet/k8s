# Optional TLS without moving Valkey or its Pub/Sub connections

`valkeyTlsFrontend.enabled` adds a separate, stateless Nginx stream frontend.
The original `redis` Deployment, plaintext `redis:6379` Service and all existing
broker/client connections remain unchanged. Native persistent migration remains
held: the application uses a real cache-invalidation subscription and its
FireAndForget writes do not provide a safe producer handoff barrier.

Clients can use `redis-tls.sky.svc.cluster.local:6380`. The existing
`redis-shared-tls` certificate covers that name. Client certificates are optional;
if supplied, they must verify against `redis-shared-root-trust`. Redis AUTH and
ACL protocol bytes pass through unchanged; TLS identity does not replace Redis
ACL authorization. No request or connection payloads are logged.

TLS terminates at the frontend. Its plaintext hop to the original broker is
restricted to the same Kubernetes node. Required Pod affinity selects the
original `app=redis` Pod and excludes the persistent candidate. The separate
`redis-tls-local` backend Service has `internalTrafficPolicy: Local`, so it cannot
fall back to a remote-node plaintext endpoint. The two frontend replicas share
the source's node/failure domain; they do not make the singleton broker highly
available. No database PVC is mounted by the frontend.

The pinned MariaDB broker Nginx image includes stream TLS and `inotifyd`.
Projected certificate/CA events trigger configuration validation and graceful
reload: old workers retain established streams while fresh workers use the new
certificate. A bad projection marks the frontend NotReady and keeps its previous
workers/connections intact. The next valid projection clears the failure marker.
No forced worker-shutdown timeout is configured.

The exact-image synthetic test verified 301 ordered publications on both an
existing plaintext subscriber and an existing TLS subscriber through invalid-key
projection and valid certificate renewal, with zero disconnects and an unchanged
Valkey run ID. Controls rejected missing/wrong Redis AUTH, an untrusted client
certificate, a wrong server CA and a wrong hostname; a trusted client certificate
worked. Render regression requires every preexisting object to remain identical.

After GitOps deployment, require both frontend Pods Ready on the original
Valkey node, a unique local backend matching the original Pod, a valid served
leaf/root/SAN and successful authenticated TLS PING. Verify the original Pod,
process run ID, Service UID, subscriptions and application traffic are unchanged.
Keep the existing replica handoff/candidate unpromoted until its separate
cache-invalidation and producer-continuity gates are satisfied.
