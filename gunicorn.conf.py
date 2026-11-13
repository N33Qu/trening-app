import glob
import os

bind = "0.0.0.0:8000"
workers = int(os.environ.get("GUNICORN_WORKERS", "2"))
threads = int(os.environ.get("GUNICORN_THREADS", "2"))
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "60"))
graceful_timeout = 20
keepalive = 5
preload_app = True
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info").lower()
worker_tmp_dir = os.environ.get("GUNICORN_WORKER_TMP_DIR", "/tmp")  # noqa: S108 - only writable path
forwarded_allow_ips = "*"
control_socket_disable = True
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(M)sms "%(a)s"'

_prom_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
if _prom_dir:
    os.makedirs(_prom_dir, exist_ok=True)
    for _f in glob.glob(os.path.join(_prom_dir, "*.db")):
        os.remove(_f)


def child_exit(server, worker):
    if _prom_dir:
        from prometheus_client import multiprocess

        multiprocess.mark_process_dead(worker.pid)
