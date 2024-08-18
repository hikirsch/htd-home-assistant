import socket
import time

from htd.discovery import discover_gateways


def get_local_ip_prefix():
    # Get the local machine's IP address
    local_ip = socket.gethostbyname(socket.gethostname())
    # Extract the prefix (first three octets)
    ip_parts = local_ip.split('.')
    return '.'.join(ip_parts[:3]) + '.'


def main():
    # base_ip = get_local_ip_prefix()
    base_ip = "192.168.200."
    start_time = time.perf_counter()
    print("Start Time: %f" % start_time)
    found = discover_gateways(base_ip)
    end_time = time.perf_counter()
    print("End Time: %f" % end_time)
    print("Time took: %f" % (end_time - start_time))

    print(found)


main()
