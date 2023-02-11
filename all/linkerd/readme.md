## control plane

install linkerd control plane with the command
```
helm install linkerd-control-plane -n linkerd \
  --set-file identityTrustAnchorsPEM=ca.crt \
  --set identity.issuer.scheme=kubernetes.io/tls \
  linkerd/linkerd-control-plane
```

reference: https://linkerd.io/2.12/tasks/automatically-rotating-control-plane-tls-credentials/
