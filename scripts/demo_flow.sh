#!/usr/bin/env bash
set -e
BASE=${BASE:-http://localhost:8000/api/v1}
echo "== health =="; curl -s http://localhost:8000/health
echo; echo "== register driver =="
curl -s -X POST $BASE/auth/register -H 'Content-Type: application/json' -d '{"email":"d1@test.com","password":"password123","full_name":"D One","role":"driver"}' || true
echo; echo "== login =="
TOKEN=$(curl -s -X POST $BASE/auth/login -H 'Content-Type: application/json' -d '{"email":"driver@demo.test","password":"demo1234"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
HOSTTOKEN=$(curl -s -X POST $BASE/auth/login -H 'Content-Type: application/json' -d '{"email":"host@demo.test","password":"demo1234"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
echo "== search =="; curl -s "$BASE/spots/search?lat=37.7749&lng=-122.4194&radius_km=5"
echo; echo "== hold spot 1 (next hour, 2h) =="
START=$(python3 -c "from datetime import datetime,timedelta,timezone;print((datetime.now(timezone.utc)+timedelta(hours=1)).isoformat())")
END=$(python3 -c "from datetime import datetime,timedelta,timezone;print((datetime.now(timezone.utc)+timedelta(hours=3)).isoformat())")
BOOKING=$(curl -s -X POST $BASE/bookings/hold -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d "{\"spot_id\":1,\"start\":\"$START\",\"end\":\"$END\"}")
echo "$BOOKING"
BID=$(echo "$BOOKING" | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
echo "== confirm =="; curl -s -X POST $BASE/bookings/$BID/confirm -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"payment_method":"mock_card"}'
echo; echo "== QR (headers) =="; curl -s -I $BASE/bookings/$BID/qr -H "Authorization: Bearer $TOKEN" | head -3
echo "== simulate arrival (spot 1 starts in 1h, so expect denied outside window; use QR verify endpoint flow in tests) =="
curl -s -X POST $BASE/vision/simulate -H "Authorization: Bearer $HOSTTOKEN" -H 'Content-Type: application/json' -d '{"camera_id":"cam-001","event":"arrival","plate":"DEMO1234"}'
echo; echo "done"
