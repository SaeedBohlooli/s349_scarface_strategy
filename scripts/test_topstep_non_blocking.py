from topstep_thread_launcher import fire_topstep_nonblocking;
import time
def demo_nonblocking_real():
    t0 = time.perf_counter()
    for i in range(10):
        if i == 2:
            fire_topstep_nonblocking(side="long")   # sends using accounts from config
        if i == 5:
            fire_topstep_nonblocking(side="short")  # sends using accounts from config
        print(f"tick {i} @ {time.perf_counter() - t0:.2f}s")
        time.sleep(0.3)
if __name__ == "__main__":
    demo_nonblocking_real()
    print("loop finished; background client still may be working.")