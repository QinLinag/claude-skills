#!/usr/bin/env bash
# 把离线版页面 + plan.md + 路线图放到用户自己的服务器上，给手机 Safari/微信/手机 Claude 用。
# 这是对外发布（公网可访问），每次都要先得到用户同意。
#
#   deploy.sh <ssh-host> <行程目录> <下线日期 YYYY-MM-DD> [端口，默认 28765]
#
# 服务器上：/opt/trip-pages/serve.py + systemd 服务 trip-pages（DynamicUser，只认随机路径，其余 404）；
# 每个行程一个随机 token 目录 /srv/trip-pages/<token>/，到下线日期北京时间 00:00 由 transient timer 自动删除。
set -euo pipefail
HOST=$1 TRIP=$2 EXPIRE=$3 PORT=${4:-28765}
HERE=$(cd "$(dirname "$0")" && pwd)
OFF="$TRIP/offline"
HTML=$(ls "$OFF"/*.html | head -1)
TOKEN_FILE="$TRIP/host_token"
[ -f "$TOKEN_FILE" ] || echo "trip-$(openssl rand -hex 8)" > "$TOKEN_FILE"
TOKEN=$(cat "$TOKEN_FILE")
STAGE=$(mktemp -d)
cp "$HTML" "$STAGE/index.html" && gzip -9 -k "$STAGE/index.html"
[ -f "$OFF/plan.md" ] && cp "$OFF/plan.md" "$STAGE/plan.md"
[ -f "$OFF/路线总览.jpg" ] && cp "$OFF/路线总览.jpg" "$STAGE/map.jpg"

ssh "$HOST" "mkdir -p /opt/trip-pages /srv/trip-pages/$TOKEN"
scp -q "$HERE/serve.py" "$HOST:/opt/trip-pages/serve.py"
scp -q "$STAGE"/* "$HOST:/srv/trip-pages/$TOKEN/"
ssh "$HOST" bash -s <<EOF
set -e
chmod 755 /srv/trip-pages /srv/trip-pages/$TOKEN && chmod 644 /srv/trip-pages/$TOKEN/* /opt/trip-pages/serve.py
if [ ! -f /etc/systemd/system/trip-pages.service ]; then
  printf '%s\n' '[Unit]' 'Description=Static trip pages (random-token paths)' 'After=network-online.target' '' \
    '[Service]' 'Environment=PORT=$PORT' 'ExecStart=/usr/bin/python3 /opt/trip-pages/serve.py' 'DynamicUser=yes' 'Restart=always' 'RestartSec=3' '' \
    '[Install]' 'WantedBy=multi-user.target' > /etc/systemd/system/trip-pages.service
  systemctl daemon-reload && systemctl enable trip-pages
fi
systemctl restart trip-pages
systemctl stop trip-expire-$TOKEN.timer 2>/dev/null || true
systemctl reset-failed trip-expire-$TOKEN.service trip-expire-$TOKEN.timer 2>/dev/null || true
systemd-run --quiet --unit=trip-expire-$TOKEN --on-calendar="$EXPIRE 00:00:00 Asia/Shanghai" /bin/rm -rf /srv/trip-pages/$TOKEN
EOF
rm -rf "$STAGE"
IP=$(ssh -G "$HOST" | awk '/^hostname /{print $2}')
U="http://$IP:$PORT/$TOKEN"
for p in "" plan.md map.jpg; do
  printf '%-10s %s  ' "${p:-网页}" "$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' --max-time 60 "$U/$p")"; echo "$U/$p"
done
echo "（$EXPIRE 00:00 北京时间自动下线）"
