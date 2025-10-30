# at top of your decision-loop module
from concurrent.futures import ThreadPoolExecutor
import threading
from topstep_client import topstep_order_execution, CONFIG_PATH  # import your client

_TOPSTEP_EXECUTOR = ThreadPoolExecutor(max_workers=2)  # tune as needed
__TOPSTEP_PENDING = set()        # avoid overlapping same-side bursts
__PENDING_LOCK = threading.Lock()
def fire_topstep_nonblocking(*, side: str):
    key = (side)
    print(f"[topstep] async {side} started")

    # prevent duplicate in-flight calls for the same key
    with __PENDING_LOCK:
        if key in __TOPSTEP_PENDING:
            return
        __TOPSTEP_PENDING.add(key)

    def _worker():
        try:
            # No result() / no waiting — this is fire-and-forget
            print(f"[topstep] async order request for {side} was sent, we are not placing orders today.")
            #topstep_order_execution(side=side, add_app_headers=False)
        except Exception as e:
            # optional: log/notify
            print(f"[topstep] async {side} failed: {e}")
        finally:
            with __PENDING_LOCK:
                __TOPSTEP_PENDING.discard(key)

    _TOPSTEP_EXECUTOR.submit(_worker)
