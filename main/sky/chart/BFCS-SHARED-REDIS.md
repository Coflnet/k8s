# BFCS Redis TLS coexistence and global publication hold

Keep every existing broker and publisher running. The independent EU
`sky-bfcs-redis-shared` broker is additive; its presence and EU subscriptions do
not prove global consumer continuity. Linode, CloudFanatic, Datawagon and Contabo
also serve BFCS WebSocket consumers. BFCS publishes to one `FLIP_REDIS_OPTIONS`
endpoint and subscribes to every `REDIS_FLIP_INSTANCES` entry. It forwards received
messages to WebSocket clients, not into its own publication broker.

The global publication transition is held. The helper's legacy `consume` and
`publish` commands now fail with a clear error before reading or changing KV.
An EU-only receipt cannot authorize changing the shared `FLIP_REDIS_OPTIONS` key.
The requested independent second-broker and dual-consumer migration remains
pending verified TLS routes and subscriptions for every global consumer.
The remote optional TLS frontends are phase-one support on the original brokers,
as documented in `BFCS-REMOTE-TLS.md`; they do not perform that migration.

The existing `kv/sky/sky-bfcs` leaf is read by both EU and Linode. Its appended
EU-internal `.svc` consumer entry must therefore leave shared KV. ModCommands's
EU-internal entry must also become explicitly EU-only before future reuse of its
shared configuration. Every previous broker/consumer entry stays unchanged.

1. Reconcile the EU chart with `global.bfcsSharedRedis.consumersEnabled: true`.
   Alongside its existing shared-root trust mount, the EU BFCS Deployment now
   declares the exact existing consumer connection as environment entry
   `REDIS_FLIP_INSTANCES__3`; the EU ModCommands Rollout declares `__4`.
   Shared KV temporarily overrides those entries with the same value, so this
   source deployment does not change the effective connection. Keep publishing
   unchanged. Stop on scheduling, readiness or analysis failure.
2. Audit `configure-bfcs-redis-coexistence.py cleanup-shared-consumers
   --consumer-receipt PRIVATE/consumers.json --kubeconfig KUBECONFIG` inside the
   existing narrow OpenBao session. `cleanup-shared-consumers --print-policy`
   renders its exact two-leaf task ACL. The helper verifies the EU cluster UID,
   full healthy rollouts, the exact environment on both owner templates and all
   current Pods, independent old/new brokers, certificate freshness and both
   subscriptions from every EU consumer before reading the two KV leaves.
3. Add `--execute --receipt PRIVATE/cleanup.json` in the narrow child session.
   The helper refuses a changed publisher or occupied/ambiguous consumer index,
   preflights both leaves before any write, and CAS merge-patches JSON null only
   for the two exact appended entries. Readback must equal the previous map
   minus those entries, including every unrelated field. An already absent key
   is safe for resuming a partial successful cleanup. It records private,
   immutable metadata evidence. Revoke the child, prove403 and remove its artifact.
4. Verify EU subscriptions remain healthy after cleanup. Linode's shared KV no
   longer supplies the unreachable EU-local address on reload or restart. All
   publication targets, existing broker processes and prior consumer routes stay.

Use `verify --consumer-receipt PRIVATE/consumers.json --kubeconfig KUBECONFIG
--receipt PRIVATE/eu-canary.json` for read-only EU validation. Its receipt is
explicitly EU-scoped and cannot release the global publication hold.

For eventual migration, separate cluster-specific publication topology from
shared credential KV, enumerate every live consumer, and establish verified TLS
DNS/TCP/CA/SAN routes and both subscriptions from each actual consumer Pod to
every proposed publication broker. Keep old and new brokers subscribed throughout
any reviewed publisher transition. A Ready Pod is insufficient:
`ModBackgroundService` can skip an unreachable entry at startup after connecting
to another broker. Retirement and mandatory mTLS remain separate operations.
