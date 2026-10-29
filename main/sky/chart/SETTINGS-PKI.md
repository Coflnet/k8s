# Settings external CQL client enrollment

Internal HTTP and Redis stay on their existing paths; the EU cluster already uses
Cilium WireGuard. This chart requests only the external CQL client identity.
The optional internal HTTPS/Redis prototype is deferred and is not applied here.

Both certificate issuance and application activation default off. Only the EU
Fleet target loads `settings-pki-eu.yaml`, which stages the dedicated
`sky-settings-client` Issuer/Certificate, `sky-settings-certificates` TokenRequest
service account/RBAC and public CQL trust. The Deployment remains unchanged while
`pki.applicationEnabled` is false. All application additions require both
`pki.enabled` and `pki.applicationEnabled`; disabling issuance also disables them.
No server certificate or HTTPS policy is requested.

The CQL trust bundle contains the actual legacy `scylla-client` CA plus the shared
root. The explicit server name is `sky-client`. Existing CQL hosts, keyspace and
password authentication remain unchanged. Kafka files, paths and SASL settings,
HTTP 8000 and the standalone plaintext Settings Redis connection are preserved.
Use this rollout order:

1. Stage the Issuer and client Certificate; require the Certificate to be Ready.
2. With the existing Core image, set `pki.applicationEnabled: true`, keep
   `pki.readinessEnabled: false`, and change `pki.revision`. This prepares whole
   read-only client/trust mounts, private writable memory-backed HOME and
   `fsGroup: 1000` before introducing strict PEM handling. Verify the existing
   connection guard and let this prepared rollout complete with its original
   readiness probe. The chart does not change an image.
3. Promote the reviewed Core 0.7.5 Settings source image through normal CI/Argo.
   Bind the connection guard to the exact image, Pod UID and container ID. Inspect
   the Running candidate directly, even while NotReady, within 60 seconds; do not
   wait for the existing 90-second readiness delay. Require `/health/ready` to
   succeed and verify external CQL TLS plus the existing Redis connection. The
   new startup check and endpoint each perform a fresh CQL SELECT and Redis PING
   within five seconds.
4. After the full warmup and rollout, optionally set `pki.readinessEnabled: true`
   to select `/health/ready`. Preserve the original 90-second delay and other
   probe timing settings.

Kafka migration is a separate certificate and connection gate.
