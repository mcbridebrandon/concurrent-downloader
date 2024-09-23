import asyncio
import pingparsing
import time
import random

# List of known global servers for testing. (Replace with a more extensive list if needed)
SERVERS = [
    "8.8.8.8",  # Google DNS
    "1.1.1.1",  # Cloudflare DNS
    "208.67.222.222",  # OpenDNS
    "9.9.9.9",  # Quad9 DNS
    "8.8.4.4",  # Google DNS
    "208.67.220.220",  # OpenDNS
    "4.2.2.2",  # Level3 DNS
    "1.0.0.1",  # Cloudflare DNS Secondary
    # Add more public servers or servers of interest
]

# Create a PingParsing object
ping_parser = pingparsing.PingParsing()

# Function to ping a server and get metrics
async def ping_server(server):
    transmitter = pingparsing.PingTransmitter()
    transmitter.destination = server
    transmitter.count = 10  # Number of ICMP requests per server (increase for more precision)
    transmitter.interval = 0.2  # Interval between pings (seconds)

    try:
        result = transmitter.ping()
        metrics = ping_parser.parse(result).as_dict()
        print(f"Ping to {server}:\n"
              f"  Avg Latency: {metrics['rtt_avg']} ms\n"
              f"  Max Latency: {metrics['rtt_max']} ms\n"
              f"  Min Latency: {metrics['rtt_min']} ms\n"
              f"  Packet Loss: {metrics['packet_loss_rate']} %\n"
              f"  Jitter: {metrics['rtt_mdev']} ms\n")
    except Exception as e:
        print(f"Failed to ping {server}: {e}")

# Function to perform concurrent ping testing to all servers
async def ping_all_servers():
    tasks = []
    for server in SERVERS:
        tasks.append(asyncio.create_task(ping_server(server)))
    await asyncio.gather(*tasks)

# Main function to run the ping testing continuously at the highest possible frequency
async def main():
    while True:
        await ping_all_servers()
        await asyncio.sleep(0.5)  # Delay between full rounds of testing (adjust based on need)

if __name__ == "__main__":
    asyncio.run(main())
