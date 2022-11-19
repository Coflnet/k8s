#!/bin/bash
# Delete CRD finalizers, instances and definitions
for crd in $(kubectl get crd -o jsonpath={.items[*].metadata.name} | tr ' ' '\n' | grep longhorn.rancher.io); do
  kubectl -n longhorn get $crd -o yaml | sed "s/\- longhorn.rancher.io//g" | kubectl apply -f -
  kubectl -n longhorn delete $crd --all
  kubectl delete crd/$crd
done

