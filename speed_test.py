import asyncio
import aiohttp
import time
import os
import csv
import datetime
import signal
import sys
import socket
import xml.etree.ElementTree as ET
from aiohttp import ClientSession, TCPConnector
import itertools

# Number of concurrent tasks
NUM_DOWNLOAD_TASKS = 200  # Adjusted for your hardware
NUM_UPLOAD_TASKS = 200    # Adjusted for your hardware
CHUNK_SIZE = 1024 * 1024   # 1MB chunks
MEASUREMENT_INTERVAL = 10  # Measure average speed every 10 seconds
MAX_RETRIES = 3            # Maximum number of retries for each download/upload
RETRY_BACKOFF = 2          # Backoff multiplier for retries

# Global variables to track the total data downloaded and uploaded
total_downloaded = 0
total_uploaded = 0
total_lock = asyncio.Lock()

# List to store results
results = []
results_lock = asyncio.Lock()

# Flag to indicate whether the program is running
running = True

def resolve_server_ip(url):
    """Resolve the server IP address from its URL."""
    try:
        hostname = url.split('/')[2]
        ip_address = socket.gethostbyname(hostname)
        return ip_address
    except Exception:
        return 'Unknown'

async def download_file(session, download_url, server_info):
    """Download a file to test download speed."""
    global total_downloaded
    start_time = time.time()
    retries = 0

    server_location = server_info.get('country', 'Unknown')
    server_ip = resolve_server_ip(download_url)
    latency = None
    downloaded_size = 0
    error_message = ''
    jitter_values = []

    while retries < MAX_RETRIES and running:
        try:
            # Measure latency
            latency_start = time.time()
            async with session.get(download_url, timeout=10) as response:
                latency_end = time.time()
                latency = latency_end - latency_start

                if response.status != 200:
                    retries += 1
                    error_message = f"HTTP Status {response.status}"
                    await asyncio.sleep(RETRY_BACKOFF ** retries)
                    continue

                while running:
                    chunk = await response.content.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    chunk_size = len(chunk)
                    async with total_lock:
                        total_downloaded += chunk_size
                    downloaded_size += chunk_size

            break  # Exit retry loop after successful download
        except Exception as e:
            retries += 1
            error_message = str(e)
            await asyncio.sleep(RETRY_BACKOFF ** retries)

    end_time = time.time()
    elapsed_time = end_time - start_time
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    async with results_lock:
        results.append({
            'Timestamp': timestamp,
            'Type': 'Download',
            'URL': download_url,
            'Server IP': server_ip,
            'Location': server_location,
            'Total Data (MB)': downloaded_size / (1024 * 1024),
            'Latency (s)': latency,
            'Elapsed Time (s)': elapsed_time,
            'Average Speed (Mbps)': (downloaded_size * 8) / (elapsed_time * 1_000_000) if elapsed_time > 0 else 0,
            'Error Message': error_message
        })

async def upload_file(session, upload_url, server_info):
    """Upload data to a server to test upload speed."""
    global total_uploaded
    start_time = time.time()
    retries = 0

    server_location = server_info.get('country', 'Unknown')
    server_ip = resolve_server_ip(upload_url)
    latency = None
    total_size = 10 * 1024 * 1024  # Total data to upload (e.g., 10MB)
    uploaded_size = 0
    error_message = ''

    while retries < MAX_RETRIES and running:
        try:
            data = os.urandom(total_size)
            latency_start = time.time()
            async with session.post(upload_url, data=data, timeout=10) as response:
                latency_end = time.time()
                latency = latency_end - latency_start

                if response.status not in [200, 201, 204]:
                    retries += 1
                    error_message = f"HTTP Status {response.status}"
                    await asyncio.sleep(RETRY_BACKOFF ** retries)
                    continue

                uploaded_size = len(data)
                async with total_lock:
                    total_uploaded += uploaded_size

            break
        except Exception as e:
            retries += 1
            error_message = str(e)
            await asyncio.sleep(RETRY_BACKOFF ** retries)

    end_time = time.time()
    elapsed_time = end_time - start_time
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    async with results_lock:
        results.append({
            'Timestamp': timestamp,
            'Type': 'Upload',
            'URL': upload_url,
            'Server IP': server_ip,
            'Location': server_location,
            'Total Data (MB)': uploaded_size / (1024 * 1024),
            'Latency (s)': latency,
            'Elapsed Time (s)': elapsed_time,
            'Average Speed (Mbps)': (uploaded_size * 8) / (elapsed_time * 1_000_000) if elapsed_time > 0 else 0,
            'Error Message': error_message
        })

