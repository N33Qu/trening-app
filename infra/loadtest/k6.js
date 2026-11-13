import http from 'k6/http';
import { check, sleep } from 'k6';

// Uzycie: k6 run -e HOSTS_IP=127.0.0.1:8443 infra/loadtest/k6.js
// (HOSTS_IP mapuje trening.local na adres port-forwardu; bez zmiennej uzywany jest DNS/hosts)
// VUS - liczba wirtualnych uzytkownikow (domyslnie 50)
const VUS = parseInt(__ENV.VUS || '50', 10);
const HOST = __ENV.HOST || 'trening.local';

export const options = {
  insecureSkipTLSVerify: true,
  hosts: __ENV.HOSTS_IP ? { [HOST]: __ENV.HOSTS_IP } : {},
  stages: [
    { duration: '1m', target: VUS },
    { duration: '3m', target: VUS },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<1000'],
  },
};

const BASE = __ENV.BASE_URL || `https://${HOST}`;

export default function () {
  const r1 = http.get(`${BASE}/`);
  check(r1, { 'login page 200': (r) => r.status === 200 });
  const r2 = http.get(`${BASE}/healthz`);
  check(r2, { 'healthz 200': (r) => r.status === 200 });
  sleep(0.2);
}
