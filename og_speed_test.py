import threading
import requests
import time
import random

# List of reliable download URLs from different high-capacity servers
DOWNLOAD_URLS = [
    "http://proof.ovh.net/files/10Gb.dat",  # OVH
    "http://speedtest.tele2.net/10GB.zip",  # Tele2
    "https://ipv4.download.thinkbroadband.com/10GB.zip",  # Thinkbroadband
    "http://ipv4.download.thinkbroadband.com/5GB.zip",  # Thinkbroadband (smaller file)
    "http://speedtest.belwue.net/10G",  # BelWue
]

NUM_THREADS = 100  # Further increased number of threads to maximize download speed
CHUNK_SIZE = 2 * 1024 * 1024  # 2MB chunks for faster processing
MEASUREMENT_INTERVAL = 60  # Measure average speed every 60 seconds
MAX_RETRIES = 3  # Maximum number of retries for each download
RETRY_BACKOFF = 2  # Backoff multiplier for retries
CONNECTIONS_PER_URL = 10  # Further increased connections per URL

# Global variable to track the total data downloaded
total_downloaded = 0
total_lock = threading.Lock()

def download_file(download_url):
    """Download a large file to max out the download speed."""
    global total_downloaded
    
    retries = 0
    
    while retries < MAX_RETRIES:
        try:
            print(f"Starting download from {download_url}")
            response = requests.get(download_url, stream=True)
            
            # Check if the request was successful
            if response.status_code != 200:
                print(f"Error: Received status code {response.status_code} for URL {download_url}")
                retries += 1
                time.sleep(RETRY_BACKOFF ** retries)  # Exponential backoff
                continue
            
            # Check for content length and handle large file download
            total_size = int(response.headers.get('content-length', 0))
            if total_size == 0:
                print(f"Error: Unable to retrieve content length from {download_url}")
                retries += 1
                time.sleep(RETRY_BACKOFF ** retries)
                continue
            
            downloaded_size = 0
            for chunk in response.iter_content(CHUNK_SIZE):
                with total_lock:
                    total_downloaded += len(chunk)
                    downloaded_size += len(chunk)
            
            print(f"Completed download from {download_url}")
            break  # Exit retry loop after successful download
        except requests.exceptions.RequestException as e:
            print(f"Exception occurred while downloading from {download_url}: {e}")
            retries += 1
            time.sleep(RETRY_BACKOFF ** retries)  # Exponential backoff
    
def download_from_multiple_connections(url):
    """Download from a single URL using multiple connections."""
    threads = []
    for _ in range(CONNECTIONS_PER_URL):
        thread = threading.Thread(target=download_file, args=(url,))
        threads.append(thread)
        thread.start()
    
    for thread in threads:
        thread.join()

def calculate_average_speed():
    """Calculate and print the average download speed every minute."""
    global total_downloaded
    
    while True:
        start_time = time.time()
        start_downloaded = total_downloaded
        
        time.sleep(MEASUREMENT_INTERVAL)
        
        end_time = time.time()
        end_downloaded = total_downloaded
        
        # Calculate the amount of data downloaded in the last interval
        data_downloaded = end_downloaded - start_downloaded
        elapsed_time = end_time - start_time
        
        # Convert bytes to megabits (1 byte = 8 bits, 1 megabit = 1,000,000 bits)
        average_speed_mbps = (data_downloaded * 8) / (elapsed_time * 1_000_000)
        
        print(f"Average download speed over the last {MEASUREMENT_INTERVAL} seconds: {average_speed_mbps:.2f} Mbps")

def run_concurrent_downloads(num_threads):
    """Run multiple threads to perform concurrent downloads continuously."""
    threads = []
    
    # Start download threads for each URL using multiple connections
    for _ in range(num_threads):
        url = random.choice(DOWNLOAD_URLS)
        thread = threading.Thread(target=download_from_multiple_connections, args=(url,))
        threads.append(thread)
        thread.start()
    
    # Start the speed calculation thread
    speed_thread = threading.Thread(target=calculate_average_speed)
    threads.append(speed_thread)
    speed_thread.start()

    for thread in threads:
        thread.join()

if __name__ == "__main__":
    # Run concurrent downloads in a continuous loop
    print("Starting continuous concurrent downloads...")
    run_concurrent_downloads(NUM_THREADS)