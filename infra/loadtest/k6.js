import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  insecureSkipTLSVerify: true,
  stages: [
    { duration: '1m', target: 50 },
    { duration: '3m', target: 50 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<1000'],
  },
};

const BASE = __ENV.BASE_URL || 'https://trening.local';

export default function () {
  const r1 = http.get(`${BASE}/`);
  check(r1, { 'login page 200': (r) => r.status === 200 });
  const r2 = http.get(`${BASE}/healthz`);
  check(r2, { 'healthz 200': (r) => r.status === 200 });
  sleep(0.2);
}
