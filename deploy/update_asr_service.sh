#!/usr/bin/env bash
# Run on the existing Ubuntu VM after pulling this release, before updating web.
set -euo pipefail
cd /opt/avar
test -r /home/ubuntu/asr-transfer/service/asr.env
test -r /home/ubuntu/asr-transfer/model/manifest.json
docker inspect avar-asr >/dev/null
docker network inspect avar_default >/dev/null
docker build -t avar-asr:upload10-v1 deploy/asr_service
old="avar-asr-before-upload10-$(date -u +%Y%m%dT%H%M%SZ)"
rollback() {
  echo 'ASR update failed; restoring previous container.' >&2
  docker rm -f avar-asr >/dev/null 2>&1 || true
  docker rename "$old" avar-asr
  docker start avar-asr >/dev/null
}
docker stop avar-asr >/dev/null
docker rename avar-asr "$old"
trap rollback ERR
docker run -d --name avar-asr --restart unless-stopped --network avar_default \
  --user "$(id -u ubuntu):$(id -g ubuntu)" --memory 6g --memory-swap 6g \
  --cpus 1 --pids-limit 128 --read-only --tmpfs /tmp:rw,nosuid,size=128m \
  --cap-drop ALL --security-opt no-new-privileges \
  --env-file /home/ubuntu/asr-transfer/service/asr.env \
  --mount type=bind,src=/home/ubuntu/asr-transfer/model,dst=/models,readonly \
  avar-asr:upload10-v1 >/dev/null
ready=0
for attempt in $(seq 1 45); do
  if docker exec avar-asr python -c 'import os,json,urllib.request; r=urllib.request.Request("http://127.0.0.1:8090/health",headers={"Authorization":"Bearer "+os.environ["ASR_INTERNAL_TOKEN"]}); d=json.load(urllib.request.urlopen(r,timeout=3)); assert d["ready"] and d["max_seconds"]==10' 2>/dev/null; then
    ready=1; break
  fi
  sleep 2
done
test "$ready" = 1
trap - ERR
echo "ASR ready: 10 seconds. Previous container retained: $old"