async def worker_download_task(session, server_cycle):
    """Task function to perform continuous downloads."""
    while running:
        server_info = next(server_cycle)
        url = server_info['url']
        await download_file(session, url, server_info)

async def worker_upload_task(session, server_cycle):
    """Task function to perform continuous uploads."""
    while running:
        server_info = next(server_cycle)
        url = server_info['url'].replace('download', 'upload')
        await upload_file(session, url, server_info)

async def calculate_average_speed():
    """Calculate and print the average download and upload speed periodically."""
    global total_downloaded, total_uploaded

    while running:
        start_time = time.time()
        start_downloaded = total_downloaded
        start_uploaded = total_uploaded

        await asyncio.sleep(MEASUREMENT_INTERVAL)

        end_time = time.time()
        end_downloaded = total_downloaded
        end_uploaded = total_uploaded

        data_downloaded = end_downloaded - start_downloaded
        data_uploaded = end_uploaded - start_uploaded
        elapsed_time = end_time - start_time

        average_download_speed_mbps = (data_downloaded * 8) / (elapsed_time * 1_000_000) if elapsed_time > 0 else 0
        average_upload_speed_mbps = (data_uploaded * 8) / (elapsed_time * 1_000_000) if elapsed_time > 0 else 0

        print(f"Average download speed over the last {MEASUREMENT_INTERVAL} seconds: {average_download_speed_mbps:.2f} Mbps")
        print(f"Average upload speed over the last {MEASUREMENT_INTERVAL} seconds: {average_upload_speed_mbps:.2f} Mbps")

def signal_handler(sig, frame):
    """Handle Ctrl+C (SIGINT) signal."""
    global running
    print("\nCtrl+C detected. Stopping all operations...")
    running = False

def save_results_to_csv():
    """Save all collected results to a CSV file."""
    filename = f"results_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    fieldnames = [
        'Timestamp', 'Type', 'URL', 'Server IP', 'Location',
        'Total Data (MB)', 'Latency (s)', 'Elapsed Time (s)', 'Average Speed (Mbps)', 'Error Message'
    ]
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            writer.writerow(result)
    print(f"Results saved to {filename}")

async def get_server_list():
    """Retrieve and parse the list of servers."""
    # URL to the Ookla server list
    server_list_url = "https://www.speedtest.net/speedtest-servers-static.php"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(server_list_url) as response:
                content = await response.text()
                root = ET.fromstring(content)

        servers = []
        countries = set()

        for server in root.iter('server'):
            url = server.attrib.get('url')
            country = server.attrib.get('country')
            if url and country:
                servers.append({
                    'url': url,
                    'country': country
                })
                countries.add(country)

        print(f"Retrieved {len(servers)} servers from {len(countries)} countries.")
        return servers

    except Exception as e:
        print(f"Failed to retrieve server list: {e}")
        sys.exit(1)

async def main():
    """Main function to run concurrent transfers."""
    global running

    # Register signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)

    # Retrieve the server list
    servers = await get_server_list()

    # Cycle through servers to ensure each is tested
    download_server_cycle = itertools.cycle(servers)
    upload_server_cycle = itertools.cycle(servers)

    # Use a connector with a high limit
    connector = TCPConnector(limit=1000)

    async with ClientSession(connector=connector) as session:
        # Start the speed calculation task
        speed_task = asyncio.create_task(calculate_average_speed())

        # Start download tasks
        download_tasks = [
            asyncio.create_task(worker_download_task(session, download_server_cycle))
            for _ in range(NUM_DOWNLOAD_TASKS)
        ]

        # Start upload tasks
        upload_tasks = [
            asyncio.create_task(worker_upload_task(session, upload_server_cycle))
            for _ in range(NUM_UPLOAD_TASKS)
        ]

        # Wait until running is False
        try:
            while running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            # Cancel all tasks
            for task in download_tasks + upload_tasks + [speed_task]:
                task.cancel()
            await asyncio.gather(*download_tasks, *upload_tasks, speed_task, return_exceptions=True)
            save_results_to_csv()

if __name__ == "__main__":
    print("Starting continuous concurrent downloads and uploads...")
    asyncio.run(main())
